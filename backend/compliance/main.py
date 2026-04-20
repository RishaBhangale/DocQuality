"""
FastAPI Application Entry Point.

Configures and launches the complete document quality evaluation system
including FastAPI REST endpoints, Dash dashboard, CORS, logging, and
exception handling middleware.
"""

import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from a2wsgi import WSGIMiddleware

from compliance.config import settings
from compliance.database import init_db
from compliance.api.routes import router as api_router


# --- Logging Configuration ---

def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


# --- Application Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("=" * 60)
    logger.info("Document Quality Evaluation System - Starting")
    logger.info("=" * 60)

    # Initialize database
    init_db()
    logger.info("Database initialized.")

    # Ensure upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("Upload directory: %s", settings.UPLOAD_DIR)

    # Validate configuration
    warnings = settings.validate()
    for warning in warnings:
        logger.warning("CONFIG: %s", warning)

    # Log LLM configuration status
    if settings.FOUNDRY_API_KEY and settings.FOUNDRY_ENDPOINT:
        logger.info("LLM CONFIG: API Key = SET (%d chars), Endpoint = %s, Model = %s",
                     len(settings.FOUNDRY_API_KEY),
                     settings.FOUNDRY_ENDPOINT[:50] + "..." if len(settings.FOUNDRY_ENDPOINT) > 50 else settings.FOUNDRY_ENDPOINT,
                     settings.FOUNDRY_MODEL)
    else:
        logger.warning("LLM CONFIG: NOT CONFIGURED (API Key: %s, Endpoint: %s)",
                       "SET" if settings.FOUNDRY_API_KEY else "EMPTY",
                       "SET" if settings.FOUNDRY_ENDPOINT else "EMPTY")

    logger.info("Server ready at http://%s:%d", settings.APP_HOST, settings.APP_PORT)
    logger.info("API docs at http://%s:%d/docs", settings.APP_HOST, settings.APP_PORT)
    logger.info("Dash dashboard at http://%s:%d/dashboard/", settings.APP_HOST, settings.APP_PORT)
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Application shutting down.")


# --- FastAPI Application ---

app = FastAPI(
    title="Document Quality Evaluation System",
    description=(
        "AI-assisted document quality analysis using a hybrid architecture: "
        "Azure Foundry LLM for structured extraction + semantic reasoning, "
        "and a deterministic rule engine for reproducible scoring."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# --- CORS Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Exception Handling Middleware ---

@app.middleware("http")
async def exception_handling_middleware(request: Request, call_next):
    """Global exception handler middleware."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.exception("Unhandled exception: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all incoming requests."""
    logger.info("Request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info(
        "Response: %s %s -> %d",
        request.method, request.url.path, response.status_code,
    )
    return response


# --- Register API Routes ---

app.include_router(api_router, prefix="/api")


# --- Mount Dash Application ---

try:
    from compliance.dash_app.dashboard import create_dash_app

    dash_app = create_dash_app()
    app.mount("/dashboard", WSGIMiddleware(dash_app.server))
    logger.info("Dash dashboard mounted at /dashboard/")
except Exception as e:
    logger.warning("Failed to mount Dash dashboard: %s", str(e))


# --- Root Endpoint ---

@app.get("/", tags=["System"])
async def root():
    """Root endpoint with system information."""
    return {
        "name": "Document Quality Evaluation System",
        "version": "1.0.0",
        "api_docs": "/docs",
        "dashboard": "/dashboard/",
        "health": "/api/health",
    }


# --- Run with Uvicorn ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
