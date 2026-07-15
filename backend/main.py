"""FastAPI backend for The Virtual Garage: An F1 Engineering Suite.

Exposes the strategy, suspension and telemetry engines as JSON endpoints and
serves the static frontend. Input is validated via typed/constrained query
parameters, so malformed requests return a 422 instead of crashing.
"""

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import f1_data

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="The Virtual Garage: An F1 Engineering Suite", version="1.0.0")

# Restrict CORS to an explicit allowlist (never "*"). Override in deployment via
# the ALLOWED_ORIGINS env var (comma-separated).
_default_origins = "http://localhost:8000,http://127.0.0.1:8000"
allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/strategy")
def strategy(
    session_key: int = Query(..., ge=1),
    driver_number: int = Query(..., ge=1, le=99),
) -> dict:
    return f1_data.compute_strategy(session_key, driver_number)


@app.get("/api/suspension")
def suspension(
    roll_angle: float = Query(0.0, ge=-5.0, le=5.0),
    wishbone_length: float = Query(380.0, ge=300.0, le=500.0),
) -> dict:
    return f1_data.compute_suspension(roll_angle, wishbone_length)


@app.get("/api/telemetry")
def telemetry(
    session_key: int = Query(..., ge=1),
    driver_number: int = Query(..., ge=1, le=99),
) -> dict:
    return f1_data.compute_telemetry(session_key, driver_number)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


# Serve the rest of the static frontend (JS/CSS). Mounted last so it does not
# shadow the /api routes above.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
