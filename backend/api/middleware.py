"""Request-ID middleware for correlating API responses and logs."""

from __future__ import annotations

import re
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128

# Non-empty printable ASCII without whitespace/control; UUID-like and similar tokens.
_SAFE_REQUEST_ID = re.compile(r"^[!-~]{1,%d}$" % MAX_REQUEST_ID_LENGTH)


def is_valid_request_id(value: str | None) -> bool:
    """Return True if value is a safe client-supplied request ID."""
    if not value:
        return False
    if len(value) > MAX_REQUEST_ID_LENGTH:
        return False
    return _SAFE_REQUEST_ID.fullmatch(value) is not None


def resolve_request_id(incoming: str | None) -> str:
    """Accept a valid incoming request ID or generate a new UUID4."""
    if is_valid_request_id(incoming):
        return incoming  # type: ignore[return-value]
    return str(uuid.uuid4())


class RequestIdMiddleware:
    """Validate/generate X-Request-ID, store on request.state, echo on response.

    Pure ASGI middleware (not BaseHTTPMiddleware) so exception handlers can
    return controlled responses without being re-raised by the middleware stack.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)
        request_id = resolve_request_id(headers.get(REQUEST_ID_HEADER))

        # Ensure request.state exists for FastAPI/Starlette Request.
        state = scope.setdefault("state", {})
        if not isinstance(state, dict):
            # Starlette may use a State object; set attribute when possible.
            setattr(state, "request_id", request_id)
        else:
            state["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_request_id)
