from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import database
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_checks_database() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_safe_error_when_database_is_unavailable(
    monkeypatch,
) -> None:
    def fail_database_check() -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("connection failed"))

    monkeypatch.setattr(database, "check_database", fail_database_check)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database is unavailable.",
        }
    }
