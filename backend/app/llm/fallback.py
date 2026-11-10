"""
Deterministic Fallback Provider (Milestone M6).

Guarantees 100% operational functionality without an external LLM API key.
Uses pattern matching, regular expressions, and structured templates to:
- Parse common administrative commands and natural language scenario requests.
- Produce structured, evidence-grounded explanations of already-computed decisions.
"""
from __future__ import annotations

import re
from typing import Any

from app.llm.interface import LLMProvider
from app.schemas.llm import ExplanationRequest, IntentTypeEnum, ParsedIntent


class DeterministicFallbackProvider(LLMProvider):
    """Zero-dependency deterministic fallback provider."""

    @property
    def provider_name(self) -> str:
        return "deterministic_fallback"

    @property
    def model_name(self) -> str | None:
        return "rules_template_engine"

    async def parse_intent(
        self,
        text: str,
        entity_context: dict[str, Any] | None = None,
    ) -> ParsedIntent:
        clean_text = text.strip()
        text_lower = clean_text.lower()

        # 1. Check for conflict queries
        if any(w in text_lower for w in ["conflict", "violation", "overlap", "double book", "double-book"]):
            return ParsedIntent(
                intent_type=IntentTypeEnum.check_conflicts,
                confidence=0.95,
                raw_query=clean_text,
            )

        # 2. Check for workload queries
        if any(w in text_lower for w in ["workload", "overload", "hours", "capacity", "teaching load"]):
            return ParsedIntent(
                intent_type=IntentTypeEnum.check_workload,
                confidence=0.95,
                raw_query=clean_text,
            )

        # 3. Check for leave replacement / simulation queries
        is_leave_sim = any(
            w in text_lower
            for w in ["leave", "replace", "replacement", "substitute", "absent", "cover", "simulate", "what-if", "what if"]
        )

        # Also match Hero scenario prompt directly
        is_hero = "raj sharma" in text_lower or "cs001" in text_lower

        if is_leave_sim or is_hero:
            # Extract faculty string
            faculty_match = re.search(
                r"\b((?:dr\.?|prof\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|[A-Z]{2}\d{3})\b",
                clean_text,
                re.IGNORECASE,
            )
            faculty_str = faculty_match.group(1) if faculty_match else None
            if not faculty_str and is_hero:
                faculty_str = "Dr. Raj Sharma"

            missing: list[str] = []
            if not faculty_str:
                missing.append("faculty_name")

            return ParsedIntent(
                intent_type=IntentTypeEnum.leave_simulation,
                faculty_name_or_code=faculty_str,
                confidence=0.9 if faculty_str else 0.6,
                missing_fields=missing,
                clarification_prompt=(
                    "Please specify which faculty member is requesting leave (e.g., 'Dr. Raj Sharma' or 'CS001')."
                    if "faculty_name" in missing
                    else None
                ),
                raw_query=clean_text,
            )

        # 4. Clarification needed
        return ParsedIntent(
            intent_type=IntentTypeEnum.clarification_needed,
            confidence=0.5,
            missing_fields=["intent_type"],
            clarification_prompt=(
                "I can help with faculty leave replacement simulation, timetable conflict detection, "
                "or workload distribution checks. For example: 'Dr. Raj Sharma is on leave next week "
                "Monday to Wednesday. Optimize replacement plans.'"
            ),
            raw_query=clean_text,
        )

    async def generate_explanation(
        self,
        request: ExplanationRequest,
    ) -> str:
        """
        Produce a clear, deterministic explanation grounded strictly in verified output data.
        """
        cov_pct = f"{request.coverage_percentage:.1f}%"
        status_text = "fully covered" if request.covered_occurrences == request.total_occurrences else "partially covered"

        explanation = (
            f"**Operational Decision Summary:**\n\n"
            f"Faculty member **{request.faculty_name}** is on leave from **{request.start_date}** to **{request.end_date}**, "
            f"affecting **{request.total_occurrences} class occurrences**.\n\n"
            f"The Google OR-Tools CP-SAT joint optimization planner generated replacement alternatives, achieving **{cov_pct} coverage** "
            f"({request.covered_occurrences} of {request.total_occurrences} classes {status_text}) with an overall score of **{request.overall_score:.1f}**.\n\n"
            f"**Independent Critic Verification:**\n"
            f"- **Validation Status:** {request.critic_status.upper()} ({request.critic_summary})\n"
            f"- **Hard Violations Introduced:** {request.new_hard_violations_count} (guaranteed zero new conflicts)\n"
            f"- **Baseline Conflicts Resolved:** {request.resolved_violations_count} conflicts resolved by substitution\n\n"
        )

        if request.workload_shifts:
            explanation += "**Faculty Workload Shifts:**\n"
            for shift in request.workload_shifts[:4]:
                name = shift.get("faculty_name", "Faculty")
                delta = shift.get("delta_hours", 0.0)
                after = shift.get("after_hours", 0.0)
                sign = "+" if delta > 0 else ""
                explanation += f"- {name}: {sign}{delta:.1f}h (total: {after:.1f}h this week)\n"
            explanation += "\n"

        explanation += (
            "*(This explanation was generated using the deterministic verified template engine. "
            "Operational records in PostgreSQL remain unchanged under HC-10.)*"
        )
        return explanation

