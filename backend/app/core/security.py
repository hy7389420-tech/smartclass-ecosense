import json
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Any

from app.config import get_settings


class RequestRateLimiter:
    def __init__(self) -> None:
        self._requests: defaultdict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def consume(
        self, bucket: str, client_key: str, limit: int, window_seconds: int
    ) -> int | None:
        now = monotonic()
        key = (bucket, client_key)
        with self._lock:
            requests = self._requests[key]
            while requests and now - requests[0] >= window_seconds:
                requests.popleft()
            if len(requests) >= limit:
                return max(1, int(window_seconds - (now - requests[0])))
            requests.append(now)
            if len(self._requests) > 10_000:
                expired_keys = [
                    request_key
                    for request_key, entries in self._requests.items()
                    if not entries or now - entries[-1] >= window_seconds
                ]
                for expired_key in expired_keys:
                    self._requests.pop(expired_key, None)
        return None

    def clear(self, client_key: str | None = None) -> None:
        with self._lock:
            if client_key is None:
                self._requests.clear()
            else:
                for key in [key for key in self._requests if key[1] == client_key]:
                    self._requests.pop(key, None)


request_rate_limiter = RequestRateLimiter()


class RequestProtectionMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        client = scope.get("client")
        client_key = client[0] if client else "unknown"
        retry_after = self._consume_rate_limits(scope["path"], client_key, settings)
        if retry_after is not None:
            await self._send_error(
                send,
                429,
                "RATE_LIMITED",
                "Too many requests. Please try again later.",
                [(b"retry-after", str(retry_after).encode("ascii"))],
            )
            return

        declared_length = self._declared_content_length(scope)
        if declared_length == -1:
            await self._send_error(
                send,
                400,
                "INVALID_CONTENT_LENGTH",
                "Request content length is invalid.",
            )
            return
        if (
            declared_length is not None
            and declared_length > settings.max_request_body_bytes
        ):
            await self._send_error(
                send,
                413,
                "REQUEST_BODY_TOO_LARGE",
                "Request body exceeds the configured size limit.",
            )
            return

        try:
            messages = await self._read_request_body(
                receive, settings.max_request_body_bytes
            )
        except RequestBodyTooLarge:
            await self._send_error(
                send,
                413,
                "REQUEST_BODY_TOO_LARGE",
                "Request body exceeds the configured size limit.",
            )
            return

        message_index = 0

        async def replay_body() -> dict[str, Any]:
            nonlocal message_index
            if message_index >= len(messages):
                return {"type": "http.disconnect"}
            message = messages[message_index]
            message_index += 1
            return message

        async def add_security_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                security_headers = (
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"x-permitted-cross-domain-policies", b"none"),
                    (b"cache-control", b"no-store"),
                )
                headers.extend(
                    (name, value)
                    for name, value in security_headers
                    if name not in existing
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, replay_body, add_security_headers)

    @staticmethod
    def _consume_rate_limits(path: str, client_key: str, settings) -> int | None:
        retry_after = request_rate_limiter.consume(
            "global",
            client_key,
            settings.request_rate_limit_requests,
            settings.request_rate_limit_window_seconds,
        )
        if retry_after is not None:
            return retry_after

        if path == "/auth/login" or path.startswith("/auth/"):
            retry_after = request_rate_limiter.consume(
                "auth",
                client_key,
                settings.auth_rate_limit_requests,
                settings.request_rate_limit_window_seconds,
            )
        elif path == "/events" or path.startswith("/events/"):
            retry_after = request_rate_limiter.consume(
                "events",
                client_key,
                settings.event_rate_limit_requests,
                settings.request_rate_limit_window_seconds,
            )
        return retry_after

    @staticmethod
    def _declared_content_length(scope: dict[str, Any]) -> int | None:
        values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if not values:
            return None
        try:
            parsed = [int(value) for value in values]
        except ValueError:
            return -1
        if any(value < 0 for value in parsed) or len(set(parsed)) != 1:
            return -1
        return parsed[0]

    @staticmethod
    async def _read_request_body(
        receive: Any, maximum_bytes: int
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        total_bytes = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            total_bytes += len(message.get("body", b""))
            if total_bytes > maximum_bytes:
                raise RequestBodyTooLarge
            if not message.get("more_body", False):
                break
        return messages

    @staticmethod
    async def _send_error(
        send: Any,
        status_code: int,
        code: str,
        message: str,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(
            {"error": {"code": code, "message": message}},
            separators=(",", ":"),
        ).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"x-permitted-cross-domain-policies", b"none"),
            (b"cache-control", b"no-store"),
        ]
        headers.extend(extra_headers or [])
        await send(
            {"type": "http.response.start", "status": status_code, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body})


class RequestBodyTooLarge(Exception):
    pass
