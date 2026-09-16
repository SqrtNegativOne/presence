"""
main.py — FastAPI application entry point.

Run with:  uv run uvicorn main:app --reload --port 8000
"""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

import config
import database
from routers import attendance, students

# ---------------------------------------------------------------------------
# Loguru setup — pretty, coloured logs in the terminal
# ---------------------------------------------------------------------------
logger.remove()  # remove the default handler
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> — {message}",
    level="DEBUG",
    colorize=True,
)


# ---------------------------------------------------------------------------
# Lifespan: code that runs at startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    logger.info("Starting Presence backend…")
    logger.info(f"Cloud mode enabled: {config.CLOUD_MODE_ENABLED}")
    database.init_db()  # create tables if they don't exist
    # We intentionally do NOT pre-load the InsightFace model here because
    # it takes 5-10 seconds and the first request will trigger it anyway.
    # Uncomment the next two lines if you want it loaded at startup:
    # from services.face_service import get_face_app
    # get_face_app()
    yield
    # --- shutdown ---
    logger.info("Shutting down Presence backend.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Presence — Teacher Attendance API",
    description="Face-recognition-based attendance system for classrooms.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the configured frontend origins to call our API without CORS errors.
# Configure via the ALLOWED_ORIGINS env var (comma-separated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(students.router)
app.include_router(attendance.router)


@app.get("/")
async def root():
    return {
        "message": "Presence API is running. Visit /docs for the interactive API explorer."
    }
