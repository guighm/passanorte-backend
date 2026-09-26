"""Corpo de erro padronizado e handlers globais (D-12, Princípio II).

Todo erro da API retorna: {"error": {"code", "message", "details"}} com o
header X-Request-Id propagado. Nenhum stack trace ou detalhe interno é
exposto ao cliente.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from shared.logging import get_request_id


class ApiError(Exception):
    """Erro de domínio com corpo padronizado."""

    def __init__(self, code: str, message: str, status_code: int, details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def _response(status_code: int, body: dict) -> JSONResponse:
    request_id = get_request_id()
    headers = {"X-Request-Id": request_id} if request_id else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _response(exc.status_code, exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "error": {
                    "code": "validation_error",
                    "message": "Payload inválido.",
                    "details": {"fields": [e for e in exc.errors() if "url" not in e]},
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Falha interna nunca vaza detalhes ao cliente (Princípio III).
        return _response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"error": {"code": "internal_error", "message": "Erro interno.", "details": {}}},
        )
