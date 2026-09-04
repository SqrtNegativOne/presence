"""
routers/attendance.py — Process a group photo, persist sessions/records, and export attendance CSV.
"""

import csv
import hashlib
import io
from datetime import date

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

import database
from services.face_service import match_embeddings, match_group_photo
from services.image_service import annotate_image

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


class MatchEmbeddingsRequest(BaseModel):
    class_name: str
    attendance_date: str = Field(default="")
    embeddings: list[list[float]] = Field(default_factory=list)
    model_type: str = Field(default="faceapi")
    photo_hash: str | None = None
    bboxes: list[list[int] | None] | None = None


@router.post("/process")
async def process_attendance(
    class_name: str = Form(...),
    photo: UploadFile = File(...),
    attendance_date: str = Form(default=""),  # optional; defaults to today
):
    """
    Upload a group photo → run face recognition → annotate image → persist session & records → respond.
    """
    if not attendance_date:
        attendance_date = str(date.today())

    image_bytes = await photo.read()
    photo_hash = hashlib.sha256(image_bytes).hexdigest()

    # Load enrolled students for this class (with their embeddings) from the database
    all_students = database.get_all_students_with_embeddings(class_name)
    if not all_students:
        raise HTTPException(
            status_code=400,
            detail="No students enrolled yet. Please enroll students before taking attendance.",
        )

    logger.info(
        f"Processing attendance for class={class_name}, date={attendance_date}, students_in_db={len(all_students)}"
    )

    # Run face detection + matching
    try:
        face_results = match_group_photo(image_bytes, all_students)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Face matching failed: {e}")
        raise HTTPException(
            status_code=500, detail="Face recognition failed. Check server logs."
        )

    # Annotate the original image with colored boxes
    try:
        annotated_b64 = annotate_image(image_bytes, face_results)
    except Exception as e:
        logger.error(f"Image annotation failed: {e}")
        raise HTTPException(status_code=500, detail="Image annotation failed.")

    recognized = [f for f in face_results if f["status"] == "recognized"]
    unknown = [f for f in face_results if f["status"] == "unknown"]

    # Identify absent students (enrolled minus recognized)
    student_map = {s["id"]: s for s in all_students}
    enrolled_ids = set(student_map.keys())
    recognized_ids = {r["student_id"] for r in recognized if r.get("student_id")}
    absent_ids = enrolled_ids - recognized_ids

    absent_students = [
        {
            "face_index": None,
            "bbox": None,
            "student_id": student_map[sid]["id"],
            "name": student_map[sid]["name"],
            "roll_number": student_map[sid]["roll_number"],
            "class_name": student_map[sid]["class_name"],
            "status": "absent",
            "similarity": None,
        }
        for sid in sorted(
            absent_ids,
            key=lambda sid: (student_map[sid]["roll_number"], student_map[sid]["name"]),
        )
    ]

    # Persist the attendance session
    session_id = database.create_attendance_session(
        class_name=class_name,
        attendance_date=attendance_date,
        total_faces=len(face_results),
        recognized_count=len(recognized),
        unknown_count=len(unknown),
        photo_hash=photo_hash,
    )

    # Persist attendance records for all enrolled students
    records_to_insert = []
    for r in recognized:
        records_to_insert.append(
            {
                "student_id": r["student_id"],
                "status": "present",
                "similarity": r.get("similarity"),
                "face_index": r.get("face_index"),
            }
        )
    for a in absent_students:
        records_to_insert.append(
            {
                "student_id": a["student_id"],
                "status": "absent",
                "similarity": None,
                "face_index": None,
            }
        )
    database.insert_attendance_records(session_id, records_to_insert)

    return {
        "session_id": session_id,
        "annotated_image": annotated_b64,
        "date": attendance_date,
        "class_name": class_name,
        "results": face_results + absent_students,
        "total_faces": len(face_results),
        "recognized_count": len(recognized),
        "unknown_count": len(unknown),
        "absent_count": len(absent_students),
    }


@router.post("/match-embeddings")
async def match_embeddings_attendance(payload: MatchEmbeddingsRequest):
    """
    Match client-computed face embeddings against enrolled students.
    Used in local mode where the browser extracts embeddings and never uploads the group photo.
    """
    class_name = payload.class_name.strip()
    attendance_date = payload.attendance_date.strip() or str(date.today())
    model_type = payload.model_type.strip() or "faceapi"

    if not class_name:
        raise HTTPException(status_code=400, detail="class_name is required.")

    # Load enrolled students for this class with matching model_type
    all_students = database.get_all_students_with_embeddings(
        class_name, model_type=model_type
    )
    if not all_students:
        raise HTTPException(
            status_code=400,
            detail=f"No students enrolled yet for class '{class_name}' with model '{model_type}'. Please enroll students before taking attendance.",
        )

    query_embeddings = [np.array(emb, dtype=np.float32) for emb in payload.embeddings]
    face_results = match_embeddings(
        query_embeddings=query_embeddings,
        known_students=all_students,
        bboxes=payload.bboxes,
    )

    recognized = [f for f in face_results if f["status"] == "recognized"]
    unknown = [f for f in face_results if f["status"] == "unknown"]

    # Identify absent students (enrolled minus recognized)
    student_map = {s["id"]: s for s in all_students}
    enrolled_ids = set(student_map.keys())
    recognized_ids = {r["student_id"] for r in recognized if r.get("student_id")}
    absent_ids = enrolled_ids - recognized_ids

    absent_students = [
        {
            "face_index": None,
            "bbox": None,
            "student_id": student_map[sid]["id"],
            "name": student_map[sid]["name"],
            "roll_number": student_map[sid]["roll_number"],
            "class_name": student_map[sid]["class_name"],
            "status": "absent",
            "similarity": None,
        }
        for sid in sorted(
            absent_ids,
            key=lambda sid: (student_map[sid]["roll_number"], student_map[sid]["name"]),
        )
    ]

    # Persist the attendance session
    session_id = database.create_attendance_session(
        class_name=class_name,
        attendance_date=attendance_date,
        total_faces=len(face_results),
        recognized_count=len(recognized),
        unknown_count=len(unknown),
        photo_hash=payload.photo_hash,
    )

    # Persist attendance records for all enrolled students
    records_to_insert = []
    for r in recognized:
        records_to_insert.append(
            {
                "student_id": r["student_id"],
                "status": "present",
                "similarity": r.get("similarity"),
                "face_index": r.get("face_index"),
            }
        )
    for a in absent_students:
        records_to_insert.append(
            {
                "student_id": a["student_id"],
                "status": "absent",
                "similarity": None,
                "face_index": None,
            }
        )
    database.insert_attendance_records(session_id, records_to_insert)

    return {
        "session_id": session_id,
        "date": attendance_date,
        "class_name": class_name,
        "results": face_results + absent_students,
        "total_faces": len(face_results),
        "recognized_count": len(recognized),
        "unknown_count": len(unknown),
        "absent_count": len(absent_students),
    }


@router.get("/history")
async def get_attendance_history(class_name: str | None = Query(default=None)):
    """
    Return past attendance sessions, optionally filtered by class_name.
    """
    return database.get_attendance_history(class_name)


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: int):
    """
    Return full details and records for one attendance session.
    """
    detail = database.get_session_detail(session_id)
    if not detail:
        raise HTTPException(
            status_code=404, detail=f"Attendance session {session_id} not found"
        )
    return detail


@router.get("/export")
async def export_csv(
    session_id: int | None = Query(default=None),
    class_name: str | None = Query(default=None),
    attendance_date: str | None = Query(default=None),
):
    """
    Stream a CSV file from the database for an attendance session.
    Accepts either session_id, or class_name + attendance_date.
    Includes both Present and Absent students.
    """
    session_detail = None
    if session_id is not None:
        session_detail = database.get_session_detail(session_id)
    elif class_name and attendance_date:
        session_detail = database.get_session_by_class_and_date(
            class_name, attendance_date
        )

    if not session_detail:
        raise HTTPException(
            status_code=404, detail="Attendance session not found in database."
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Roll Number", "Class", "Date", "Status"])

    for r in session_detail["records"]:
        status_str = "Present" if r["status"] == "present" else "Absent"
        writer.writerow(
            [
                r["name"] or "Unknown",
                r["roll_number"] or "",
                r["class_name"] or session_detail["class_name"],
                session_detail["attendance_date"],
                status_str,
            ]
        )

    output.seek(0)
    filename = f"{session_detail['attendance_date']}_{session_detail['class_name']}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
