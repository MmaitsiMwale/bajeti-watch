"""
api/main.py

FastAPI application entrypoint for Bajeti Watch.

Run locally:
    uvicorn api.main:app --reload --port 8000

With ngrok (in a second terminal):
    ngrok http 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health    import router as health_router
from api.routes.whatsapp  import router as whatsapp_router
from api.routes.dashboard import router as dashboard_router

# Load .env before anything else
load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Bajeti Watch API starting up...")
    logger.info(f"Environment : {os.environ.get('APP_ENV', 'development')}")
    logger.info(f"Groq model  : {os.environ.get('GROQ_MODEL', 'llama-3.1-70b-versatile')}")
    logger.info(f"Embeddings  : {os.environ.get('EMBEDDING_PROVIDER', 'ollama')}")
    yield
    logger.info("Bajeti Watch API shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bajeti Watch API",
    description="Budget transparency for every Kenyan citizen.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dashboard to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router,   tags=["Health"])
app.include_router(whatsapp_router, prefix="/webhook", tags=["WhatsApp"])
app.include_router(dashboard_router, tags=["Dashboard"])


@app.get("/")
async def root():
    return {
        "service": "Bajeti Watch API",
        "docs":    "/docs",
        "health":  "/health",
        "webhook": "/webhook/whatsapp",
        "dashboard_api": "/dashboard/summary",
    }