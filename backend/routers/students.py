"""
routers/students.py — Endpoints for enrolling and managing students.

FastAPI routers are mini-applications that group related endpoints.
They're registered in main.py with app.include_router(...).
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

import database
from services.face_service import encode_single_face

router = APIRouter(prefix="/api/students", tags=["students"])


@router.post("/enroll")
async def enroll_student(
    name: str = Form(...),          # Form(...) means required form field
    roll_number: str = Form(...),
    class_name: str = Form(...),
    photo: UploadFile = File(...),  # uploaded image file
):
    """
    Enroll a new student by uploading their solo portrait.

    Steps:
    1. Read the uploaded image bytes
    2. Detect the single face and compute its 512-d embedding
    3. Store name/roll/class + embedding in SQLite
    """
    image_bytes = await photo.read()

    try:
        embedding = encode_single_face(image_bytes)
    except ValueError as e:
        # This catches "no face" or "multiple faces" errors from face_service
        raise HTTPException(status_code=400, detail=str(e))

    try:
        student_id = database.insert_student(name.strip(), roll_number.strip(), class_name.strip(), embedding)
    except Exception as e:
        # The most likely error here is a UNIQUE constraint violation on roll_number
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"Roll number '{roll_number}' is already enrolled.")
        logger.error(f"DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database error during enrollment.")

    return {"id": student_id, "name": name, "roll_number": roll_number, "class_name": class_name}


@router.get("")
async def list_students(class_name: str | None = None):
    """
    Return all students, optionally filtered by class_name query param.
    Example: GET /api/students?class_name=10-A
    """
    students = database.get_all_students(class_name)
    return {"students": students, "count": len(students)}


@router.delete("/{student_id}")
async def remove_student(student_id: int):
    """Delete a student by their database ID."""
    deleted = database.delete_student(student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Student with id={student_id} not found.")
    return {"message": f"Student {student_id} deleted successfully."}
