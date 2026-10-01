"""Google ID-token authentication for protected FastAPI routes."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_google_id_token(token: str) -> dict[str, Any]:
    """Verify a Google ID token and return its claims.

    Raises:
        RuntimeError: if GOOGLE_CLIENT_ID is not configured.
        ValueError: if the token is invalid, expired, or has the wrong audience.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured")

    return id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        audience=client_id,
    )


def require_google_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency that requires a valid Google ID token."""
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return verify_google_id_token(credentials.credentials)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured.",
        ) from None
    except (ValueError, GoogleAuthError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
