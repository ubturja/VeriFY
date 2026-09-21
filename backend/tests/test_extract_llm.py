from __future__ import annotations

import pytest

from verify.domain.enums import DocumentKind
from verify.domain.models import Evidence, ExtractedDocument, ExtractedField
from verify.pipeline.extract_llm import ExtractedFields, fill_missing_fields
from verify.providers.base import LLMCallMeta, LLMProvider


class StubLLM(LLMProvider):
    name = "stub"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    async def complete_json(self, *, task, system, user, schema, images=None):
        self.calls += 1
        parsed = schema.model_validate(self.payload)
        return parsed, LLMCallMeta(provider=self.name, model="stub", task=task)


def _seed_doc() -> ExtractedDocument:
    doc = ExtractedDocument(
        kind=DocumentKind.SI,
        attachment="si.txt",
        fields={
            "shipper": ExtractedField(
                name="shipper",
                value="ACME PTE LTD",
                confidence=0.95,
                evidence=Evidence(attachment="si.txt", locator="line:1", snippet="ACME"),
            ),
        },
        raw_text=(
            "SHIPPER: ACME PTE LTD\n"
            "CONSIGNEE: BLANK\n"
            "PORT OF LOADING: SINGAPORE\n"
            "PORT OF DISCHARGE: HAMBURG\n"
            "CONTAINERS: 2 x 40HC\n"
            "GROSS WEIGHT: 24,500 KG\n"
        ),
    )
    return doc


@pytest.mark.asyncio
async def test_fill_missing_fields_populates_blanks_only():
    doc = _seed_doc()
    stub = StubLLM(
        {
            "shipper": "SHOULD NOT OVERRIDE",
            "consignee": "GLOBAL LOGISTICS GMBH",
            "notify_party": "SAME AS CONSIGNEE",
            "port_of_loading": "SINGAPORE",
            "port_of_discharge": "HAMBURG",
            "container_count": "2 x 40HC",
            "gross_weight_kg": "24500",
            "rationale": "read from body",
        }
    )
    filled = await fill_missing_fields(doc, llm=stub)
    assert stub.calls == 1
    assert set(filled) == {
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    }
    assert doc.fields["shipper"].value == "ACME PTE LTD"
    assert doc.fields["shipper"].from_llm is False
    consignee = doc.fields["consignee"]
    assert consignee.value == "GLOBAL LOGISTICS GMBH"
    assert consignee.from_llm is True
    assert consignee.evidence and consignee.evidence.locator == "llm:tier-b"


@pytest.mark.asyncio
async def test_fill_missing_fields_noop_when_complete():
    stub = StubLLM({})
    doc = ExtractedDocument(
        kind=DocumentKind.BL,
        attachment="bl.txt",
        fields={
            name: ExtractedField(name=name, value="x", confidence=0.9)
            for name in [
                "shipper",
                "consignee",
                "notify_party",
                "port_of_loading",
                "port_of_discharge",
                "container_count",
                "gross_weight_kg",
            ]
        },
        raw_text="already complete",
    )
    filled = await fill_missing_fields(doc, llm=stub)
    assert stub.calls == 0
    assert filled == []


@pytest.mark.asyncio
async def test_fill_missing_fields_null_llm_is_safe():
    doc = _seed_doc()
    filled = await fill_missing_fields(doc, llm=None)
    assert filled == []


def test_schema_matches_compare_fields():
    fields = set(ExtractedFields.model_fields) - {"rationale"}
    assert fields == {
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    }
