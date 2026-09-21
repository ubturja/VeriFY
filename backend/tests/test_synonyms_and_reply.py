from __future__ import annotations

from pathlib import Path

from verify.domain.models import FieldComparison
from verify.services.reply import build_reply
from verify.services.shipments import related_cases, shipment_id_for
from verify.services.synonyms import SynonymStore


def test_synonym_learn_and_promote(tmp_path: Path) -> None:
    store = SynonymStore(tmp_path / "syn.json")
    comparisons = [
        FieldComparison(
            field="shipper",
            si_value="ACME PVT LTD",
            bl_value="ACME PRIVATE LIMITED",
            match=False,
            confidence=0.85,
        )
    ]
    remembered = store.learn_from_correction(
        previous_defects=["shipper"],
        current_defects=[],
        comparisons=comparisons,
    )
    assert remembered == ["shipper"]

    fresh = [
        FieldComparison(
            field="shipper",
            si_value="ACME PVT LTD",
            bl_value="ACME PRIVATE LIMITED",
            match=False,
            confidence=0.85,
        )
    ]
    reloaded = SynonymStore(tmp_path / "syn.json")
    promoted = reloaded.apply(fresh)
    assert promoted == ["shipper"]
    assert fresh[0].match is True
    assert fresh[0].note == "learned-synonym"


def test_reply_draft_lists_defects() -> None:
    case = {
        "email_id": "e1",
        "subject": "Please check draft BL",
        "from": "ops@carrier.test",
        "result": {
            "status": "MISMATCH",
            "defect_fields": ["consignee"],
            "comparisons": [
                {
                    "field": "consignee",
                    "si_value": "GLOBAL LOGISTICS",
                    "bl_value": "GLOBAL LOGISTIX",
                    "match": False,
                }
            ],
        },
    }
    draft = build_reply(case, "reviewer@ex.com")
    assert draft["to"] == "ops@carrier.test"
    assert draft["subject"].startswith("Re: ")
    assert "consignee" in draft["body"]
    assert "GLOBAL LOGISTICS" in draft["body"]
    assert draft["body"].strip().endswith("reviewer@ex.com")


def test_shipment_id_and_related_cases() -> None:
    def case(email_id: str, body: str) -> dict:
        return {
            "email_id": email_id,
            "subject": "Draft BL",
            "body": body,
            "attachments": [],
            "result": {},
        }

    target = case("e1", "Please check B/L No. HLC-12345")
    other_same = case("e2", "Regarding BL number HLC-12345")
    other_different = case("e3", "Regarding BL No. XYZ-99999")
    assert shipment_id_for(target) == "bl:HLC-12345"
    matches = related_cases(target, [target, other_same, other_different])
    assert [m["email_id"] for m in matches] == ["e2"]
