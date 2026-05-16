"""FastAPI application entry point.

Owns the application factory, lifespan and the wiring of:
  - settings (loaded eagerly so a misconfigured env fails fast)
  - logging
  - exception handlers
  - CORS
  - routers
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("Starting %s", settings.app_name)
    yield
    log.info("Stopping %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG · Historia de Colombia — API",
        description=(
            "REST API for the LangGraph-powered agent that answers questions about "
            "Colombian history grounded in user-uploaded documents."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)

    return app


app = create_app()
