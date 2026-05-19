"""
routers/students.py — Enrol and manage students. All operations are scoped to
the authenticated user; one teacher's roster is invisible to another.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

import database
from auth.dependencies import get_current_user
from services.face_service import encode_single_face, invalidate_cache

router = APIRouter(prefix="/api/students", tags=["students"])


@router.post("/enroll")
async def enroll_student(
    name: str = Form(...),
    roll_number: str = Form(...),
    class_name: str = Form(...),
    photo: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    image_bytes = await photo.read()
    recognizer_name = user["preferred_recognizer"]
    try:
        embedding, _ = encode_single_face(image_bytes, recognizer_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        student_id = database.insert_student(
            user["id"], name.strip(), roll_number.strip(), class_name.strip(),
            embedding, recognizer_name,
        )
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409,
                                detail=f"Roll number '{roll_number}' is already enrolled.")
        logger.error(f"DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database error during enrollment.")

    invalidate_cache(user["id"], recognizer_name)
    return {
        "id": student_id, "name": name, "roll_number": roll_number,
        "class_name": class_name, "recognizer_name": recognizer_name,
    }


@router.get("")
async def list_students(class_name: str | None = None,
                        user: dict = Depends(get_current_user)):
    students = database.get_user_students(user["id"], class_name)
    return {"students": students, "count": len(students)}


@router.delete("/{student_id}")
async def remove_student(student_id: int,
                         user: dict = Depends(get_current_user)):
    deleted = database.delete_student(user["id"], student_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Student with id={student_id} not found.")
    invalidate_cache(user["id"])
    return {"message": f"Student {student_id} deleted successfully."}
