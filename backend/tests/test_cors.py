"""CORS middleware: allowed vs disallowed origins and Authorization preflight."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import _cors_allowed_origins, add_cors_middleware


ALLOWED_ORIGIN = "http://localhost:3000"
DISALLOWED_ORIGIN = "https://evil.example"


def _app_with_cors(monkeypatch, origins: str | None) -> FastAPI:
    """Fresh FastAPI app with CORS bound from the given env value."""
    if origins is None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)

    app = FastAPI()

    @app.post("/chat")
    def chat():
        return {"ok": True}

    add_cors_middleware(app)
    return app


def test_cors_allowed_origins_parses_comma_separated_with_spaces(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " http://localhost:3000 , https://app.example.com ",
    )
    assert _cors_allowed_origins() == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_cors_allowed_origins_empty_or_unset_returns_empty(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert _cors_allowed_origins() == []

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "  ,  , ")
    assert _cors_allowed_origins() == []


def test_allowed_origin_preflight_includes_authorization(monkeypatch):
    client = TestClient(_app_with_cors(monkeypatch, ALLOWED_ORIGIN))

    response = client.options(
        "/chat",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers
    assert "x-request-id" in allow_headers
    allow_methods = response.headers.get("access-control-allow-methods", "").upper()
    assert "POST" in allow_methods
    assert "GET" in allow_methods


def test_allowed_origin_exposes_request_id_on_response(monkeypatch):
    client = TestClient(_app_with_cors(monkeypatch, ALLOWED_ORIGIN))

    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    expose = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in expose


def test_allowed_origin_get_preflight(monkeypatch):
    client = TestClient(_app_with_cors(monkeypatch, ALLOWED_ORIGIN))

    response = client.options(
        "/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    allow_methods = response.headers.get("access-control-allow-methods", "").upper()
    assert "GET" in allow_methods


def test_allowed_origin_post_includes_allow_origin(monkeypatch):
    client = TestClient(_app_with_cors(monkeypatch, ALLOWED_ORIGIN))

    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_disallowed_origin_has_no_allow_origin(monkeypatch):
    client = TestClient(_app_with_cors(monkeypatch, ALLOWED_ORIGIN))

    response = client.post(
        "/chat",
        json={"question": "What is Panadol used for?"},
        headers={"Origin": DISALLOWED_ORIGIN},
    )

    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin is None or allow_origin != DISALLOWED_ORIGIN
