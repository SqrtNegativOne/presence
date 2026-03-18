"""
routers/students.py — Endpoints for enrolling and managing students.

FastAPI routers are mini-applications that group related endpoints.
They're registered in main.py with app.include_router(...).
"""

import csv
import io
import zipfile

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


@router.post("/bulk-enroll")
async def bulk_enroll_students(
    csv_file: UploadFile = File(...),
    photos_zip: UploadFile = File(...),
):
    """
    Enroll multiple students from a CSV file and a ZIP of their photos.

    CSV format (with header row):
        name,roll_number,class_name,photo
        Arjun Sharma,CS101,10-A,arjun.jpg

    The ZIP must contain all photos referenced in the CSV.
    Each row is processed independently — failures don't stop the rest.

    Returns a summary with per-row results.
    """
    csv_bytes = await csv_file.read()
    zip_bytes = await photos_zip.read()

    # Validate that the uploaded ZIP is actually a ZIP archive
    if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        raise HTTPException(status_code=400, detail="photos_zip is not a valid ZIP file.")

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    # Build a flat map of basename → bytes so photos can live in subdirectories
    zip_contents: dict[str, bytes] = {}
    for name in zf.namelist():
        if not name.endswith("/"):  # skip directory entries
            zip_contents[name.split("/")[-1]] = zf.read(name)

    # Parse CSV
    try:
        text = csv_bytes.decode("utf-8-sig")  # utf-8-sig strips Excel BOM if present
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    required_cols = {"name", "roll_number", "class_name", "photo"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have columns: {', '.join(sorted(required_cols))}. "
                   f"Found: {', '.join(reader.fieldnames or [])}",
        )

    results = []
    succeeded = 0
    failed = 0

    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is the header
        name = (row.get("name") or "").strip()
        roll = (row.get("roll_number") or "").strip()
        cls  = (row.get("class_name") or "").strip()
        photo_filename = (row.get("photo") or "").strip()

        def fail(reason: str):
            nonlocal failed
            failed += 1
            results.append({"row": i, "name": name, "roll_number": roll, "status": "error", "detail": reason})

        if not all([name, roll, cls, photo_filename]):
            fail("Missing required field(s) — name, roll_number, class_name and photo are all required.")
            continue

        photo_bytes = zip_contents.get(photo_filename)
        if photo_bytes is None:
            fail(f"Photo '{photo_filename}' not found in ZIP.")
            continue

        try:
            embedding = encode_single_face(photo_bytes)
        except ValueError as e:
            fail(str(e))
            continue

        try:
            student_id = database.insert_student(name, roll, cls, embedding)
        except Exception as e:
            if "UNIQUE" in str(e):
                fail(f"Roll number '{roll}' is already enrolled.")
            else:
                logger.error(f"DB insert failed for row {i}: {e}")
                fail("Database error during insertion.")
            continue

        succeeded += 1
        results.append({"row": i, "name": name, "roll_number": roll, "status": "ok", "id": student_id})

    logger.info(f"Bulk enroll complete: {succeeded} succeeded, {failed} failed out of {len(rows)} rows.")
    return {"total": len(rows), "succeeded": succeeded, "failed": failed, "results": results}
