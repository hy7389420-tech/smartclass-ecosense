def create_department(client):
    return client.post("/departments", json={"name": "Engineering"}).json()


def test_class_crud(client):
    department = create_department(client)
    payload = {
        "department_id": department["id"],
        "name": "B.Tech",
        "section": "A",
        "year": 1,
    }
    created = client.post("/classes", json=payload)
    assert created.status_code == 201
    class_id = created.json()["id"]
    assert client.get(f"/classes/{class_id}").json()["name"] == "B.Tech"
    assert client.get("/classes").json()["total"] == 1

    payload["name"] = "ECE"
    updated = client.put(f"/classes/{class_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "ECE"

    assert client.delete(f"/classes/{class_id}").status_code == 204


def test_class_validates_year_and_department_reference(client):
    department = create_department(client)
    invalid_year = client.post(
        "/classes",
        json={
            "department_id": department["id"],
            "name": "B.Tech",
            "section": "A",
            "year": 0,
        },
    )
    assert invalid_year.status_code == 422

    missing_department = client.post(
        "/classes",
        json={
            "department_id": 987,
            "name": "B.Tech",
            "section": "A",
            "year": 1,
        },
    )
    assert missing_department.status_code == 409
