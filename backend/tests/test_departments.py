def test_department_crud_and_pagination(client):
    created = client.post("/departments", json={"name": "Engineering"})
    assert created.status_code == 201
    department_id = created.json()["id"]

    read = client.get(f"/departments/{department_id}")
    assert read.status_code == 200
    assert read.json()["name"] == "Engineering"
    assert read.json()["created_at"].endswith(("Z", "+00:00"))

    listed = client.get("/departments?limit=1&offset=0")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert len(listed.json()["items"]) == 1

    updated = client.put(
        f"/departments/{department_id}",
        json={"name": "Electrical Engineering"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Electrical Engineering"

    deleted = client.delete(f"/departments/{department_id}")
    assert deleted.status_code == 204
    assert client.get(f"/departments/{department_id}").status_code == 404


def test_department_validation_and_duplicate_name_error_shape(client):
    invalid = client.post("/departments", json={"name": "   "})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    assert client.post("/departments", json={"name": "Engineering"}).status_code == 201
    duplicate = client.post("/departments", json={"name": "Engineering"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


def test_list_pagination_rejects_limit_above_maximum(client):
    response = client.get("/departments?limit=101")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
