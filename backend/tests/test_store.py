import pytest

from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, PipelineResult
from verify.services.store import CaseStore


def _row(store: CaseStore, email_id: str = "e1") -> None:
    email = EmailMessage(email_id=email_id, sender="desk@carrier.test", subject="Draft BL")
    result = PipelineResult(
        email_id=email_id,
        category=Category.BL_COMPARISON,
        status=Status.MISMATCH,
        has_defect=True,
        defect_fields=["shipper"],
        decided_by=DecidedBy.RULE,
    )
    store.upsert(email, result)


def test_confirm_does_not_change_scoreboard_fields(tmp_path):
    path = tmp_path / "state.json"
    store = CaseStore(path)
    _row(store)
    row = store.confirm("e1", reviewer="Ada", note="matches SI")
    assert row is not None
    assert row["result"]["category"] == "BL_COMPARISON"
    assert row["result"]["status"] == "MISMATCH"
    assert row["result"]["has_defect"] is True
    assert row["result"]["defect_fields"] == ["shipper"]
    assert row["result"]["decided_by"] == "rule"
    assert row["review"]["action"] == "confirm"
    assert row["review"]["by"] == "Ada"
    assert row["review"]["accepted_status"] == "MISMATCH"

    replayed = CaseStore(path)
    kept = replayed.get("e1")
    assert kept is not None
    assert kept["review"]["by"] == "Ada"
    assert kept["result"]["status"] == "MISMATCH"


def test_upsert_keeps_confirm_until_retry(tmp_path):
    store = CaseStore(tmp_path / "state.json")
    _row(store)
    store.confirm("e1", reviewer="Ada")
    email = store.as_email("e1")
    assert email is not None
    result = PipelineResult(
        email_id="e1",
        category=Category.BL_COMPARISON,
        status=Status.MISMATCH,
        decided_by=DecidedBy.RULE,
    )
    store.upsert(email, result)
    assert store.get("e1")["review"]["by"] == "Ada"
    store.upsert(email, result, reset_review=True)
    assert store.get("e1")["review"] is None
    assert store.audit()[-1]["action"] == "confirm"


def test_confirm_unknown_case_returns_none(tmp_path):
    store = CaseStore(tmp_path / "missing.json")
    assert store.confirm("nope", reviewer="Ada") is None


def test_correct_overrides_scoreboard_and_sets_human(tmp_path):
    path = tmp_path / "state.json"
    store = CaseStore(path)
    _row(store)
    row = store.correct(
        "e1",
        reviewer="Ada",
        status="OK",
        note="shipper names are the same legal entity",
    )
    assert row is not None
    assert row["result"]["status"] == "OK"
    assert row["result"]["has_defect"] is False
    assert row["result"]["defect_fields"] == []
    assert row["result"]["decided_by"] == "human"
    assert row["result"]["category"] == "BL_COMPARISON"
    assert row["review"]["action"] == "correct"
    assert row["review"]["previous"]["status"] == "MISMATCH"

    replayed = CaseStore(path)
    kept = replayed.get("e1")
    assert kept is not None
    assert kept["result"]["status"] == "OK"
    assert kept["result"]["decided_by"] == "human"
    assert replayed.metrics()["corrected"] == 1


def test_correct_mismatch_requires_defect_fields(tmp_path):
    store = CaseStore(tmp_path / "state.json")
    email = EmailMessage(email_id="e1", sender="ops@test", subject="ok")
    store.upsert(
        email,
        PipelineResult(
            email_id="e1",
            category=Category.GENERAL,
            status=Status.OK,
            decided_by=DecidedBy.RULE,
        ),
    )
    with pytest.raises(ValueError, match="defect field"):
        store.correct("e1", reviewer="Ada", status="MISMATCH")
    row = store.correct("e1", reviewer="Ada", status="MISMATCH", defect_fields=["consignee"])
    assert row["result"]["has_defect"] is True
    assert row["result"]["defect_fields"] == ["consignee"]


def test_sqlite_store_survives_reload(tmp_path):
    path = tmp_path / "verify.sqlite"
    store = CaseStore(path)
    _row(store)
    store.confirm("e1", reviewer="Ada")
    replayed = CaseStore(path)
    kept = replayed.get("e1")
    assert kept is not None
    assert kept["review"]["by"] == "Ada"
    assert kept["result"]["status"] == "MISMATCH"


def test_confirm_after_correct_is_rejected(tmp_path):
    store = CaseStore(tmp_path / "state.json")
    _row(store)
    store.correct("e1", reviewer="Ada", status="OK")
    with pytest.raises(ValueError, match="already corrected"):
        store.confirm("e1", reviewer="Ada")
    assert store.get("e1")["review"]["action"] == "correct"
    assert store.metrics()["corrected"] == 1
    assert store.metrics()["confirmed"] == 0
