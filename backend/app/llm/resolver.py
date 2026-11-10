"""
Entity and Date Resolver for natural language interpretation (M6).

Grounds extracted strings against real PostgreSQL database records:
- Faculty names or employee codes -> Faculty UUID and Department ID
- Department names or codes -> Department UUID
- Date expressions (relative or absolute) -> Python date objects
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Department, Faculty


class EntityResolver:
    """Resolves extracted natural language entities against authoritative database records."""

    def __init__(self, db: Session, reference_date: date | None = None) -> None:
        self.db = db
        self.reference_date = reference_date or settings.today

    def resolve_faculty(self, text: str) -> Faculty | None:
        """
        Find faculty by exact code, substring in name, or clean name match.
        Example: 'Dr. Raj Sharma' or 'CS001' or 'Raj Sharma' -> Faculty record.
        """
        if not text:
            return None

        clean = text.strip()
        # 1. Match by employee code (e.g. CS001)
        by_code = self.db.query(Faculty).filter(Faculty.employee_code.ilike(clean)).first()
        if by_code:
            return by_code

        # 2. Strip honorifics (Dr., Prof., etc.)
        name_only = re.sub(r"^(dr\.?|prof\.?|mr\.?|ms\.?|mrs\.?)\s+", "", clean, flags=re.IGNORECASE).strip()
        by_name = (
            self.db.query(Faculty)
            .filter(
                or_(
                    Faculty.name.ilike(f"%{clean}%"),
                    Faculty.name.ilike(f"%{name_only}%"),
                )
            )
            .first()
        )
        return by_name

    def resolve_department(self, text: str) -> Department | None:
        """
        Resolve department by code (CS, EC, ME) or full name.
        """
        if not text:
            return None

        clean = text.strip().upper()
        dept = (
            self.db.query(Department)
            .filter(
                or_(
                    Department.code.ilike(clean),
                    Department.name.ilike(f"%{text.strip()}%"),
                )
            )
            .first()
        )
        return dept

    def resolve_dates(self, text: str) -> tuple[date | None, date | None]:
        """
        Extract start and end date from natural language text.
        Handles:
        - ISO format: '2026-11-02 to 2026-11-04'
        - Month names: 'Nov 2 to Nov 4', 'November 2 - November 4, 2026'
        - Relative references: 'next week', 'next week Mon to Wed', 'this week', 'today'
        """
        ref = self.reference_date

        # Check for ISO date format (YYYY-MM-DD)
        iso_matches = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if len(iso_matches) >= 2:
            try:
                d1 = date.fromisoformat(iso_matches[0])
                d2 = date.fromisoformat(iso_matches[1])
                return (min(d1, d2), max(d1, d2))
            except ValueError:
                pass
        elif len(iso_matches) == 1:
            try:
                d1 = date.fromisoformat(iso_matches[0])
                return (d1, d1)
            except ValueError:
                pass

        # Month name format (e.g. 'Nov 2 to Nov 4' or 'November 2 to 4')
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        }

        month_pattern = r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*(?:to|-|through|until)\s*(?:(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+)?(\d{1,2})(?:st|nd|rd|th)?)?(?:,?\s*(\d{4}))?"
        m_match = re.search(month_pattern, text, re.IGNORECASE)
        if m_match:
            month_str, day1_str, day2_str, year_str = m_match.groups()
            month = month_map.get(month_str.lower(), ref.month)
            year = int(year_str) if year_str else ref.year
            day1 = int(day1_str)
            day2 = int(day2_str) if day2_str else day1
            try:
                d1 = date(year, month, day1)
                d2 = date(year, month, day2)
                return (min(d1, d2), max(d1, d2))
            except ValueError:
                pass

        # Relative phrases
        text_lower = text.lower()

        # 'next week monday to wednesday' / 'monday through wednesday next week'
        if "next week" in text_lower or "next monday" in text_lower:
            days_to_next_mon = (7 - ref.weekday()) % 7
            if days_to_next_mon == 0:
                days_to_next_mon = 7
            next_monday = ref + timedelta(days=days_to_next_mon)

            if "wednesday" in text_lower or "wed" in text_lower:
                return (next_monday, next_monday + timedelta(days=2))  # Mon - Wed
            elif "friday" in text_lower or "fri" in text_lower:
                return (next_monday, next_monday + timedelta(days=4))  # Mon - Fri
            else:
                return (next_monday, next_monday + timedelta(days=4))  # Default next week full Mon-Fri

        if "this week" in text_lower:
            this_monday = ref - timedelta(days=ref.weekday())
            this_friday = this_monday + timedelta(days=4)
            return (this_monday, this_friday)

        if "today" in text_lower:
            return (ref, ref)

        if "tomorrow" in text_lower:
            return (ref + timedelta(days=1), ref + timedelta(days=1))

        return (None, None)

