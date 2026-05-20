"""
routers/attendance.py — Process a group photo, persist results, export CSV.

Recognition results are saved to attendance_records so the same date+class
combination can be re-exported later without re-running the model.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger

import database
from auth.dependencies import get_current_user
from services.face_service import match_group_photo
from services.image_service import annotate_image

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.post("/process")
async def process_attendance(
    class_name: str = Form(...),
    photo: UploadFile = File(...),
    attendance_date: str = Form(default=""),
    user: dict = Depends(get_current_user),
):
    if not attendance_date:
        attendance_date = str(date.today())

    image_bytes = await photo.read()
    recognizer_name = user["preferred_recognizer"]

    # Make sure this user has at least one student encoded with the current recognizer
    current_recognizer_count = len(
        database.get_user_students_with_embeddings(user["id"], recognizer_name)
    )
    if current_recognizer_count == 0:
        total_in_db = len(database.get_user_students(user["id"]))
        if total_in_db == 0:
            raise HTTPException(status_code=400,
                                detail="No students enrolled yet. Enroll students first.")
        raise HTTPException(
            status_code=400,
            detail=(f"You have {total_in_db} students enrolled, but none with the "
                    f"current recognizer ('{recognizer_name}'). Switch recognizer "
                    "in Settings or re-enroll."),
        )

    logger.info(f"[user={user['id']}] processing attendance class={class_name} "
                f"date={attendance_date} recognizer={recognizer_name}")

    try:
        face_results = match_group_photo(image_bytes, user["id"], recognizer_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Face matching failed: {e}")
        raise HTTPException(status_code=500, detail="Face recognition failed. Check server logs.")

    try:
        annotated_b64 = annotate_image(image_bytes, face_results)
    except Exception as e:
        logger.error(f"Image annotation failed: {e}")
        raise HTTPException(status_code=500, detail="Image annotation failed.")

    # Persist recognized students to attendance_records (one row each).
    roll_to_student = {
        s["roll_number"]: s for s in database.get_user_students(user["id"])
    }
    for r in face_results:
        if r["status"] != "recognized":
            continue
        s = roll_to_student.get(r["roll_number"])
        if s:
            database.record_attendance(
                user_id=user["id"], student_id=s["id"],
                class_name=class_name, attendance_date=attendance_date,
                status="present", similarity=r["similarity"],
            )

    recognized = [f for f in face_results if f["status"] == "recognized"]
    unknown = [f for f in face_results if f["status"] == "unknown"]

    return {
        "annotated_image": annotated_b64,
        "date": attendance_date,
        "class_name": class_name,
        "recognizer": recognizer_name,
        "results": face_results,
        "total_faces": len(face_results),
        "recognized_count": len(recognized),
        "unknown_count": len(unknown),
    }


@router.get("/export")
async def export_csv(
    class_name: str = Query(...),
    attendance_date: str = Query(...),
    roll_numbers: str = Query(default=""),
    user: dict = Depends(get_current_user),
):
    """Stream a CSV file with the recognized students for this date+class."""
    roll_list = [r.strip() for r in roll_numbers.split(",") if r.strip()] if roll_numbers else []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Roll Number", "Class", "Date", "Status"])

    if roll_list:
        all_students = database.get_user_students(user["id"])
        student_map = {s["roll_number"]: s for s in all_students}
        for roll in roll_list:
            if roll in student_map:
                s = student_map[roll]
                writer.writerow([s["name"], s["roll_number"], s["class_name"],
                                 attendance_date, "Present"])

    output.seek(0)
    filename = f"{attendance_date}_{class_name}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_DEMO_GROUP_PHOTO = Path(__file__).parent.parent / "demo_assets" / "group" / "class.jpg"


@router.get("/demo-classes")
async def list_demo_sample_classes(user: dict = Depends(get_current_user)):
    """List the demo classes bundled with the app (synthetic + Apollo 11)."""
    from seed_demo import list_demo_classes
    return {"classes": list_demo_classes()}


@router.get("/demo-group-photo")
async def demo_group_photo(class_name: str = Query("Demo-Class"),
                           user: dict = Depends(get_current_user)):
    """Serve the bundled group photo for a demo class."""
    from seed_demo import demo_group_photo as resolve
    path = resolve(class_name)
    if not path:
        raise HTTPException(status_code=404,
                            detail=f"No demo group photo for class '{class_name}'.")
    return FileResponse(path, media_type="image/jpeg",
                        filename=f"demo_{class_name}.jpg")


@router.get("/history")
async def attendance_history(
    class_name: str = Query(...),
    attendance_date: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Return the persisted roll for a (class, date) pair."""
    records = database.list_attendance(user["id"], class_name, attendance_date)
    return {"records": records, "count": len(records)}
