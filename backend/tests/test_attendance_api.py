import csv
import io
from unittest.mock import patch
import pytest

import database


def test_process_attendance_no_students(client, dummy_image_bytes):
    response = client.post(
        "/api/attendance/process",
        data={"class_name": "NonExistentClass"},
        files={"photo": ("group.jpg", dummy_image_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "No students enrolled yet" in response.json()["detail"]


def test_process_attendance_persistence_and_absences(client, dummy_embedding, dummy_image_bytes):
    # Enroll Alice and Bob
    sid_alice = database.insert_student("Alice", "CS101", "10-A", dummy_embedding)
    sid_bob = database.insert_student("Bob", "CS102", "10-A", dummy_embedding)

    mock_face_results = [
        {
            "face_index": 1,
            "bbox": [10, 10, 50, 50],
            "student_id": sid_alice,
            "name": "Alice",
            "roll_number": "CS101",
            "class_name": "10-A",
            "status": "recognized",
            "similarity": 0.85,
        }
    ]

    with patch("routers.attendance.match_group_photo", return_value=mock_face_results), \
         patch("routers.attendance.annotate_image", return_value="dummy_base64"):
        response = client.post(
            "/api/attendance/process",
            data={"class_name": "10-A", "attendance_date": "2026-03-05"},
            files={"photo": ("group.jpg", dummy_image_bytes, "image/jpeg")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    session_id = data["session_id"]
    assert data["class_name"] == "10-A"
    assert data["date"] == "2026-03-05"
    assert data["total_faces"] == 1
    assert data["recognized_count"] == 1
    assert data["unknown_count"] == 0
    assert data["absent_count"] == 1

    # Verify results list includes both present and absent students
    results = data["results"]
    assert len(results) == 2
    present_item = next(r for r in results if r["student_id"] == sid_alice)
    absent_item = next(r for r in results if r["student_id"] == sid_bob)
    assert present_item["status"] == "recognized"
    assert absent_item["status"] == "absent"
    assert absent_item["face_index"] is None

    # Verify session detail endpoint
    session_res = client.get(f"/api/attendance/sessions/{session_id}")
    assert session_res.status_code == 200
    session_data = session_res.json()
    assert session_data["id"] == session_id
    assert len(session_data["records"]) == 2

    # Verify history endpoint
    history_res = client.get("/api/attendance/history?class_name=10-A")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    assert history[0]["id"] == session_id

    # Verify CSV export
    export_res = client.get(f"/api/attendance/export?session_id={session_id}")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]

    csv_text = export_res.text
    reader = list(csv.reader(io.StringIO(csv_text)))
    assert reader[0] == ["Name", "Roll Number", "Class", "Date", "Status"]
    rows = reader[1:]
    assert len(rows) == 2

    alice_row = next(r for r in rows if r[0] == "Alice")
    bob_row = next(r for r in rows if r[0] == "Bob")

    assert alice_row == ["Alice", "CS101", "10-A", "2026-03-05", "Present"]
    assert bob_row == ["Bob", "CS102", "10-A", "2026-03-05", "Absent"]


def test_export_by_class_and_date(client, dummy_embedding, dummy_image_bytes):
    sid = database.insert_student("Charlie", "CS103", "10-B", dummy_embedding)
    session_id = database.create_attendance_session(
        class_name="10-B",
        attendance_date="2026-03-05",
        total_faces=1,
        recognized_count=1,
        unknown_count=0,
    )
    database.insert_attendance_records(
        session_id,
        [{"student_id": sid, "status": "present", "similarity": 0.9, "face_index": 1}],
    )

    export_res = client.get("/api/attendance/export?class_name=10-B&attendance_date=2026-03-05")
    assert export_res.status_code == 200
    assert "Charlie" in export_res.text


def test_export_not_found(client):
    res = client.get("/api/attendance/export?session_id=99999")
    assert res.status_code == 404
