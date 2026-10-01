"""Consistent JSON error envelopes and FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from api.middleware import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "Something went wrong."

_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def get_request_id(request: Request) -> str:
    """Read request ID from middleware state, or fall back to header/unknown."""
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    header_value = request.headers.get(REQUEST_ID_HEADER)
    if header_value:
        return header_value
    return "unknown"


def error_code_for_status(status_code: int) -> str:
    """Map HTTP status to a stable machine-readable error code."""
    return _STATUS_CODE_MAP.get(status_code, "HTTP_ERROR")


def _detail_to_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        # FastAPI validation-style list; keep message client-safe and stable.
        return "Request validation failed."
    return INTERNAL_ERROR_MESSAGE


def error_envelope(
    *,
    code: str,
    message: str,
    request_id: str,
) -> dict[str, Any]:
    """Build the standard API error body."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException into the standard error envelope."""
    request_id = get_request_id(request)
    status_code = exc.status_code
    code = error_code_for_status(status_code)
    # Keep auth/config messages for expected HTTPException; never leak internals
    # for unexpected 5xx raised as HTTPException with non-string detail.
    if status_code >= 500 and not isinstance(exc.detail, str):
        message = INTERNAL_ERROR_MESSAGE
        code = "INTERNAL_ERROR"
    else:
        message = _detail_to_message(exc.detail)

    headers = dict(exc.headers) if exc.headers else {}
    headers.setdefault(REQUEST_ID_HEADER, request_id)

    return JSONResponse(
        status_code=status_code,
        content=error_envelope(code=code, message=message, request_id=request_id),
        headers=headers,
    )


def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Convert Pydantic/FastAPI validation errors into a safe 422 envelope."""
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=422,
        content=error_envelope(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=request_id,
        ),
        headers={REQUEST_ID_HEADER: request_id},
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors with request_id; return a controlled 500 body."""
    request_id = get_request_id(request)
    # Do not log Authorization headers or full request bodies.
    logger.error(
        "Unhandled exception request_id=%s path=%s method=%s",
        request_id,
        request.url.path,
        request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            code="INTERNAL_ERROR",
            message=INTERNAL_ERROR_MESSAGE,
            request_id=request_id,
        ),
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_exception_handlers(app) -> None:
    """Attach application exception handlers to the FastAPI app."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
