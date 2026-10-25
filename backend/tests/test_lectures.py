def create_lecture_context(client):
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
    classroom = client.post(
        "/classrooms",
        json={"name": "Room 101", "capacity": 60},
    ).json()
    return class_group["id"], classroom["id"]


def lecture_payload(class_id, classroom_id, start, end):
    return {
        "classroom_id": classroom_id,
        "class_id": class_id,
        "subject": "Physics",
        "start_time": start,
        "end_time": end,
    }


def test_lecture_crud_converts_timestamps_to_utc(client):
    class_id, classroom_id = create_lecture_context(client)
    payload = lecture_payload(
        class_id,
        classroom_id,
        "2030-01-01T10:00:00",
        "2030-01-01T11:00:00",
    )
    created = client.post("/lectures", json=payload)
    assert created.status_code == 201
    lecture_id = created.json()["id"]
    assert created.json()["start_time"] == "2030-01-01T04:30:00Z"
    assert client.get(f"/lectures/{lecture_id}").status_code == 200
    assert client.get("/lectures").json()["total"] == 1

    payload["subject"] = "Updated Physics"
    updated = client.put(f"/lectures/{lecture_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["subject"] == "Updated Physics"

    assert client.delete(f"/lectures/{lecture_id}").status_code == 204


def test_lecture_rejects_invalid_time_order(client):
    class_id, classroom_id = create_lecture_context(client)
    response = client.post(
        "/lectures",
        json=lecture_payload(
            class_id,
            classroom_id,
            "2030-01-01T11:00:00Z",
            "2030-01-01T10:00:00Z",
        ),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_lifecycle_status_is_changed_only_through_lifecycle_endpoints(client):
    class_id, classroom_id = create_lecture_context(client)
    payload = lecture_payload(
        class_id,
        classroom_id,
        "2030-01-01T10:00:00Z",
        "2030-01-01T11:00:00Z",
    )
    invalid_create = client.post("/lectures", json={**payload, "status": "live"})
    assert invalid_create.status_code == 422
    assert invalid_create.json()["error"]["code"] == "INVALID_INITIAL_LECTURE_STATUS"

    created = client.post("/lectures", json=payload).json()
    invalid_update = client.put(
        f"/lectures/{created['id']}",
        json={**payload, "status": "completed"},
    )
    assert invalid_update.status_code == 409
    assert invalid_update.json()["error"]["code"] == "USE_LECTURE_LIFECYCLE"


def test_lecture_rejects_overlapping_times_and_update_conflicts(client):
    class_id, classroom_id = create_lecture_context(client)
    first = client.post(
        "/lectures",
        json=lecture_payload(
            class_id,
            classroom_id,
            "2030-01-01T10:00:00Z",
            "2030-01-01T11:00:00Z",
        ),
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    overlapping = client.post(
        "/lectures",
        json=lecture_payload(
            class_id,
            classroom_id,
            "2030-01-01T10:30:00Z",
            "2030-01-01T11:30:00Z",
        ),
    )
    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "LECTURE_TIME_CONFLICT"

    second = client.post(
        "/lectures",
        json=lecture_payload(
            class_id,
            classroom_id,
            "2030-01-01T11:00:00Z",
            "2030-01-01T12:00:00Z",
        ),
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    update_conflict = client.put(
        f"/lectures/{second_id}",
        json=lecture_payload(
            class_id,
            classroom_id,
            "2030-01-01T10:45:00Z",
            "2030-01-01T11:45:00Z",
        ),
    )
    assert update_conflict.status_code == 409
    assert client.get(f"/lectures/{first_id}").status_code == 200
