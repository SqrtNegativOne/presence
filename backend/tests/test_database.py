import numpy as np
import psycopg
import pytest

import database


def test_insert_and_get_student(tmp_db, dummy_embedding):
    student_id = database.insert_student(
        name="Alice Smith",
        roll_number="CS101",
        class_name="10-A",
        embedding=dummy_embedding,
        model_type="insightface",
    )
    assert student_id > 0

    # get_all_students should list without embedding
    students = database.get_all_students()
    assert len(students) == 1
    assert students[0]["name"] == "Alice Smith"
    assert students[0]["roll_number"] == "CS101"
    assert students[0]["model_type"] == "insightface"
    assert "face_embedding" not in students[0]

    # get_all_students_with_embeddings should return numpy array
    students_with_emb = database.get_all_students_with_embeddings(
        "10-A", model_type="insightface"
    )
    assert len(students_with_emb) == 1
    emb = students_with_emb[0]["face_embedding"]
    assert isinstance(emb, np.ndarray)
    assert emb.dtype == np.float32
    assert emb.shape == (512,)
    assert np.allclose(emb, dummy_embedding)


def test_insert_duplicate_roll_number(tmp_db, dummy_embedding):
    database.insert_student("Alice", "CS101", "10-A", dummy_embedding)
    with pytest.raises(psycopg.IntegrityError):
        database.insert_student("Bob", "CS101", "10-A", dummy_embedding)


def test_delete_student(tmp_db, dummy_embedding):
    sid = database.insert_student("Alice", "CS101", "10-A", dummy_embedding)
    assert database.delete_student(sid) is True
    assert database.delete_student(sid) is False


def test_insert_faceapi_embedding_128(tmp_db, dummy_embedding_128):
    sid = database.insert_student(
        name="Charlie Brown",
        roll_number="CS103",
        class_name="10-B",
        embedding=dummy_embedding_128,
        model_type="faceapi",
    )
    assert sid > 0

    students = database.get_all_students_with_embeddings("10-B", model_type="faceapi")
    assert len(students) == 1
    assert students[0]["model_type"] == "faceapi"
    assert students[0]["face_embedding"].shape == (128,)
    assert np.allclose(students[0]["face_embedding"], dummy_embedding_128)


def test_attendance_session_and_records(tmp_db, dummy_embedding):
    sid1 = database.insert_student("Alice", "CS101", "10-A", dummy_embedding)
    sid2 = database.insert_student("Bob", "CS102", "10-A", dummy_embedding)

    session_id = database.create_attendance_session(
        class_name="10-A",
        attendance_date="2026-03-05",
        total_faces=1,
        recognized_count=1,
        unknown_count=0,
        photo_hash="abc123hash",
    )
    assert session_id > 0

    records = [
        {"student_id": sid1, "status": "present", "similarity": 0.88, "face_index": 1},
        {
            "student_id": sid2,
            "status": "absent",
            "similarity": None,
            "face_index": None,
        },
    ]
    database.insert_attendance_records(session_id, records)

    # History
    history = database.get_attendance_history("10-A")
    assert len(history) == 1
    assert history[0]["id"] == session_id
    assert history[0]["class_name"] == "10-A"
    assert history[0]["recognized_count"] == 1

    # Session detail
    detail = database.get_session_detail(session_id)
    assert detail is not None
    assert detail["id"] == session_id
    assert len(detail["records"]) == 2

    present_rec = next(r for r in detail["records"] if r["student_id"] == sid1)
    absent_rec = next(r for r in detail["records"] if r["student_id"] == sid2)

    assert present_rec["name"] == "Alice"
    assert present_rec["status"] == "present"
    assert present_rec["similarity"] == 0.88
    assert present_rec["face_index"] == 1

    assert absent_rec["name"] == "Bob"
    assert absent_rec["status"] == "absent"
    assert absent_rec["similarity"] is None
    assert absent_rec["face_index"] is None

    # Helper by class and date
    by_class_date = database.get_session_by_class_and_date("10-A", "2026-03-05")
    assert by_class_date is not None
    assert by_class_date["id"] == session_id
