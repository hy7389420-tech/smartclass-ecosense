def create_class(client):
    department = client.post("/departments", json={"name": "Engineering"}).json()
    return client.post(
        "/classes",
        json={
            "department_id": department["id"],
            "name": "B.Tech",
            "section": "A",
            "year": 1,
        },
    ).json()


def test_student_crud(client):
    class_group = create_class(client)
    payload = {
        "student_code": "STUDENT_A",
        "roll_no": "1",
        "name": "Student A",
        "class_id": class_group["id"],
    }
    created = client.post("/students", json=payload)
    assert created.status_code == 201
    student_id = created.json()["id"]
    assert client.get(f"/students/{student_id}").json()["student_code"] == "STUDENT_A"
    assert client.get("/students").json()["total"] == 1

    payload["name"] = "Student A Updated"
    updated = client.put(f"/students/{student_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Student A Updated"

    assert client.delete(f"/students/{student_id}").status_code == 204


def test_student_code_must_be_unique_and_foreign_class_must_exist(client):
    class_group = create_class(client)
    payload = {
        "student_code": "STUDENT_A",
        "roll_no": "1",
        "name": "Student A",
        "class_id": class_group["id"],
    }
    assert client.post("/students", json=payload).status_code == 201

    duplicate = client.post(
        "/students",
        json={**payload, "roll_no": "2", "name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    missing_class = client.post(
        "/students",
        json={**payload, "student_code": "STUDENT_B", "class_id": 999},
    )
    assert missing_class.status_code == 409


def test_class_delete_is_guarded_when_a_student_references_it(client):
    department = client.post("/departments", json={"name": "Engineering"}).json()
    class_group = client.post(
        "/classes",
        json={
            "department_id": department["id"],
            "name": "B.Tech",
            "section": "A",
            "year": 1,
        },
    ).json()
    student_response = client.post(
        "/students",
        json={
            "student_code": "STUDENT_A",
            "roll_no": "1",
            "name": "Student A",
            "class_id": class_group["id"],
        },
    )
    assert student_response.status_code == 201

    blocked_delete = client.delete(f"/classes/{class_group['id']}")
    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["error"]["code"] == "CONFLICT"
