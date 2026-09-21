from __future__ import annotations

import pytest

from verify.domain.models import FieldComparison
from verify.pipeline.judge import JudgeVerdict, resolve_gray_band
from verify.providers.base import LLMCallMeta, LLMProvider


class StubJudge(LLMProvider):
    name = "stub-judge"

    def __init__(self, verdict: dict) -> None:
        self.verdict = verdict
        self.calls = 0

    async def complete_json(self, *, task, system, user, schema, images=None):
        self.calls += 1
        return schema.model_validate(self.verdict), LLMCallMeta(
            provider=self.name, model="stub", task=task
        )


@pytest.mark.asyncio
async def test_judge_flips_gray_band_same_entity():
    comparison = FieldComparison(
        field="shipper",
        si_value="ACME PRIVATE LIMITED",
        bl_value="ACME PVT LTD",
        match=False,
        confidence=0.85,
    )
    stub = StubJudge({"same_entity": True, "confidence": 0.9, "rationale": "same abbrev"})
    flipped = await resolve_gray_band([comparison], llm=stub)
    assert flipped == ["shipper"]
    assert comparison.match is True
    assert "llm-judge" in (comparison.note or "")


@pytest.mark.asyncio
async def test_judge_keeps_mismatch_when_distinct():
    comparison = FieldComparison(
        field="shipper",
        si_value="ACME PRIVATE LIMITED",
        bl_value="ACME LOGISTICS PTE LTD",
        match=False,
        confidence=0.85,
    )
    stub = StubJudge({"same_entity": False, "confidence": 0.9, "rationale": "different registered names"})
    flipped = await resolve_gray_band([comparison], llm=stub)
    assert flipped == []
    assert comparison.match is False


@pytest.mark.asyncio
async def test_judge_skips_rows_outside_gray_band():
    already_matched = FieldComparison(field="consignee", si_value="A", bl_value="A", match=True)
    unrelated = FieldComparison(field="port_of_loading", si_value="SIN", bl_value="HKG", match=False)
    stub = StubJudge({"same_entity": True, "confidence": 0.9, "rationale": "x"})
    flipped = await resolve_gray_band([already_matched, unrelated], llm=stub)
    assert flipped == []
    assert stub.calls == 0


def test_verdict_model_bounds():
    v = JudgeVerdict.model_validate({"same_entity": True, "confidence": 0.5})
    assert 0 <= v.confidence <= 1
