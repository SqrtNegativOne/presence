from unittest.mock import patch


def test_enroll_student(client, dummy_embedding, dummy_image_bytes):
    with patch("routers.students.encode_single_face", return_value=dummy_embedding):
        response = client.post(
            "/api/students/enroll",
            data={"name": "Alice Smith", "roll_number": "CS101", "class_name": "10-A"},
            files={"photo": ("alice.jpg", dummy_image_bytes, "image/jpeg")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice Smith"
    assert data["roll_number"] == "CS101"
    assert data["class_name"] == "10-A"
    assert "id" in data


def test_enroll_duplicate_roll_number(client, dummy_embedding, dummy_image_bytes):
    with patch("routers.students.encode_single_face", return_value=dummy_embedding):
        res1 = client.post(
            "/api/students/enroll",
            data={"name": "Alice Smith", "roll_number": "CS101", "class_name": "10-A"},
            files={"photo": ("alice.jpg", dummy_image_bytes, "image/jpeg")},
        )
        assert res1.status_code == 200

        res2 = client.post(
            "/api/students/enroll",
            data={"name": "Alice Clone", "roll_number": "CS101", "class_name": "10-A"},
            files={"photo": ("alice2.jpg", dummy_image_bytes, "image/jpeg")},
        )
        assert res2.status_code == 409
        assert "already enrolled" in res2.json()["detail"]


def test_enroll_no_face(client, dummy_image_bytes):
    with patch(
        "routers.students.encode_single_face",
        side_effect=ValueError("No face detected in the enrollment photo."),
    ):
        response = client.post(
            "/api/students/enroll",
            data={"name": "Bob", "roll_number": "CS102", "class_name": "10-A"},
            files={"photo": ("bob.jpg", dummy_image_bytes, "image/jpeg")},
        )
    assert response.status_code == 400
    assert "No face detected" in response.json()["detail"]


def test_enroll_multiple_faces(client, dummy_image_bytes):
    with patch(
        "routers.students.encode_single_face",
        side_effect=ValueError(
            "2 faces detected. Enrollment photos must contain exactly one person."
        ),
    ):
        response = client.post(
            "/api/students/enroll",
            data={"name": "Bob", "roll_number": "CS102", "class_name": "10-A"},
            files={"photo": ("bob.jpg", dummy_image_bytes, "image/jpeg")},
        )
    assert response.status_code == 400
    assert (
        "Enrollment photos must contain exactly one person" in response.json()["detail"]
    )


def test_list_students_by_class(client, dummy_embedding, dummy_image_bytes):
    with patch("routers.students.encode_single_face", return_value=dummy_embedding):
        client.post(
            "/api/students/enroll",
            data={"name": "Alice", "roll_number": "CS101", "class_name": "10-A"},
            files={"photo": ("a.jpg", dummy_image_bytes, "image/jpeg")},
        )
        client.post(
            "/api/students/enroll",
            data={"name": "Bob", "roll_number": "CS102", "class_name": "10-B"},
            files={"photo": ("b.jpg", dummy_image_bytes, "image/jpeg")},
        )

    # Filter by 10-A
    res_a = client.get("/api/students?class_name=10-A")
    assert res_a.status_code == 200
    assert res_a.json()["count"] == 1
    assert res_a.json()["students"][0]["name"] == "Alice"

    # List all
    res_all = client.get("/api/students")
    assert res_all.status_code == 200
    assert res_all.json()["count"] == 2


def test_delete_student(client, dummy_embedding, dummy_image_bytes):
    with patch("routers.students.encode_single_face", return_value=dummy_embedding):
        res = client.post(
            "/api/students/enroll",
            data={"name": "Alice", "roll_number": "CS101", "class_name": "10-A"},
            files={"photo": ("a.jpg", dummy_image_bytes, "image/jpeg")},
        )
    student_id = res.json()["id"]

    del_res = client.delete(f"/api/students/{student_id}")
    assert del_res.status_code == 200

    del_res2 = client.delete(f"/api/students/{student_id}")
    assert del_res2.status_code == 404


def test_enroll_student_embedding(client, dummy_embedding_128):
    res = client.post(
        "/api/students/enroll-embedding",
        json={
            "name": "David",
            "roll_number": "CS104",
            "class_name": "10-A",
            "embedding": dummy_embedding_128.tolist(),
            "model_type": "faceapi",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "David"
    assert data["roll_number"] == "CS104"
    assert data["model_type"] == "faceapi"
    assert "id" in data


def test_enroll_student_embedding_duplicate(client, dummy_embedding_128):
    client.post(
        "/api/students/enroll-embedding",
        json={
            "name": "David",
            "roll_number": "CS104",
            "class_name": "10-A",
            "embedding": dummy_embedding_128.tolist(),
            "model_type": "faceapi",
        },
    )
    res = client.post(
        "/api/students/enroll-embedding",
        json={
            "name": "David Clone",
            "roll_number": "CS104",
            "class_name": "10-A",
            "embedding": dummy_embedding_128.tolist(),
            "model_type": "faceapi",
        },
    )
    assert res.status_code == 409
