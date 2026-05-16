"""Domain exceptions and FastAPI handlers.

Every error the application raises on purpose inherits from `AppError`. Handlers
registered in `app.main` translate these into a uniform JSON shape:

    {
      "code": "DOCUMENT_NOT_FOUND",
      "message": "Document <uuid> does not exist.",
      "details": {...}
    }

Keeping the hierarchy here (instead of sprinkled across modules) gives one place
to audit error codes when writing the frontend or the documento técnico.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Base hierarchy
# ──────────────────────────────────────────────────────────────


class AppError(Exception):
    """Base for all expected, user-facing errors.

    Subclasses set `code` and `status_code` as class attributes; the constructor
    accepts an optional message override and an arbitrary `details` mapping.
    """

    code: str = "APP_ERROR"
    status_code: int = status.HTTP_400_BAD_REQUEST
    message: str = "Application error."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


# ── Authentication / authorisation ────────────────────────────


class InvalidJWT(AppError):
    code = "INVALID_JWT"
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "The provided authentication token is invalid or expired."


class Forbidden(AppError):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN
    message = "You do not have permission to perform this action."


# ── Documents / ingestion ─────────────────────────────────────


class DocumentNotFound(AppError):
    code = "DOCUMENT_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "The requested document does not exist."


class UnsupportedFileType(AppError):
    code = "UNSUPPORTED_FILE_TYPE"
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    message = "This file type is not supported."


class DocumentProcessingError(AppError):
    code = "DOCUMENT_PROCESSING_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "The document could not be processed."


# ── Embeddings / LLM ──────────────────────────────────────────


class EmbeddingError(AppError):
    code = "EMBEDDING_ERROR"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "Failed to generate embeddings."


class LLMUnavailable(AppError):
    code = "LLM_UNAVAILABLE"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "The language model is currently unavailable."


# ── RAG agent ─────────────────────────────────────────────────


class InsufficientContext(AppError):
    """Raised when the agent cannot find grounded context to answer.

    This is *not* an error from the user's perspective — the frontend treats it
    as a regular response with `grounded=false`. We model it as an exception
    only when surfaced outside the graph (e.g. forced via API in the future).
    """

    code = "INSUFFICIENT_CONTEXT"
    status_code = status.HTTP_200_OK
    message = "No tengo suficiente información en mi base de conocimiento para responder esa pregunta."


# ──────────────────────────────────────────────────────────────
# FastAPI handlers
# ──────────────────────────────────────────────────────────────


def _error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}}


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    log.info("AppError raised: code=%s status=%s", exc.code, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.code, exc.message, exc.details),
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            "VALIDATION_ERROR",
            "Request payload did not match the expected schema.",
            {"errors": exc.errors()},
        ),
    )


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire all handlers above into a FastAPI instance.

    Called from `app.main` during application setup.
    """
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
