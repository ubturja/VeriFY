"""Tier B extraction: ask an LLM to fill fields the rule extractor could not
parse. Used only after the deterministic parser has done its best. Every LLM
value is stamped with lower confidence and evidence that names the document,
so nothing silently overrides a rule-parsed value."""

from __future__ import annotations

import contextlib
from typing import Any

from pydantic import BaseModel, Field

from verify.domain.enums import COMPARE_FIELDS
from verify.domain.models import Evidence, ExtractedDocument, ExtractedField
from verify.providers.base import LLMProvider
from verify.text.normalize import collapse_ws, is_blank_token, party_name_only

_SYSTEM = (
    "You extract shipping-document fields. Return only what the document actually says. "
    "Never invent values. If a field is not present or is unreadable, return null for it. "
    "For party fields (shipper, consignee, notify_party) return only the company name, "
    "not the address block. Weights should be in kilograms."
)


class ExtractedFields(BaseModel):
    shipper: str | None = None
    consignee: str | None = None
    notify_party: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    container_count: str | None = None
    gross_weight_kg: str | None = None
    rationale: str = Field(default="")


def _blank_or_missing(doc: ExtractedDocument, field: str) -> bool:
    existing = doc.fields.get(field)
    if existing is None:
        return True
    if existing.blank_token:
        return True
    return existing.value is None or is_blank_token(existing.value)


def missing_fields(doc: ExtractedDocument) -> list[str]:
    return [name for name in COMPARE_FIELDS if _blank_or_missing(doc, name)]


async def fill_missing_fields(
    doc: ExtractedDocument,
    *,
    llm: LLMProvider | None,
    max_chars: int = 6000,
) -> list[str]:
    """Populate blank/missing fields in ``doc`` using the LLM. Returns the list
    of fields that were filled."""
    if llm is None:
        return []
    missing = missing_fields(doc)
    if not missing:
        return []
    text = (doc.raw_text or "").strip()
    if not text:
        return []
    snippet = text[:max_chars]
    user = (
        f"Document filename: {doc.attachment}\n"
        f"Document kind guess: {doc.kind.value if doc.kind else 'unknown'}\n"
        f"Fields still missing: {', '.join(missing)}\n\n"
        f"---\n{snippet}\n---"
    )
    try:
        parsed, _ = await llm.complete_json(
            task="extract-missing-fields",
            system=_SYSTEM,
            user=user,
            schema=ExtractedFields,
        )
    except Exception:
        return []
    payload: dict[str, Any] = parsed.model_dump() if isinstance(parsed, BaseModel) else dict(parsed)
    filled: list[str] = []
    for name in missing:
        value = payload.get(name)
        if not isinstance(value, str):
            continue
        cleaned = collapse_ws(value)
        if name in {"shipper", "consignee", "notify_party"}:
            cleaned = collapse_ws(party_name_only(cleaned) or "")
        if not cleaned or is_blank_token(cleaned):
            continue
        with contextlib.suppress(Exception):
            existing = doc.fields.get(name)
            evidence = Evidence(
                attachment=doc.attachment,
                locator="llm:tier-b",
                snippet=cleaned[:200],
            )
            doc.fields[name] = ExtractedField(
                name=name,
                value=cleaned,
                confidence=0.55,
                blank_token=False,
                evidence=evidence,
                from_llm=True,
            )
            filled.append(name)
            _ = existing  # kept for future audit if we need to record the prior blank
    return filled
