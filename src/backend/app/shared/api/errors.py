from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.shared.domain.errors import (
    DomainError,
    Forbidden,
    InvalidCredentials,
    InvalidStateTransition,
    NotFound,
    TooManyAttempts,
)

_STATUS = [
    (InvalidCredentials, 401),
    (Forbidden, 403),
    (NotFound, 404),
    (InvalidStateTransition, 409),
    (TooManyAttempts, 429),
    (DomainError, 422),
]


def register_error_handlers(app: FastAPI) -> None:
    async def handle(_: Request, exc: Exception) -> JSONResponse:
        code = next(c for t, c in _STATUS if isinstance(exc, t))
        headers = ({"Retry-After": str(exc.retry_after_seconds)}
                   if isinstance(exc, TooManyAttempts) else None)
        return JSONResponse(status_code=code, content={"detail": str(exc), "code": type(exc).__name__},
                            headers=headers)

    app.add_exception_handler(DomainError, handle)
