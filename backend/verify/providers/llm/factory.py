from __future__ import annotations

from pydantic import BaseModel

from verify.config import Settings
from verify.providers.base import LLMCallMeta, LLMProvider


class NullLLMProvider(LLMProvider):
    """Used when no API key is configured. Pipeline stays on rules and parsers."""

    name = "null"

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        images: list[bytes] | None = None,
    ) -> tuple[BaseModel, LLMCallMeta]:
        raise RuntimeError("LLM is not configured. Set GEMINI_API_KEY or GROQ_API_KEY.")


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_primary == "gemini" and settings.gemini_api_key:
        from verify.providers.llm.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_classify_model)
    if settings.groq_api_key:
        from verify.providers.llm.groq import GroqProvider

        return GroqProvider(settings.groq_api_key, settings.groq_text_model)
    return NullLLMProvider()
