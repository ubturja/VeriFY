"""LLM-as-judge for the party-name gray band.

When two shipper / consignee / notify_party strings are similar but not
identical after normalization, the rule engine calls them a MISMATCH. Many
of those are the same legal entity written slightly differently (branch code,
Pte Ltd vs Private Limited, capitalisation of a joint venture). We ask the
LLM to decide only for the ambiguous middle band. Anything the LLM cannot
justify stays a MISMATCH, so the judge only lowers false-positive defects,
it never introduces new ones.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from verify.domain.models import FieldComparison
from verify.providers.base import LLMProvider
from verify.text.normalize import fold_party

PARTY_FIELDS = {"shipper", "consignee", "notify_party"}
LOW_BAND = 80
HIGH_BAND = 96


class JudgeVerdict(BaseModel):
    same_entity: bool
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


_SYSTEM = (
    "You compare two party names from shipping documents and decide if they "
    "refer to the same legal entity. Say true only when the difference is a "
    "spelling variant, punctuation, branch/office suffix, or a well-known "
    "trading name of the same registered company. Say false for different "
    "companies even in the same group. Never guess."
)


def _in_gray_band(item: FieldComparison) -> bool:
    if item.field not in PARTY_FIELDS:
        return False
    if item.match is not False:
        return False
    if not item.si_value or not item.bl_value:
        return False
    if fold_party(item.si_value) == fold_party(item.bl_value):
        return False
    score = fuzz.ratio(fold_party(item.si_value), fold_party(item.bl_value))
    return LOW_BAND <= score < HIGH_BAND


async def resolve_gray_band(
    comparisons: list[FieldComparison],
    *,
    llm: LLMProvider | None,
) -> list[str]:
    """Rewrite gray-band party rows in place. Returns the list of fields that
    the LLM flipped from MISMATCH to MATCH."""
    if llm is None:
        return []
    flipped: list[str] = []
    for item in comparisons:
        if not _in_gray_band(item):
            continue
        user = (
            f"Field: {item.field}\n"
            f"SI value: {item.si_value}\n"
            f"BL value: {item.bl_value}"
        )
        try:
            parsed, _ = await llm.complete_json(
                task="judge-party",
                system=_SYSTEM,
                user=user,
                schema=JudgeVerdict,
            )
        except Exception:
            continue
        verdict = parsed if isinstance(parsed, JudgeVerdict) else JudgeVerdict.model_validate(parsed)
        if verdict.same_entity and verdict.confidence >= 0.75:
            item.match = True
            item.confidence = max(item.confidence, verdict.confidence)
            item.note = f"llm-judge:same-entity ({verdict.rationale[:120]})"
            flipped.append(item.field)
        else:
            item.note = f"llm-judge:distinct ({verdict.rationale[:120]})"
    return flipped
