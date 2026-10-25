import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.security import request_rate_limiter


def test_security_headers_are_attached_to_api_responses(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-permitted-cross-domain-policies"] == "none"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_explicit_origin_and_rejects_unlisted_origin(client):
    allowed = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    denied = client.get(
        "/health",
        headers={"Origin": "https://unlisted.example"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_cors_does_not_enable_wildcard_credentials(client):
    response = client.options(
        "/events",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-camera-key,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"


def test_oversized_body_is_rejected_before_route_processing(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_request_body_bytes", 1024)
    response = client.post(
        "/activity",
        content=b"x" * 1025,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_BODY_TOO_LARGE"


def test_global_auth_and_event_rate_limits_return_429(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "request_rate_limit_requests", 100)
    monkeypatch.setattr(settings, "auth_rate_limit_requests", 1)
    monkeypatch.setattr(settings, "event_rate_limit_requests", 1)

    assert client.get("/auth/me", headers={"Authorization": ""}).status_code == 401
    auth_limited = client.get("/auth/me", headers={"Authorization": ""})
    assert auth_limited.status_code == 429
    assert int(auth_limited.headers["retry-after"]) >= 1

    request_rate_limiter.clear("testclient")
    assert client.get("/events", headers={"Authorization": ""}).status_code == 401
    event_limited = client.get("/events", headers={"Authorization": ""})
    assert event_limited.status_code == 429
    assert event_limited.json()["error"]["code"] == "RATE_LIMITED"


def test_global_request_limit_is_enforced(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "request_rate_limit_requests", 1)
    assert client.get("/health").status_code == 200
    limited = client.get("/health")
    assert limited.status_code == 429


def test_http_errors_use_safe_common_envelope(client):
    response = client.get("/missing-route?token=must-not-be-returned")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "HTTP_ERROR", "message": "Resource was not found."}
    }


def test_unexpected_error_response_is_generic_and_logs_no_exception_detail(caplog):
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/explode")
    def explode():
        raise RuntimeError("sensitive internal diagnostic")

    caplog.set_level(logging.ERROR)
    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/explode")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal error occurred.",
        }
    }
    assert "sensitive internal diagnostic" not in caplog.text
    assert any(
        getattr(record, "error_type", None) == "RuntimeError"
        for record in caplog.records
    )
