from fastapi.testclient import TestClient

from verify.api import app as app_module
from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, PipelineResult
from verify.services.store import CaseStore


def test_confirm_endpoint_stamps_review_only(tmp_path, monkeypatch):
    isolated = CaseStore(tmp_path / "state.json")
    monkeypatch.setattr(app_module, "store", isolated)
    email = EmailMessage(email_id="e1", sender="ops@test", subject="SI vs BL")
    isolated.upsert(
        email,
        PipelineResult(
            email_id="e1",
            category=Category.BL_COMPARISON,
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=["consignee"],
            decided_by=DecidedBy.RULE,
        ),
    )
    client = TestClient(app_module.app)
    missing = client.post("/cases/missing/confirm", json={})
    assert missing.status_code == 404

    response = client.post("/cases/e1/confirm", json={"reviewer": "Ada", "note": "accepted"})
    assert response.status_code == 200
    body = response.json()
    assert body["review"]["action"] == "confirm"
    assert body["review"]["by"] == "Ada"
    assert body["review"]["note"] == "accepted"
    assert body["result"]["status"] == "MISMATCH"
    assert body["result"]["defect_fields"] == ["consignee"]
    assert body["result"]["decided_by"] == "rule"

    audit = client.get("/audit").json()
    assert audit[-1]["action"] == "confirm"
    assert client.get("/metrics").json()["confirmed"] == 1


def test_imap_poll_requires_app_password(monkeypatch):
    monkeypatch.setattr(app_module.settings, "imap_app_password", "")
    client = TestClient(app_module.app)
    response = client.post("/inbox/imap")
    assert response.status_code == 400
    assert "IMAP_APP_PASSWORD" in response.json()["detail"]
