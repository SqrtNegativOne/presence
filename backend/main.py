"""
main.py — FastAPI application entry point.

Run with:  uv run uvicorn main:app --reload --port 8000
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

import database
from auth.jwt import warn_if_dev_secret
from routers import attendance, auth as auth_router, recognizers as recognizers_router, students

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{line}</cyan> — {message}",
    level="DEBUG",
    colorize=True,
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Presence backend…")
    database.init_db()
    warn_if_dev_secret()

    # Seed the demo user in the background — encoding the four faces with
    # InsightFace can take ~30 s on first run because the model has to download.
    # We don't want that to delay the API coming online.
    if os.environ.get("PRESENCE_SEED_DEMO", "1") != "0":
        async def _seed():
            try:
                from seed_demo import seed as seed_demo
                await asyncio.to_thread(seed_demo)
            except Exception as e:
                logger.warning(f"Demo seeding failed: {e}")
        asyncio.create_task(_seed())

    yield
    logger.info("Shutting down Presence backend.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Presence — Teacher Attendance API",
    description="Face-recognition-based attendance system for classrooms.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(recognizers_router.router)
app.include_router(students.router)
app.include_router(attendance.router)


@app.get("/")
async def root():
    return {"message": "Presence API is running. Visit /docs for the interactive API explorer."}
