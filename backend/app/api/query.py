"""
Query API route for Natural Language Intent Parsing & Explanations (Milestone M6).

POST /query — parses natural language questions, extracts parameters, executes
deterministic decision pipelines (rules, CP-SAT solver, Critic), and produces
readable, evidence-grounded explanations.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import RoleEnum, User
from app.db.session import get_db
from app.engine.rules import RuleEngine
from app.engine.simulation import SimulationPipeline
from app.llm import EntityResolver, get_llm_provider
from app.schemas.llm import (
    ExplanationRequest,
    IntentTypeEnum,
    QueryRequest,
    QueryResponse,
)
from app.schemas.rules import ConflictsResponse, WorkloadResponse
from app.schemas.simulation import SimulationRequest
from app.services.timetable import get_workload_this_week, week_bounds

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Natural language operational query and scenario simulation",
    description=(
        "Interprets natural language operational requests using Groq (or deterministic fallback), "
        "resolves entities and dates against real PostgreSQL records, executes deterministic "
        "decision engines, and returns a verified decision with a readable explanation.\n\n"
        "⚠ All underlying data is SYNTHETIC."
    ),
)
async def process_query(
    request: QueryRequest,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> QueryResponse:
    llm = get_llm_provider(settings)
    resolver = EntityResolver(db, reference_date=settings.today)

    # 1. Parse intent
    parsed_intent = await llm.parse_intent(request.query, request.context)

    # 2. Resolve entities & dates against database
    if parsed_intent.faculty_name_or_code and not parsed_intent.faculty_id:
        fac = resolver.resolve_faculty(parsed_intent.faculty_name_or_code)
        if fac:
            parsed_intent.faculty_id = fac.id
            parsed_intent.department_id = fac.department_id
            parsed_intent.faculty_name_or_code = fac.name

    if not parsed_intent.start_date or not parsed_intent.end_date:
        d1, d2 = resolver.resolve_dates(request.query)
        if d1 and d2:
            parsed_intent.start_date = d1
            parsed_intent.end_date = d2

    # Role enforcement: check cross-department access if faculty/dept identified
    if current_user.role == RoleEnum.hod and parsed_intent.department_id:
        if parsed_intent.department_id != current_user.department_id:
            check_department_access(current_user, parsed_intent.department_id)

    # 3. Handle leave replacement simulation intent
    if parsed_intent.intent_type == IntentTypeEnum.leave_simulation:
        # Check if we have required parameters
        missing = []
        if not parsed_intent.faculty_id:
            missing.append("faculty_member")
        if not parsed_intent.start_date or not parsed_intent.end_date:
            missing.append("leave_dates")

        if missing:
            parsed_intent.missing_fields = missing
            explanation = (
                f"I understood that you want to simulate a leave replacement scenario, but I need "
                f"additional details: {', '.join(missing)}. For example: 'Dr. Raj Sharma is on leave "
                f"next week from Nov 2 to Nov 4. Optimize replacement plans.'"
            )
            return QueryResponse(
                query=request.query,
                parsed_intent=parsed_intent,
                explanation=explanation,
                llm_provider=llm.provider_name,
                llm_model=llm.model_name,
                llm_status=f"{llm.provider_name}_clarification_needed",
            )

        # Execute deterministic simulation pipeline
        sim_pipeline = SimulationPipeline(db)
        sim_req = SimulationRequest(
            faculty_id=parsed_intent.faculty_id,
            start_date=parsed_intent.start_date,
            end_date=parsed_intent.end_date,
            max_alternatives=parsed_intent.max_alternatives,
            scenario_name=f"Leave Replacement: {parsed_intent.faculty_name_or_code} ({parsed_intent.start_date} to {parsed_intent.end_date})",
        )
        sim_result = sim_pipeline.run_simulation(sim_req, current_user)

        # Generate evidence-grounded explanation
        selected = sim_result.selected_plan
        critic = sim_result.critic_result
        raw_shifts = getattr(sim_result.diff, "faculty_workload_shifts", None)
        if raw_shifts:
            shifts_dict = [
                {
                    "faculty_name": getattr(s, "faculty_name", str(s)),
                    "delta_hours": getattr(s, "delta_hours", 0.0),
                    "after_hours": getattr(s, "after_hours", 0.0),
                }
                for s in raw_shifts
            ]
        else:
            faculty_counts: dict[str, int] = {}
            for a in (selected.assignments if selected else []):
                if a.assigned_faculty_name:
                    faculty_counts[a.assigned_faculty_name] = faculty_counts.get(a.assigned_faculty_name, 0) + 1
            shifts_dict = [
                {
                    "faculty_name": fname,
                    "delta_hours": float(cnt),
                    "after_hours": float(cnt),
                }
                for fname, cnt in faculty_counts.items()
            ]

        exp_req = ExplanationRequest(
            scenario_name=sim_result.scenario_summary,
            faculty_name=parsed_intent.faculty_name_or_code or "Selected Faculty",
            start_date=parsed_intent.start_date,
            end_date=parsed_intent.end_date,
            covered_occurrences=selected.covered_occurrences,
            total_occurrences=selected.total_occurrences,
            coverage_percentage=selected.coverage_percentage,
            critic_status=critic.status.value,
            critic_summary=critic.summary,
            new_hard_violations_count=critic.new_hard_violations_count,
            resolved_violations_count=critic.resolved_violations_count,
            overall_score=selected.overall_score,
            workload_shifts=shifts_dict,
            evidence_refs=[e.description for e in sim_result.evidence_refs],
        )

        explanation = await llm.generate_explanation(exp_req)

        return QueryResponse(
            query=request.query,
            parsed_intent=parsed_intent,
            explanation=explanation,
            simulation=sim_result,
            llm_provider=llm.provider_name,
            llm_model=llm.model_name,
            llm_status=f"{llm.provider_name}_success",
        )

    # 4. Handle check conflicts intent
    elif parsed_intent.intent_type == IntentTypeEnum.check_conflicts:
        engine = RuleEngine(db)
        rule_result = engine.validate_timetable_template()

        conflicts_resp = ConflictsResponse(
            is_valid=rule_result.is_valid,
            total_conflicts=rule_result.total_violations,
            hard_conflicts=rule_result.hard_violations_count,
            soft_conflicts=rule_result.soft_violations_count,
            violations=rule_result.violations,
            by_rule=rule_result.by_rule,
            evaluation_scope="template",
        )

        explanation = (
            f"**Timetable Conflict Analysis:**\n\n"
            f"The deterministic Rule Engine evaluated the active weekly template and identified "
            f"**{rule_result.hard_violations_count} hard constraint violations** across rules "
            f"{', '.join(sorted(rule_result.by_rule.keys()))}.\n\n"
            f"- **HC-01 (Faculty Overlaps):** {len(rule_result.by_rule.get('HC-01', []))} occurrence(s)\n"
            f"- **HC-02 (Room Overlaps):** {len(rule_result.by_rule.get('HC-02', []))} occurrence(s)\n"
            f"- **HC-04 (Room Capacity):** {len(rule_result.by_rule.get('HC-04', []))} occurrence(s)\n"
            f"- **HC-05 (Lab Requirement):** {len(rule_result.by_rule.get('HC-05', []))} occurrence(s)\n"
            f"- **HC-06 (Expertise Mismatch):** {len(rule_result.by_rule.get('HC-06', []))} occurrence(s)\n"
        )

        return QueryResponse(
            query=request.query,
            parsed_intent=parsed_intent,
            explanation=explanation,
            conflicts=conflicts_resp,
            llm_provider=llm.provider_name,
            llm_model=llm.model_name,
            llm_status=f"{llm.provider_name}_success",
        )

    # 5. Handle check workload intent
    elif parsed_intent.intent_type == IntentTypeEnum.check_workload:
        mon, sun = week_bounds(settings.today)
        dept_id = current_user.department_id if current_user.role == RoleEnum.hod else None
        wl_raw = get_workload_this_week(db, mon, sun, department_id=dept_id)

        explanation = (
            f"**Faculty Workload & Capacity Utilization:**\n\n"
            f"For the current week ({mon} to {sun}):\n"
            f"- **Average Teaching Load:** {wl_raw['avg_hours_this_week']:.1f} hours\n"
            f"- **Maximum Assigned Load:** {wl_raw['max_hours_this_week']:.1f} hours\n"
            f"- **Minimum Assigned Load:** {wl_raw['min_hours_this_week']:.1f} hours\n"
            f"- **Overloaded Faculty (HC-07 breach):** {wl_raw['overloaded_count']} faculty members\n"
        )

        return QueryResponse(
            query=request.query,
            parsed_intent=parsed_intent,
            explanation=explanation,
            llm_provider=llm.provider_name,
            llm_model=llm.model_name,
            llm_status=f"{llm.provider_name}_success",
        )

    # 6. Fallback clarification
    else:
        explanation = (
            "I could not determine the exact operational task requested. You can ask me to:\n"
            "1. **Simulate leave replacements:** 'Dr. Raj Sharma is on leave next week Monday to Wednesday.'\n"
            "2. **Check timetable conflicts:** 'What conflicts exist in the schedule?'\n"
            "3. **Inspect faculty workload:** 'Show faculty workload for this week.'"
        )
        return QueryResponse(
            query=request.query,
            parsed_intent=parsed_intent,
            explanation=explanation,
            llm_provider=llm.provider_name,
            llm_model=llm.model_name,
            llm_status=f"{llm.provider_name}_clarification",
        )
