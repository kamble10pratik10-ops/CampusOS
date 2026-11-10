"""
Provider-independent LLM interface (Milestone M6).

Defines the contract for language models to interface with Campus OS.
Enforces that LLMs are limited to language translation, intent extraction,
and human-readable explanation generation.
Operational decisions are strictly executed by deterministic solvers and rules.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import Settings, settings
from app.schemas.llm import ExplanationRequest, ParsedIntent


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'groq', 'deterministic_fallback')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str | None:
        """Model identifier (e.g., 'qwen/qwen3.8-27b')."""
        pass

    @abstractmethod
    async def parse_intent(
        self,
        text: str,
        entity_context: dict[str, Any] | None = None,
    ) -> ParsedIntent:
        """
        Extract structured user intent and proposed parameters from natural language.
        """
        pass

    @abstractmethod
    async def generate_explanation(
        self,
        request: ExplanationRequest,
    ) -> str:
        """
        Produce a readable, evidence-grounded explanation of a verified decision.
        """
        pass


def get_llm_provider(app_settings: Settings | None = None) -> LLMProvider:
    """
    Factory to instantiate the configured LLM provider.
    Defaults to DeterministicFallback if Groq is not configured.
    """
    cfg = app_settings or settings
    from app.llm.fallback import DeterministicFallbackProvider

    if cfg.LLM_PROVIDER == "groq" and cfg.GROQ_API_KEY:
        try:
            from app.llm.groq_client import GroqClientProvider
            return GroqClientProvider(
                api_key=cfg.GROQ_API_KEY,
                model=cfg.GROQ_MODEL or "qwen/qwen3.8-27b",
                fallback=DeterministicFallbackProvider(),
            )
        except Exception as e:
            # Fall back safely
            return DeterministicFallbackProvider()

    return DeterministicFallbackProvider()

