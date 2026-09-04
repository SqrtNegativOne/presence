"""
routers/students.py — Endpoints for enrolling and managing students.

FastAPI routers are mini-applications that group related endpoints.
They're registered in main.py with app.include_router(...).
"""

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel, Field

import database
from services.face_service import encode_single_face

router = APIRouter(prefix="/api/students", tags=["students"])


class EnrollEmbeddingRequest(BaseModel):
    name: str
    roll_number: str
    class_name: str
    embedding: list[float]
    model_type: str = Field(default="faceapi")


@router.post("/enroll")
async def enroll_student(
    name: str = Form(...),  # Form(...) means required form field
    roll_number: str = Form(...),
    class_name: str = Form(...),
    photo: UploadFile = File(...),  # uploaded image file
):
    """
    Enroll a new student by uploading their solo portrait.

    Steps:
    1. Read the uploaded image bytes
    2. Detect the single face and compute its 512-d embedding
    3. Store name/roll/class + embedding in database
    """
    image_bytes = await photo.read()

    try:
        embedding = encode_single_face(image_bytes)
    except ValueError as e:
        # This catches "no face" or "multiple faces" errors from face_service
        raise HTTPException(status_code=400, detail=str(e))

    try:
        student_id = database.insert_student(
            name.strip(),
            roll_number.strip(),
            class_name.strip(),
            embedding,
            model_type="insightface",
        )
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            raise HTTPException(
                status_code=409,
                detail=f"Roll number '{roll_number}' is already enrolled.",
            )
        logger.error(f"DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database error during enrollment.")

    return {
        "id": student_id,
        "name": name,
        "roll_number": roll_number,
        "class_name": class_name,
        "model_type": "insightface",
    }


@router.post("/enroll-embedding")
async def enroll_student_embedding(payload: EnrollEmbeddingRequest):
    """
    Enroll a student using a pre-computed face embedding (e.g. from face-api.js in the browser).
    """
    name = payload.name.strip()
    roll_number = payload.roll_number.strip()
    class_name = payload.class_name.strip()
    model_type = payload.model_type.strip() or "faceapi"

    if not name or not roll_number or not class_name:
        raise HTTPException(
            status_code=400, detail="Name, roll number, and class name are required."
        )

    if not payload.embedding or len(payload.embedding) == 0:
        raise HTTPException(status_code=400, detail="Embedding cannot be empty.")

    embedding = np.array(payload.embedding, dtype=np.float32)

    try:
        student_id = database.insert_student(
            name=name,
            roll_number=roll_number,
            class_name=class_name,
            embedding=embedding,
            model_type=model_type,
        )
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            raise HTTPException(
                status_code=409,
                detail=f"Roll number '{roll_number}' is already enrolled.",
            )
        logger.error(f"DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Database error during enrollment.")

    return {
        "id": student_id,
        "name": name,
        "roll_number": roll_number,
        "class_name": class_name,
        "model_type": model_type,
    }


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
        raise HTTPException(
            status_code=404, detail=f"Student with id={student_id} not found."
        )
    return {"message": f"Student {student_id} deleted successfully."}
