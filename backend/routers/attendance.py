"""
routers/attendance.py — Process a group photo and export attendance CSV.
"""

import csv
import io
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

import database
from services.face_service import match_group_photo
from services.image_service import annotate_image

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.post("/process")
async def process_attendance(
    class_name: str = Form(...),
    photo: UploadFile = File(...),
    attendance_date: str = Form(default=""),  # optional; defaults to today
):
    """
    Upload a group photo → run face recognition → return annotated image + results.

    The heavy lifting happens in face_service.match_group_photo().
    This endpoint just orchestrates: load DB → run recognition → annotate → respond.
    """
    if not attendance_date:
        attendance_date = str(date.today())

    image_bytes = await photo.read()

    # Load enrolled students for this class (with their embeddings) from the database
    all_students = database.get_all_students_with_embeddings(class_name)
    if not all_students:
        raise HTTPException(
            status_code=400,
            detail="No students enrolled yet. Please enroll students before taking attendance."
        )

    logger.info(f"Processing attendance for class={class_name}, date={attendance_date}, students_in_db={len(all_students)}")

    # Run face detection + matching
    try:
        face_results = match_group_photo(image_bytes, all_students)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Face matching failed: {e}")
        raise HTTPException(status_code=500, detail="Face recognition failed. Check server logs.")

    # Annotate the original image with colored boxes
    try:
        annotated_b64 = annotate_image(image_bytes, face_results)
    except Exception as e:
        logger.error(f"Image annotation failed: {e}")
        raise HTTPException(status_code=500, detail="Image annotation failed.")

    recognized = [f for f in face_results if f["status"] == "recognized"]
    unknown = [f for f in face_results if f["status"] == "unknown"]

    return {
        "annotated_image": annotated_b64,
        "date": attendance_date,
        "class_name": class_name,
        "results": face_results,
        "total_faces": len(face_results),
        "recognized_count": len(recognized),
        "unknown_count": len(unknown),
    }


@router.get("/export")
async def export_csv(
    class_name: str = Query(...),
    attendance_date: str = Query(...),
    roll_numbers: str = Query(default=""),  # comma-separated list of recognized roll numbers
):
    """
    Stream a CSV file for the recognized students.

    Usage: GET /api/attendance/export?class_name=10-A&date=2026-03-05&roll_numbers=CS101,CS102

    The browser downloads a file named "{date}_{class_name}.csv".
    StreamingResponse is used so large files don't need to be held in memory.
    """
    # Parse the comma-separated roll numbers
    roll_list = [r.strip() for r in roll_numbers.split(",") if r.strip()] if roll_numbers else []

    # Build CSV in memory (small enough for typical class sizes)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Roll Number", "Class", "Date", "Status"])

    if roll_list:
        # Look up each recognized student from the DB
        matched_students = database.get_students_by_roll_numbers(roll_list)

        for s in matched_students:
            writer.writerow([s["name"], s["roll_number"], s["class_name"], attendance_date, "Present"])

    output.seek(0)

    filename = f"{attendance_date}_{class_name}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
