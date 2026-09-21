"""Font-split recovery for two-column PDFs, and the local party model."""

from __future__ import annotations

from pathlib import Path

import pytest

from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, FieldComparison, PipelineResult
from verify.pipeline.extract import _values_from_chars, extract_from_bytes
from verify.pipeline.judge import resolve_gray_band
from verify.services.party_model import PartyModel

_SAME = [
    ("shipper", "ACME PRIVATE LIMITED", "ACME PVT LTD", True),
    ("shipper", "NORDIC PRIVATE LIMITED", "NORDIC PVT LTD", True),
    ("consignee", "HELIX PRIVATE LIMITED", "HELIX PVT LTD", True),
]
_DISTINCT = [
    ("notify_party", "GLOBAL MARINE SERVICES LTD", "GLOBAL MINING SERVICES LTD", False),
    ("notify_party", "OCEANIC BULK CARRIERS LTD", "OCEANIC BULK TRADERS LTD", False),
    ("shipper", "EASTERN TIMBER EXPORTS LTD", "EASTERN TIMBER IMPORTS LTD", False),
]


def _examples() -> list[dict]:
    rows = []
    for field, left, right, same in [*_SAME, *_DISTINCT]:
        rows.append({"field": field, "si_value": left, "bl_value": right, "same": same})
    return rows


def _chars(label: str, value: str, *, top: float = 201.0) -> list[dict]:
    glyphs: list[dict] = []
    x = 40.0
    for char in label:
        glyphs.append({"text": char, "top": top, "x0": x, "fontname": "Helvetica-Bold"})
        x += 6
    x = 180.0
    for char in value:
        glyphs.append({"text": char, "top": top, "x0": x, "fontname": "Helvetica"})
        x += 6
    return glyphs


def test_font_split_keeps_the_notify_label_out_of_the_name():
    chars = _chars("Notify Party/Intermediate Consignee", "TOPKOPY MIDDLE EAST FZE")
    found = _values_from_chars(chars)
    assert found["notify_party"] == "TOPKOPY MIDDLE EAST FZE"


def test_seed_pdf_notify_parties_stay_distinct():
    root = Path(__file__).resolve().parents[2]
    si_path = root / "artifacts" / "seeds" / "seed-3" / "attachments" / "email_1042_SI.pdf"
    bl_path = root / "artifacts" / "seeds" / "seed-3" / "attachments" / "email_1042_BL.pdf"
    if not si_path.is_file() or not bl_path.is_file():
        pytest.skip("seed-3 attachments are not on disk")
    si = extract_from_bytes("email_1042_SI.pdf", si_path.read_bytes())
    bl = extract_from_bytes("email_1042_BL.pdf", bl_path.read_bytes())
    si_notify = (si.fields.get("notify_party").value if si.fields.get("notify_party") else "") or ""
    bl_notify = (bl.fields.get("notify_party").value if bl.fields.get("notify_party") else "") or ""
    assert "intermediate" not in si_notify.casefold()
    assert "consignee" not in si_notify.casefold()
    assert si_notify.casefold() != bl_notify.casefold()
    assert "topkopy" in si_notify.casefold()
    assert "roxcel" in bl_notify.casefold()


def test_retrain_writes_a_model_the_next_load_uses(tmp_path: Path):
    path = tmp_path / "party_model.json"
    first = PartyModel(path)
    assert first.retrain(_examples()[:2]) is None
    version = first.retrain(_examples())
    assert version
    loaded = PartyModel(path)
    assert loaded.ready
    assert loaded.version == version
    same = loaded.predict("ACME PRIVATE LIMITED", "ACME PVT LTD")
    distinct = loaded.predict("GLOBAL MARINE SERVICES LTD", "GLOBAL MINING SERVICES LTD")
    assert same is not None and same.same is True
    assert distinct is not None and distinct.same is False


@pytest.mark.asyncio
async def test_gray_band_uses_the_trained_model_without_an_llm(tmp_path: Path):
    model = PartyModel(tmp_path / "party_model.json")
    model.retrain(_examples())
    gray = FieldComparison(
        field="shipper",
        si_value="ACME PRIVATE LIMITED",
        bl_value="ACME PVT LTD",
        match=False,
        confidence=0.85,
    )
    outside = FieldComparison(
        field="shipper",
        si_value="NORTHWIND LOGISTICS LLC",
        bl_value="SOUTHWIND TRADING LLC",
        match=False,
        confidence=0.85,
    )
    flipped = await resolve_gray_band([gray, outside], llm=None, party_model=model)
    assert flipped == ["shipper"]
    assert gray.match is True
    assert gray.note is not None and gray.note.startswith("local-model:same-entity@")
    assert outside.match is False
    assert outside.note is None


def test_correction_retrains_from_the_stored_examples(auth_client):
    few = auth_client.tenant.fewshots
    for field, left, right, same in [*_SAME, *_DISTINCT]:
        few.remember(field=field, si_value=left, bl_value=right, same=same)
    auth_client.tenant.store.upsert(
        EmailMessage(email_id="model-1", sender="a@b.c", subject="s"),
        PipelineResult(
            email_id="model-1",
            category=Category.BL_COMPARISON,
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=["shipper"],
            decided_by=DecidedBy.RULE,
            comparisons=[
                FieldComparison(
                    field="shipper",
                    si_value="ACME PRIVATE LIMITED",
                    bl_value="ACME PVT LTD",
                    match=False,
                )
            ],
        ),
    )
    response = auth_client.post(
        "/cases/model-1/correct",
        json={"status": "OK", "defect_fields": [], "note": "same party"},
    )
    assert response.status_code == 200
    loaded = PartyModel(few.path.with_name("party_model.json"))
    assert loaded.ready
    assert loaded.n_examples >= 4
