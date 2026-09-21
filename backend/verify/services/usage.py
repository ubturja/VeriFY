"""Record LLM calls made during one pipeline run.

A context variable keeps the collector off the function signatures of every
extractor. `RecordingLLM` is the only wrapper; rules-only runs record nothing.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel

from verify.providers.base import LLMCallMeta, LLMProvider

_current: ContextVar[list[LLMCallMeta] | None] = ContextVar("verify_llm_usage", default=None)

# Published list prices used only as an estimate. Not an invoice.
INPUT_USD_PER_MILLION = 0.10
OUTPUT_USD_PER_MILLION = 0.40


class UsageSummary(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    models: list[str] = []

    def cost_usd(self) -> float:
        return (
            self.input_tokens * INPUT_USD_PER_MILLION
            + self.output_tokens * OUTPUT_USD_PER_MILLION
        ) / 1_000_000


def start_usage() -> Any:
    bucket: list[LLMCallMeta] = []
    return _current.set(bucket)


def finish_usage(token: Any) -> UsageSummary:
    bucket = _current.get() or []
    _current.reset(token)
    models: list[str] = []
    for call in bucket:
        label = f"{call.provider}:{call.model}"
        if label not in models:
            models.append(label)
    return UsageSummary(
        llm_calls=len(bucket),
        input_tokens=sum(call.input_tokens for call in bucket),
        output_tokens=sum(call.output_tokens for call in bucket),
        models=models,
    )


class RecordingLLM(LLMProvider):
    """Delegates to an inner provider and appends each call to the active bucket."""

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.name = inner.name

    async def complete_json(self, **kwargs: Any):
        parsed, meta = await self.inner.complete_json(**kwargs)
        bucket = _current.get()
        if bucket is not None:
            bucket.append(meta)
        return parsed, meta
