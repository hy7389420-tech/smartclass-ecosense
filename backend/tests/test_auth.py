from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import (
    ClassGroup,
    Classroom,
    Department,
    Faculty,
    FacultyClassAssignment,
    Lecture,
    Student,
    User,
)
from app.services.auth import create_access_token, hash_password, login_rate_limiter


@pytest.fixture
def scoped_accounts(session_factory: sessionmaker[Session]) -> dict[str, object]:
    password_hash = hash_password("student-test-password")
    with session_factory.begin() as session:
        department_a = Department(name="Engineering A")
        department_b = Department(name="Engineering B")
        session.add_all([department_a, department_b])
        session.flush()

        class_a = ClassGroup(
            department_id=department_a.id,
            name="Class A",
            section="A",
            year=1,
        )
        class_b = ClassGroup(
            department_id=department_b.id,
            name="Class B",
            section="B",
            year=1,
        )
        session.add_all([class_a, class_b])
        session.flush()

        student_a = Student(
            student_code="A-001",
            roll_no="1",
            name="Student A",
            class_id=class_a.id,
        )
        student_b = Student(
            student_code="B-001",
            roll_no="1",
            name="Student B",
            class_id=class_b.id,
        )
        session.add_all([student_a, student_b])
        session.flush()

        faculty_a_user = User(
            email="faculty-a@example.test",
            password_hash=password_hash,
            role="FACULTY",
            is_active=True,
        )
        faculty_b_user = User(
            email="faculty-b@example.test",
            password_hash=password_hash,
            role="FACULTY",
            is_active=True,
        )
        hod_user = User(
            email="hod-a@example.test",
            password_hash=password_hash,
            role="HOD",
            is_active=True,
        )
        student_a_user = User(
            email="student-a@example.test",
            password_hash=password_hash,
            role="STUDENT",
            student_id=student_a.id,
            is_active=True,
        )
        student_b_user = User(
            email="student-b@example.test",
            password_hash=password_hash,
            role="STUDENT",
            student_id=student_b.id,
            is_active=True,
        )
        unmapped_student_user = User(
            email="unmapped-student@example.test",
            password_hash=password_hash,
            role="STUDENT",
            is_active=True,
        )
        session.add_all(
            [
                faculty_a_user,
                faculty_b_user,
                hod_user,
                student_a_user,
                student_b_user,
                unmapped_student_user,
            ]
        )
        session.flush()

        faculty_a = Faculty(
            user_id=faculty_a_user.id,
            department_id=department_a.id,
        )
        faculty_b = Faculty(
            user_id=faculty_b_user.id,
            department_id=department_b.id,
        )
        hod_department = Faculty(
            user_id=hod_user.id,
            department_id=department_a.id,
        )
        session.add_all([faculty_a, faculty_b, hod_department])
        session.flush()

        session.add_all(
            [
                FacultyClassAssignment(faculty_id=faculty_a.id, class_id=class_a.id),
                FacultyClassAssignment(faculty_id=faculty_b.id, class_id=class_b.id),
            ]
        )

        classroom_a = Classroom(name="Room A", capacity=30)
        classroom_b = Classroom(name="Room B", capacity=30)
        session.add_all([classroom_a, classroom_b])
        session.flush()
        lecture_a = Lecture(
            classroom_id=classroom_a.id,
            class_id=class_a.id,
            subject="Math",
            faculty_id=faculty_a.id,
            start_time=datetime(2030, 1, 1, 9, tzinfo=UTC),
            end_time=datetime(2030, 1, 1, 10, tzinfo=UTC),
            status="scheduled",
        )
        lecture_b = Lecture(
            classroom_id=classroom_b.id,
            class_id=class_b.id,
            subject="Physics",
            faculty_id=faculty_b.id,
            start_time=datetime(2030, 1, 1, 10, tzinfo=UTC),
            end_time=datetime(2030, 1, 1, 11, tzinfo=UTC),
            status="scheduled",
        )
        session.add_all([lecture_a, lecture_b])
        session.flush()

        account_ids = {
            "faculty_a": faculty_a_user.id,
            "faculty_b": faculty_b_user.id,
            "hod": hod_user.id,
            "student_a": student_a_user.id,
            "student_b": student_b_user.id,
            "unmapped_student": unmapped_student_user.id,
            "student_a_record": student_a.id,
            "student_b_record": student_b.id,
            "class_a": class_a.id,
            "class_b": class_b.id,
            "department_a": department_a.id,
            "department_b": department_b.id,
            "lecture_a": lecture_a.id,
            "lecture_b": lecture_b.id,
        }
        return {
            **account_ids,
            "tokens": {
                name: create_access_token(session.get(User, user_id))
                for name, user_id in account_ids.items()
                if name
                in {
                    "faculty_a",
                    "faculty_b",
                    "hod",
                    "student_a",
                    "student_b",
                    "unmapped_student",
                }
            },
        }


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_access_token_and_me(client):
    response = client.post(
        "/auth/login",
        json={"email": "test-admin@example.test", "password": "test-admin-password"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"
    profile = client.get("/auth/me", headers=_auth_header(token))
    assert profile.status_code == 200
    assert profile.json()["role"] == "ADMIN"


def test_login_failure_is_generic_and_rate_limited(client):
    login_rate_limiter.clear("testclient")
    unknown = client.post(
        "/auth/login",
        json={"email": "unknown@example.test", "password": "wrong-password"},
    )
    incorrect = client.post(
        "/auth/login",
        json={"email": "test-admin@example.test", "password": "wrong-password"},
    )
    assert unknown.status_code == incorrect.status_code == 401
    assert unknown.json() == incorrect.json()
    for _ in range(3):
        client.post(
            "/auth/login",
            json={"email": "unknown@example.test", "password": "wrong-password"},
        )
    limited = client.post(
        "/auth/login",
        json={"email": "unknown@example.test", "password": "wrong-password"},
    )
    assert limited.status_code == 429


def test_missing_expired_and_tampered_tokens_are_rejected(client):
    unauthenticated = client.get("/auth/me", headers={"Authorization": ""})
    assert unauthenticated.status_code == 401

    user_id = client.get("/auth/me").json()["id"]
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "ver": 0,
        },
        get_settings().jwt_secret_key,
        algorithm="HS256",
    )
    expired = client.get("/auth/me", headers=_auth_header(expired_token))
    token_parts = expired_token.split(".")
    token_parts[2] = ("A" if token_parts[2][0] != "A" else "B") + token_parts[2][1:]
    tampered = client.get("/auth/me", headers=_auth_header(".".join(token_parts)))
    assert expired.status_code == tampered.status_code == 401


def test_all_user_data_routers_require_authentication(client):
    get_paths = [
        "/classes",
        "/classrooms",
        "/departments",
        "/students",
        "/students/1/presence-history",
        "/lectures",
        "/lectures/1",
        "/lectures/1/attendance",
        "/events",
        "/dashboard/1",
        "/analytics/outside-duration",
        "/analytics/lecture/1",
        "/analytics/classroom/1/utilization",
        "/insights/1",
        "/lectures/1/engagement",
        "/lectures/1/suggestions",
        "/lectures/1/suggestions/log",
        "/auth/me",
    ]
    for path in get_paths:
        response = client.get(path, headers={"Authorization": ""})
        assert response.status_code == 401, path

    activity = client.post(
        "/activity",
        headers={"Authorization": ""},
        json={
            "lecture_id": 1,
            "window_start": "2030-01-01T09:00:00Z",
            "window_end": "2030-01-01T09:00:10Z",
            "source": "simulated",
        },
    )
    assert activity.status_code == 401


def test_inactive_user_token_is_rejected(client, session_factory):
    with session_factory.begin() as session:
        user = User(
            email="inactive@example.test",
            password_hash=hash_password("inactive-account-password"),
            role="FACULTY",
            is_active=False,
        )
        session.add(user)
        session.flush()
        token = create_access_token(user)

    response = client.get("/auth/me", headers=_auth_header(token))
    assert response.status_code == 401


def test_change_password_revokes_existing_access_token(client):
    old_token = client.headers["Authorization"].removeprefix("Bearer ")
    changed = client.post(
        "/auth/change-password",
        headers=_auth_header(old_token),
        json={
            "current_password": "test-admin-password",
            "new_password": "new-test-admin-password",
        },
    )
    assert changed.status_code == 204
    assert client.get("/auth/me", headers=_auth_header(old_token)).status_code == 401

    new_login = client.post(
        "/auth/login",
        json={
            "email": "test-admin@example.test",
            "password": "new-test-admin-password",
        },
    )
    assert new_login.status_code == 200


def test_student_can_only_access_own_student_data(client, scoped_accounts):
    student_token = scoped_accounts["tokens"]["student_a"]
    own = client.get(
        f"/students/{scoped_accounts['student_a_record']}",
        headers=_auth_header(student_token),
    )
    other = client.get(
        f"/students/{scoped_accounts['student_b_record']}",
        headers=_auth_header(student_token),
    )
    listed = client.get("/students", headers=_auth_header(student_token))

    assert own.status_code == 200
    assert other.status_code == 403
    assert [item["id"] for item in listed.json()["items"]] == [
        scoped_accounts["student_a_record"]
    ]
    other_events = client.get(
        f"/events?student_id={scoped_accounts['student_b_record']}",
        headers=_auth_header(student_token),
    )
    assert other_events.status_code == 403


def test_unmapped_student_cannot_access_student_data(client, scoped_accounts):
    response = client.get(
        "/students",
        headers=_auth_header(scoped_accounts["tokens"]["unmapped_student"]),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "STUDENT_MAPPING_REQUIRED"


def test_faculty_is_limited_to_assigned_class_and_lecture(client, scoped_accounts):
    faculty_token = scoped_accounts["tokens"]["faculty_a"]
    assigned = client.get(
        f"/lectures/{scoped_accounts['lecture_a']}",
        headers=_auth_header(faculty_token),
    )
    unassigned = client.get(
        f"/lectures/{scoped_accounts['lecture_b']}",
        headers=_auth_header(faculty_token),
    )
    other_student = client.get(
        f"/students/{scoped_accounts['student_b_record']}",
        headers=_auth_header(faculty_token),
    )
    unassigned_events = client.get(
        f"/events?lecture_id={scoped_accounts['lecture_b']}",
        headers=_auth_header(faculty_token),
    )

    assert assigned.status_code == 200
    assert unassigned.status_code == 403
    assert other_student.status_code == 403
    assert unassigned_events.status_code == 403


def test_faculty_decision_log_is_authenticated_scoped_and_append_only(
    client, scoped_accounts
):
    lecture_id = scoped_accounts["lecture_a"]
    faculty_a = scoped_accounts["tokens"]["faculty_a"]
    faculty_b = scoped_accounts["tokens"]["faculty_b"]
    student = scoped_accounts["tokens"]["student_a"]

    generated = client.get(
        f"/lectures/{lecture_id}/suggestions",
        headers=_auth_header(faculty_a),
    )
    assert generated.status_code == 200
    suggestion_id = generated.json()[0]["id"]

    accepted = client.post(
        f"/suggestions/{suggestion_id}/decision",
        headers=_auth_header(faculty_a),
        json={"decision": "accepted", "note": "Will try next lecture."},
    )
    repeated = client.post(
        f"/suggestions/{suggestion_id}/decision",
        headers=_auth_header(faculty_a),
        json={"decision": "rejected"},
    )
    log = client.get(
        f"/lectures/{lecture_id}/suggestions/log",
        headers=_auth_header(faculty_a),
    )
    latest = client.get(
        f"/lectures/{lecture_id}/suggestions",
        headers=_auth_header(faculty_a),
    )
    outside_scope = client.post(
        f"/suggestions/{suggestion_id}/decision",
        headers=_auth_header(faculty_b),
        json={"decision": "ignored"},
    )
    student_decision = client.post(
        f"/suggestions/{suggestion_id}/decision",
        headers=_auth_header(student),
        json={"decision": "ignored"},
    )

    assert accepted.status_code == repeated.status_code == 201
    assert accepted.json()["decided_by"] == scoped_accounts["faculty_a"]
    assert accepted.json()["note"] == "Will try next lecture."
    assert len(log.json()) == 2
    assert [item["decision"] for item in log.json()] == ["accepted", "rejected"]
    assert latest.json()[0]["status"] == "rejected"
    assert outside_scope.status_code == 403
    assert student_decision.status_code == 403


def test_hod_is_limited_to_mapped_department(client, scoped_accounts):
    hod_token = scoped_accounts["tokens"]["hod"]
    own = client.get(
        f"/departments/{scoped_accounts['department_a']}",
        headers=_auth_header(hod_token),
    )
    other = client.get(
        f"/departments/{scoped_accounts['department_b']}",
        headers=_auth_header(hod_token),
    )
    own_class = client.get(
        f"/classes/{scoped_accounts['class_a']}",
        headers=_auth_header(hod_token),
    )
    other_class = client.get(
        f"/classes/{scoped_accounts['class_b']}",
        headers=_auth_header(hod_token),
    )
    assert own.status_code == 200
    assert other.status_code == 403
    assert own_class.status_code == 200
    assert other_class.status_code == 403


def test_student_cannot_access_aggregate_or_admin_routes(client, scoped_accounts):
    student_token = scoped_accounts["tokens"]["student_a"]
    paths = [
        "/departments",
        "/dashboard/1",
        "/analytics/lecture/1",
        "/insights/1",
        "/lectures/1/engagement",
        "/lectures/1/suggestions",
    ]
    for path in paths:
        response = client.get(path, headers=_auth_header(student_token))
        assert response.status_code == 403, path


def test_non_admin_roles_cannot_escalate_catalog_writes(client, scoped_accounts):
    payload = {
        "department_id": scoped_accounts["department_a"],
        "name": "Unauthorized class",
        "section": "X",
        "year": 1,
    }
    for role in ("faculty_a", "student_a"):
        response = client.post(
            "/classes",
            headers=_auth_header(scoped_accounts["tokens"][role]),
            json=payload,
        )
        assert response.status_code == 403, role
