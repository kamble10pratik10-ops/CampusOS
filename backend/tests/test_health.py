"""
test_health.py — M1 health check and basic API smoke tests.

These tests verify:
    - /health returns 200 with expected fields (no auth required)
    - /auth/token returns a JWT for valid demo credentials
    - /auth/token rejects bad credentials with 401
    - /auth/me returns the authenticated user
    - /dashboard requires authentication (401 without token)
    - /dashboard returns the expected shape for an authenticated HOD

All data is SYNTHETIC.  No real institutional data is used.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── Health ────────────────────────────────────────────────────────────────


def test_health_no_auth(client: TestClient) -> None:
    """GET /health must return 200 without a token."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "milestone" in body
    assert body["milestone"] == "M1"
    assert "data_label" in body


# ── Auth ──────────────────────────────────────────────────────────────────


def test_login_valid_credentials(seeded_client: TestClient) -> None:
    """POST /auth/token must return a JWT for seeded demo credentials."""
    response = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in_seconds"] > 0


def test_login_invalid_password(seeded_client: TestClient) -> None:
    """POST /auth/token must return 401 for a wrong password."""
    response = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_unknown_user(seeded_client: TestClient) -> None:
    """POST /auth/token must return 401 for an unknown email."""
    response = seeded_client.post(
        "/auth/token",
        data={"username": "ghost@campus.os", "password": "changeme"},
    )
    assert response.status_code == 401


def _get_token(client: TestClient, email: str, password: str = "changeme") -> str:
    """Helper: obtain a JWT for the given demo user."""
    response = client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]


def test_me_authenticated(seeded_client: TestClient) -> None:
    """GET /auth/me must return the authenticated user's profile."""
    token = _get_token(seeded_client, "principal@campus.os")
    response = seeded_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "principal@campus.os"
    assert body["role"] == "principal"
    assert body["is_active"] is True
    # Principal must not have a department_id restriction
    assert body["department_id"] is None


def test_me_unauthenticated(seeded_client: TestClient) -> None:
    """GET /auth/me must return 401 without a token."""
    response = seeded_client.get("/auth/me")
    assert response.status_code == 401


def test_me_invalid_token(seeded_client: TestClient) -> None:
    """GET /auth/me must return 401 for a malformed token."""
    response = seeded_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


# ── Dashboard ─────────────────────────────────────────────────────────────


def test_dashboard_unauthenticated(seeded_client: TestClient) -> None:
    """GET /dashboard must return 401 without a token."""
    response = seeded_client.get("/dashboard")
    assert response.status_code == 401


def test_dashboard_principal(seeded_client: TestClient) -> None:
    """GET /dashboard must return valid stats for the principal role."""
    token = _get_token(seeded_client, "principal@campus.os")
    response = seeded_client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    # ── Entity counts ─────────────────────────────────────────────────────
    # Seed data: 30 faculty, 40 courses, 12 sections, 15 rooms
    assert body["total_faculty"] == 30
    assert body["total_courses"] == 40
    assert body["total_sections"] == 12
    assert body["total_rooms"] == 15

    # ── Availability ──────────────────────────────────────────────────────
    # DEMO_TODAY = 2026-10-26 (Mon).  ME004 is on leave that day.
    assert body["faculty_on_leave_today"] >= 1
    assert body["faculty_available_today"] == body["total_faculty"] - body["faculty_on_leave_today"]

    # ── Conflict counts ───────────────────────────────────────────────────
    # Seed plants exactly 5 conflicts (HC-01, HC-02, HC-04, HC-05, HC-06).
    # M1 approximation may report counts per-rule, not per-violation pair,
    # but total must be > 0.
    assert body["conflict_count"] > 0
    rule_ids = {c["rule_id"] for c in body["conflicts_summary"]}
    assert "HC-01" in rule_ids
    assert "HC-02" in rule_ids

    # ── Shape ─────────────────────────────────────────────────────────────
    assert "workload_summary" in body
    assert body["workload_summary"]["avg_hours_this_week"] >= 0
    assert "recent_decisions" in body
    assert body["data_label"].startswith("SYNTHETIC")


def test_dashboard_hod(seeded_client: TestClient) -> None:
    """GET /dashboard must succeed for an HOD role."""
    token = _get_token(seeded_client, "hod.cs@campus.os")
    response = seeded_client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_faculty"] > 0


# ── Data label ────────────────────────────────────────────────────────────


def test_data_label_present(seeded_client: TestClient) -> None:
    """Dashboard response must include the SYNTHETIC data label."""
    token = _get_token(seeded_client, "principal@campus.os")
    response = seeded_client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "SYNTHETIC" in response.json()["data_label"]

