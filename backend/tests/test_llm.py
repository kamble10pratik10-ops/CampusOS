"""
test_llm.py — Natural Language Intent Parsing, Groq Integration & Explanations (M6).

Verifies SPEC Section 10 & M6 acceptance criteria:
- Natural language intent parsing and entity resolution
- Deterministic fallback when Groq is unavailable
- Explanation generation grounded strictly in verified decision data
- POST /query endpoint executing end-to-end simulations from free text
- Backend role enforcement on natural language queries
- Decision correctness invariant: LLM never overrides rules or determines feasibility
"""
from __future__ import annotations

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Department, Faculty
from app.llm.fallback import DeterministicFallbackProvider
from app.llm.groq_client import GroqClientProvider
from app.llm.resolver import EntityResolver
from app.schemas.llm import ExplanationRequest, IntentTypeEnum


def _get_token(client: TestClient, email: str, password: str = "changeme") -> str:
    res = client.post("/auth/token", data={"username": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_deterministic_fallback_intent_parsing_hero() -> None:
    """Deterministic fallback extracts faculty and intent from Hero prompt."""
    provider = DeterministicFallbackProvider()
    query = "Dr. Raj Sharma is on leave next week Monday to Wednesday. Recommend replacement plans."
    intent = await provider.parse_intent(query)

    assert intent.intent_type == IntentTypeEnum.leave_simulation
    assert "Raj Sharma" in (intent.faculty_name_or_code or "")
    assert intent.confidence >= 0.8


@pytest.mark.asyncio
async def test_deterministic_fallback_intent_parsing_conflicts() -> None:
    """Deterministic fallback extracts conflict check intent."""
    provider = DeterministicFallbackProvider()
    query = "Check for timetable conflicts and rule violations."
    intent = await provider.parse_intent(query)
    assert intent.intent_type == IntentTypeEnum.check_conflicts


@pytest.mark.asyncio
async def test_deterministic_fallback_intent_parsing_workload() -> None:
    """Deterministic fallback extracts workload check intent."""
    provider = DeterministicFallbackProvider()
    query = "Show faculty workload distribution and overloaded teachers."
    intent = await provider.parse_intent(query)
    assert intent.intent_type == IntentTypeEnum.check_workload


@pytest.mark.asyncio
async def test_deterministic_fallback_clarification_needed() -> None:
    """Ambiguous queries produce clarification prompts."""
    provider = DeterministicFallbackProvider()
    query = "What is the weather today?"
    intent = await provider.parse_intent(query)
    assert intent.intent_type == IntentTypeEnum.clarification_needed
    assert intent.clarification_prompt is not None


def test_entity_resolver_faculty_and_dates(db_session: Session) -> None:
    """EntityResolver maps natural language names and relative dates to real DB records."""
    resolver = EntityResolver(db_session, reference_date=date(2026, 10, 26))

    # 1. Resolve Dr. Raj Sharma by name
    fac = resolver.resolve_faculty("Dr. Raj Sharma")
    assert fac is not None
    assert fac.employee_code == "CS001"

    # 2. Resolve by code
    fac2 = resolver.resolve_faculty("CS001")
    assert fac2 is not None
    assert fac2.id == fac.id

    # 3. Resolve relative 'next week Mon to Wed' from Monday 2026-10-26
    d1, d2 = resolver.resolve_dates("on leave next week Monday to Wednesday")
    assert d1 == date(2026, 11, 2)
    assert d2 == date(2026, 11, 4)

    # 4. Resolve ISO dates
    d3, d4 = resolver.resolve_dates("2026-11-02 to 2026-11-04")
    assert d3 == date(2026, 11, 2)
    assert d4 == date(2026, 11, 4)


@pytest.mark.asyncio
async def test_explanation_generation_grounded_in_data() -> None:
    """Explanation includes verified coverage, Critic status, and zero new hard violations."""
    provider = DeterministicFallbackProvider()
    req = ExplanationRequest(
        scenario_name="Test Hero Scenario",
        faculty_name="Dr. Raj Sharma",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
        covered_occurrences=6,
        total_occurrences=6,
        coverage_percentage=100.0,
        critic_status="feasible_complete",
        critic_summary="100% complete coverage, 0 new hard violations",
        new_hard_violations_count=0,
        resolved_violations_count=6,
        overall_score=94.5,
        workload_shifts=[{"faculty_name": "Dr. Sunita Rao", "delta_hours": 2.0, "after_hours": 12.0}],
    )

    exp = await provider.generate_explanation(req)
    assert "Dr. Raj Sharma" in exp
    assert "100.0%" in exp
    assert "0 new" in exp
    assert "HC-10" in exp


@pytest.mark.asyncio
async def test_groq_client_graceful_fallback_on_invalid_key() -> None:
    """GroqClientProvider falls back gracefully to deterministic fallback on failure."""
    fallback = DeterministicFallbackProvider()
    groq = GroqClientProvider(
        api_key="gsk_invalid_test_key_should_fail_gracefully",
        model="qwen/qwen3.8-27b",
        fallback=fallback,
        timeout_seconds=2.0,
        max_retries=0,
    )

    # Must not raise; must seamlessly return deterministic intent
    intent = await groq.parse_intent("Dr. Raj Sharma is on leave next week from Nov 2 to Nov 4")
    assert intent.intent_type == IntentTypeEnum.leave_simulation
    assert "Raj Sharma" in (intent.faculty_name_or_code or "")


def test_api_post_query_hero_scenario(seeded_client: TestClient) -> None:
    """POST /query executes full end-to-end simulation from natural language prompt."""
    token = _get_token(seeded_client, "principal@campus.os")
    res = seeded_client.post(
        "/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Dr. Raj Sharma is on leave next week Monday to Wednesday. Recommend replacement plans.",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["parsed_intent"]["intent_type"] == "leave_simulation"
    assert data["simulation"] is not None
    assert data["simulation"]["critic_result"]["is_approved"] is True
    assert data["simulation"]["selected_plan"]["covered_occurrences"] == 6
    assert data["explanation"] != ""
    assert "Raj Sharma" in data["explanation"]


def test_api_post_query_conflicts(seeded_client: TestClient) -> None:
    """POST /query answers timetable conflict questions."""
    token = _get_token(seeded_client, "principal@campus.os")
    res = seeded_client.post(
        "/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "What timetable conflicts exist in the current schedule?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["parsed_intent"]["intent_type"] == "check_conflicts"
    assert data["conflicts"] is not None
    assert data["conflicts"]["hard_conflicts"] > 0


def test_api_post_query_cross_department_rejected(seeded_client: TestClient, db_session: Session) -> None:
    """HOD CS natural language query for EC faculty must be rejected with 403 Forbidden."""
    ec_faculty = (
        db_session.query(Faculty)
        .join(Faculty.department)
        .filter(Department.code == "EC")
        .first()
    )
    assert ec_faculty is not None

    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    res = seeded_client.post(
        "/query",
        headers={"Authorization": f"Bearer {token_cs}"},
        json={
            "query": f"{ec_faculty.name} is on leave next week from Nov 2 to Nov 4. Optimize replacement.",
        },
    )
    assert res.status_code == 403

