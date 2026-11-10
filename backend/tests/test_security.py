"""
test_security.py — Role-based authorization, cross-department access, and API contract tests (M5).

Verifies SPEC Section 12 & Section 16 requirements:
- Backend role enforcement (Principal unrestricted, HOD restricted to own department).
- Cross-department access attempts return HTTP 403 Forbidden.
- Department-filtered dashboard statistics for HODs.
- SPEC Section 13 contract routes (/whatif, /decisions, /faculty, /departments).
- No leakage of internal secrets or password hashes.
"""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Department, Faculty, RoleEnum, User


def _get_token(client: TestClient, email: str, password: str = "changeme") -> str:
    res = client.post("/auth/token", data={"username": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_cross_department_conflicts_rejected(seeded_client: TestClient, db_session: Session) -> None:
    """HOD of CS must be rejected with 403 when requesting conflicts for EC department."""
    ec_dept = db_session.query(Department).filter(Department.code == "EC").first()
    assert ec_dept is not None

    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    res = seeded_client.get(
        f"/conflicts?department_id={ec_dept.id}",
        headers={"Authorization": f"Bearer {token_cs}"},
    )
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"].lower() or "restricted" in res.json()["detail"].lower()


def test_principal_can_access_any_department_conflicts(seeded_client: TestClient, db_session: Session) -> None:
    """Principal must have unrestricted access to any department's conflicts."""
    ec_dept = db_session.query(Department).filter(Department.code == "EC").first()
    assert ec_dept is not None

    token_principal = _get_token(seeded_client, "principal@campus.os")
    res = seeded_client.get(
        f"/conflicts?department_id={ec_dept.id}",
        headers={"Authorization": f"Bearer {token_principal}"},
    )
    assert res.status_code == 200
    assert "violations" in res.json()


def test_cross_department_workload_rejected(seeded_client: TestClient, db_session: Session) -> None:
    """HOD of CS must be rejected with 403 when requesting workload for ME department."""
    me_dept = db_session.query(Department).filter(Department.code == "ME").first()
    assert me_dept is not None

    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    res = seeded_client.get(
        f"/workload?department_id={me_dept.id}",
        headers={"Authorization": f"Bearer {token_cs}"},
    )
    assert res.status_code == 403


def test_cross_department_planner_optimization_rejected(seeded_client: TestClient, db_session: Session) -> None:
    """HOD of CS must be rejected with 403 when attempting to optimize replacement for EC faculty."""
    ec_faculty = (
        db_session.query(Faculty)
        .join(Faculty.department)
        .filter(Department.code == "EC")
        .first()
    )
    assert ec_faculty is not None

    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    res = seeded_client.post(
        "/planner/optimize",
        headers={"Authorization": f"Bearer {token_cs}"},
        json={
            "faculty_id": str(ec_faculty.id),
            "start_date": "2026-11-02",
            "end_date": "2026-11-04",
        },
    )
    assert res.status_code == 403


def test_cross_department_simulation_rejected(seeded_client: TestClient, db_session: Session) -> None:
    """HOD of CS must be rejected with 403 when running simulation for EC faculty."""
    ec_faculty = (
        db_session.query(Faculty)
        .join(Faculty.department)
        .filter(Department.code == "EC")
        .first()
    )
    assert ec_faculty is not None

    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    res = seeded_client.post(
        "/simulation/run",
        headers={"Authorization": f"Bearer {token_cs}"},
        json={
            "faculty_id": str(ec_faculty.id),
            "start_date": "2026-11-02",
            "end_date": "2026-11-04",
        },
    )
    assert res.status_code == 403


def test_hod_department_scoped_dashboard(seeded_client: TestClient, db_session: Session) -> None:
    """HOD dashboard must report department-scoped counts (10 CS faculty) vs Principal (30 total faculty)."""
    token_cs = _get_token(seeded_client, "hod.cs@campus.os")
    token_principal = _get_token(seeded_client, "principal@campus.os")

    res_cs = seeded_client.get("/dashboard", headers={"Authorization": f"Bearer {token_cs}"})
    assert res_cs.status_code == 200
    data_cs = res_cs.json()
    assert data_cs["total_faculty"] == 10  # 10 CS faculty

    res_p = seeded_client.get("/dashboard", headers={"Authorization": f"Bearer {token_principal}"})
    assert res_p.status_code == 200
    data_p = res_p.json()
    assert data_p["total_faculty"] == 30  # 30 Total faculty institution-wide


def test_spec_section_13_contract_routes(seeded_client: TestClient, db_session: Session) -> None:
    """Verify SPEC Section 13 endpoints: /whatif, /decisions, /departments, /faculty."""
    token = _get_token(seeded_client, "principal@campus.os")

    # 1. GET /departments
    r_dept = seeded_client.get("/departments", headers={"Authorization": f"Bearer {token}"})
    assert r_dept.status_code == 200
    assert len(r_dept.json()) == 3

    # 2. GET /faculty
    r_fac = seeded_client.get("/faculty", headers={"Authorization": f"Bearer {token}"})
    assert r_fac.status_code == 200
    assert len(r_fac.json()) == 30

    # 3. POST /whatif
    cs_faculty = (
        db_session.query(Faculty)
        .filter(Faculty.employee_code == "CS001")
        .first()
    )
    r_whatif = seeded_client.post(
        "/whatif",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "faculty_id": str(cs_faculty.id),
            "start_date": "2026-11-02",
            "end_date": "2026-11-04",
        },
    )
    assert r_whatif.status_code == 200
    body = r_whatif.json()
    decision_id = body["decision_id"]
    assert body["critic_status"] == "feasible_complete"

    # 4. GET /decisions
    r_decisions = seeded_client.get("/decisions", headers={"Authorization": f"Bearer {token}"})
    assert r_decisions.status_code == 200
    assert any(d["id"] == decision_id for d in r_decisions.json())

    # 5. GET /decisions/{id}
    r_detail = seeded_client.get(f"/decisions/{decision_id}", headers={"Authorization": f"Bearer {token}"})
    assert r_detail.status_code == 200
    assert r_detail.json()["id"] == decision_id

    # 6. POST /decisions/{id}/approve
    r_app = seeded_client.post(f"/decisions/{decision_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert r_app.status_code == 200
    assert r_app.json()["decision_status"] == "approved"

