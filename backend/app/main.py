"""
Campus OS — FastAPI application entry point.

Architecture:
    Frontend → FastAPI → Auth/Authz → Services → PostgreSQL

⚠  All seeded data is SYNTHETIC and does not represent any real institution.

Security note (demo-only):
    CORS allows the local Vite dev server (port 5173) and an alternative port 3000.
    Do not open these origins in production without restricting to the real frontend domain.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, dashboard

# ── Application factory ───────────────────────────────────────────────────

app = FastAPI(
    title="Campus OS — ANVIL",
    description=(
        "Multi-agent decision-support platform for college operations.\n\n"
        "⚠ **SYNTHETIC DATA** — all seeded content is generated for demonstration "
        "purposes only and does not represent any real institution.\n\n"
        "Authentication: OAuth2 password flow (`POST /auth/token`)."
    ),
    version="0.1.0-M1",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS if isinstance(settings.ALLOW_ORIGINS, list) else [settings.ALLOW_ORIGINS],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(dashboard.router)

# ── Health ────────────────────────────────────────────────────────────────


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description=(
        "Returns 200 with service status. "
        "No authentication required. "
        "Use this to verify the backend is reachable."
    ),
)
def health() -> dict:
    return {
        "status": "ok",
        "version": "0.1.0-M1",
        "milestone": "M1",
        "data_label": "SYNTHETIC — NOT REAL INSTITUTIONAL DATA",
    }

