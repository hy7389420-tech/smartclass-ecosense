def test_classroom_crud(client):
    created = client.post(
        "/classrooms",
        json={"name": "Room 101", "capacity": 60},
    )
    assert created.status_code == 201
    classroom_id = created.json()["id"]
    assert client.get(f"/classrooms/{classroom_id}").json()["capacity"] == 60
    assert client.get("/classrooms").json()["total"] == 1

    updated = client.put(
        f"/classrooms/{classroom_id}",
        json={"name": "Room 102", "capacity": 45},
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 45

    assert client.delete(f"/classrooms/{classroom_id}").status_code == 204


def test_classroom_requires_positive_capacity_and_unique_name(client):
    invalid = client.post(
        "/classrooms",
        json={"name": "Room 101", "capacity": 0},
    )
    assert invalid.status_code == 422

    payload = {"name": "Room 101", "capacity": 60}
    assert client.post("/classrooms", json=payload).status_code == 201
    duplicate = client.post("/classrooms", json=payload)
    assert duplicate.status_code == 409
