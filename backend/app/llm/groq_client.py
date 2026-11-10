"""
Groq API Client Provider (Milestone M6).

Integrates the Groq API as an OpenAI-compatible natural language interface.
Uses current official models (e.g. qwen/qwen3.8-27b) with:
- Strict JSON output parsing
- Bounded retries and 10s timeouts
- Automatic seamless fallback to DeterministicFallbackProvider on any error, timeout, or rate-limit
- Guaranteed isolation: LLM output is never allowed to determine feasibility or mutate operational tables.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.llm.interface import LLMProvider
from app.schemas.llm import ExplanationRequest, IntentTypeEnum, ParsedIntent

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqClientProvider(LLMProvider):
    """Groq-hosted LLM provider with graceful deterministic fallback."""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen/qwen3.8-27b",
        fallback: LLMProvider | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback = fallback
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self.model

    async def _post_chat_completion(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        """Execute chat completion request with bounded retries."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(GROQ_API_URL, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
                    elif resp.status_code == 429 and attempt < self.max_retries:
                        logger.warning("Groq rate limit hit (429), retrying...")
                        continue
                    else:
                        raise RuntimeError(f"Groq API returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                last_err = e
                logger.warning(f"Groq API attempt {attempt+1} failed: {e}")

        raise last_err or RuntimeError("Groq request failed after retries")

    async def parse_intent(
        self,
        text: str,
        entity_context: dict[str, Any] | None = None,
    ) -> ParsedIntent:
        """
        Extract structured user intent and proposed parameters using Groq.
        Falls back to DeterministicFallbackProvider on any failure.
        """
        system_prompt = (
            "You are the intent parser for Campus OS, an academic decision support system.\n"
            "Analyze the user's natural language request and extract operational parameters.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "intent_type": "leave_simulation" | "check_conflicts" | "check_workload" | "clarification_needed" | "general_query",\n'
            '  "faculty_name_or_code": string or null,\n'
            '  "start_date": "YYYY-MM-DD" or null,\n'
            '  "end_date": "YYYY-MM-DD" or null,\n'
            '  "department_code": "CS" | "EC" | "ME" or null,\n'
            '  "confidence": float between 0.0 and 1.0,\n'
            '  "missing_fields": list of missing parameter strings,\n'
            '  "clarification_prompt": string or null\n'
            "}\n"
            "Reference context: Today is 2026-10-26 (Monday). Next week is 2026-11-02 (Monday) to 2026-11-06 (Friday).\n"
            "Do NOT include markdown fences, explanations, or commentary outside the JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        try:
            raw_response = await self._post_chat_completion(messages, temperature=0.1)
            # Clean possible markdown fences
            clean_json = raw_response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json)

            intent_str = parsed.get("intent_type", "leave_simulation")
            try:
                intent_type = IntentTypeEnum(intent_str)
            except ValueError:
                intent_type = IntentTypeEnum.leave_simulation

            return ParsedIntent(
                intent_type=intent_type,
                faculty_name_or_code=parsed.get("faculty_name_or_code"),
                start_date=parsed.get("start_date"),
                end_date=parsed.get("end_date"),
                department_code=parsed.get("department_code"),
                confidence=float(parsed.get("confidence", 0.95)),
                missing_fields=parsed.get("missing_fields", []),
                clarification_prompt=parsed.get("clarification_prompt"),
                raw_query=text,
            )
        except Exception as e:
            logger.warning(f"Groq parse_intent failed ({e}); falling back to deterministic parser.")
            if self.fallback:
                return await self.fallback.parse_intent(text, entity_context)
            raise

    async def generate_explanation(
        self,
        request: ExplanationRequest,
    ) -> str:
        """
        Produce a readable, evidence-grounded explanation of a verified decision using Groq.
        Falls back to DeterministicFallbackProvider on any failure.
        """
        system_prompt = (
            "You are the explanation assistant for Campus OS.\n"
            "Explain the already-computed, independently verified timetable decision clearly and professionally.\n"
            "STRICT RULES:\n"
            "1. Ground all numbers strictly in the provided data. NEVER invent faculty, classes, or conflicts.\n"
            "2. Note that the decision was independently verified by the deterministic Critic engine with 0 new hard violations.\n"
            "3. State that operational timetable tables remain unchanged (HC-10 non-mutation guarantee).\n"
            "4. Keep the explanation concise, professional, and well-structured using markdown."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.model_dump_json(indent=2)},
        ]

        try:
            return await self._post_chat_completion(messages, temperature=0.2)
        except Exception as e:
            logger.warning(f"Groq generate_explanation failed ({e}); falling back to deterministic generator.")
            if self.fallback:
                return await self.fallback.generate_explanation(request)
            raise

