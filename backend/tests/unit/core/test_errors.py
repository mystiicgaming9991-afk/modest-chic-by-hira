"""Unit tests for application error response contract."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from modest_chic_backend.core.errors import ApplicationError


def test_application_error_produces_correct_body() -> None:
    """An ApplicationError produces the standard error envelope."""
    error = ApplicationError(422, "VALIDATION_FAILED", "Field x is required.")
    assert error.status_code == 422
    assert error.code == "VALIDATION_FAILED"
    assert error.message == "Field x is required."


async def test_error_handler_returns_json_response() -> None:
    """The FastAPI exception handler returns the correct JSON body."""
    app = FastAPI()

    @app.exception_handler(ApplicationError)
    async def handler(request: Request, error: ApplicationError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @app.get("/test-error")
    async def raise_error() -> None:
        raise ApplicationError(409, "VERSION_CONFLICT", "Setting was modified.")

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/test-error")
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "VERSION_CONFLICT"
    assert body["message"] == "Setting was modified."


def test_error_codes_follow_convention() -> None:
    """Error codes use UPPER_SNAKE_CASE as specified in the shared conventions."""
    errors = [
        ApplicationError(400, "INVALID_SETTING", "Bad setting"),
        ApplicationError(401, "UNAUTHORIZED", "Auth required"),
        ApplicationError(403, "FORBIDDEN", "Permission required"),
        ApplicationError(404, "SETTING_NOT_FOUND", "Not found"),
        ApplicationError(409, "SETTING_VERSION_CONFLICT", "Conflict"),
        ApplicationError(429, "RATE_LIMITED", "Too many"),
    ]
    for error in errors:
        assert error.code.isupper() or "_" in error.code
        assert " " not in error.code
        assert error.code.isascii()
