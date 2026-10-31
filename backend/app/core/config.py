"""
Application configuration loaded from environment variables.

All secrets must be in .env (gitignored).  .env.example contains placeholders only.

Authentication note (demo-only limitation):
    JWT HS256 with an 8-hour expiry is sufficient for a local prototype demonstration.
    It is NOT suitable for production use:
    - No token revocation mechanism is implemented.
    - A single shared SECRET_KEY means all tokens become invalid if the key changes.
    - Production deployments should use RS256, short-lived access tokens + refresh
      tokens, and a token revocation store.
"""
from __future__ import annotations

import os
from datetime import date
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://campus_os:campus_os@localhost:5432/campus_os",
        description="PostgreSQL connection URL",
    )
    TEST_DATABASE_URL: str = Field(
        default="postgresql://campus_os:campus_os@localhost:5432/campus_os_test",
        description="PostgreSQL test connection URL",
    )

    # ── Security ─────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="INSECURE-dev-key-replace-before-any-real-use",
        description="JWT signing secret.  Use secrets.token_hex(32) to generate.",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # ── Demo ─────────────────────────────────────────────────────────────
    DEMO_PASSWORD: str = Field(default="changeme")
    DEMO_TODAY: date = Field(
        default=date(2026, 10, 26),
        description=(
            "Fixed 'today' for reproducible demos and tests. "
            "Tests inject their own value via fixtures."
        ),
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(default="fallback")  # "fallback" | "groq"
    GROQ_API_KEY: str | None = Field(default=None)
    GROQ_MODEL: str | None = Field(default=None)

    # ── CORS ─────────────────────────────────────────────────────────────
    ALLOW_ORIGINS: list[str] | str = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )

    @field_validator("ALLOW_ORIGINS", mode="after")
    @classmethod
    def parse_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)

    # ── Institution ───────────────────────────────────────────────────────
    INSTITUTION_TIMEZONE: str = Field(default="Asia/Kolkata")

    @property
    def today(self) -> date:
        """
        Return the effective 'today'.

        In production-like mode this should use datetime.date.today() with
        proper timezone handling.  For the prototype, DEMO_TODAY is used
        everywhere to keep demos reproducible.  Tests inject via dependency
        override.
        """
        return self.DEMO_TODAY


# Singleton — import this object everywhere, do not re-instantiate.
settings = Settings()
