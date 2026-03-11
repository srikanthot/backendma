"""FastAPI application entry point for the Technical Manuals Chatbot API.

This is the application factory — it creates and configures the FastAPI app,
sets up CORS, includes routes, and defines the health check endpoint.

Startup command for Azure App Service:
    gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.logging_config import configure_logging
from app.config.settings import ALLOWED_ORIGINS

# Configure logging before anything else
configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Technical Manuals Chatbot API",
    description=(
        "Backend-only chatbot API for technical manuals. "
        "Uses Microsoft Agent Framework SDK for orchestration, "
        "Azure AI Search for retrieval, and Azure OpenAI for generation. "
        "Frontend-agnostic — designed to serve React, Power Apps, PCF, "
        "or any custom UI."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — configurable via ALLOWED_ORIGINS env var (comma-separated)
# ---------------------------------------------------------------------------
origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-ID"],
)

logger.info("CORS configured for origins: %s", origins)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(router)


@app.get(
    "/health",
    summary="Health check",
    description="Simple health check endpoint for deployment verification.",
)
async def health() -> dict:
    """Simple health-check endpoint for deployment verification.

    Returns {"status": "ok"} when the service is running.
    Used by Azure App Service health probes and deployment checks.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Startup logging
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    """Log startup information for deployment verification."""
    logger.info("=" * 60)
    logger.info("Technical Manuals Chatbot API starting up")
    logger.info("Docs available at /docs")
    logger.info("Health check at /health")
    logger.info("Chat endpoint at /chat")
    logger.info("=" * 60)
