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


def test_correct_endpoint_rewrites_verdict(tmp_path, monkeypatch):
    isolated = CaseStore(tmp_path / "state.json")
    monkeypatch.setattr(app_module, "store", isolated)
    isolated.upsert(
        EmailMessage(email_id="e1", sender="ops@test", subject="SI vs BL"),
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
    missing = client.post("/cases/missing/correct", json={"status": "OK"})
    assert missing.status_code == 404
    empty = client.post("/cases/e1/correct", json={})
    assert empty.status_code == 400

    response = client.post(
        "/cases/e1/correct",
        json={"reviewer": "Ada", "status": "OK", "note": "same group"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "OK"
    assert body["result"]["defect_fields"] == []
    assert body["result"]["decided_by"] == "human"
    assert body["review"]["action"] == "correct"
    assert client.get("/metrics").json()["corrected"] == 1
    assert client.get("/audit").json()[-1]["action"] == "correct"
    locked = client.post("/cases/e1/confirm", json={"reviewer": "Ada"})
    assert locked.status_code == 409
    assert client.get("/metrics").json()["corrected"] == 1
    assert client.get("/cases/e1").json()["review"]["action"] == "correct"


def test_submit_inline_attachment(tmp_path, monkeypatch):
    isolated = CaseStore(tmp_path / "state.json")
    monkeypatch.setattr(app_module, "store", isolated)
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")
    client = TestClient(app_module.app)
    response = client.post(
        "/inbox/submit",
        json={
            "email_id": "manual-inline",
            "sender": "ops@test",
            "subject": "thanks",
            "body": "no documents",
            "attachments": [
                {
                    "filename": "note.txt",
                    "content_base64": "aGVsbG8=",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email_id"] == "manual-inline"
    assert body["attachments"][0]["filename"] == "note.txt"
    written = tmp_path / "blob" / "manual" / "manual-inline" / "note.txt"
    assert written.read_bytes() == b"hello"


def test_submit_rejects_path_traversal_email_id(tmp_path, monkeypatch):
    isolated = CaseStore(tmp_path / "state.json")
    monkeypatch.setattr(app_module, "store", isolated)
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")
    client = TestClient(app_module.app)
    response = client.post(
        "/inbox/submit",
        json={
            "email_id": "../../etc/passwd",
            "sender": "ops@test",
            "subject": "thanks",
            "body": "no documents",
            "attachments": [{"filename": "note.txt", "content_base64": "aGVsbG8="}],
        },
    )
    assert response.status_code == 400
    assert "Invalid email id" in str(response.json()["detail"])
    assert not (tmp_path / "etc").exists()
    assert list((tmp_path / "blob").rglob("*")) == []


def test_imap_poll_requires_app_password(monkeypatch):
    monkeypatch.setattr(app_module.settings, "imap_app_password", "")
    client = TestClient(app_module.app)
    response = client.post("/inbox/imap")
    assert response.status_code == 400
    assert "IMAP_APP_PASSWORD" in response.json()["detail"]


def test_imap_poll_maps_network_errors(monkeypatch):
    async def boom(*_args, **_kwargs):
        raise OSError("nodename nor servname provided")

    monkeypatch.setattr(app_module, "poll_mailbox", boom)
    client = TestClient(app_module.app)
    response = client.post("/inbox/imap")
    assert response.status_code == 502
    assert "IMAP unavailable" in response.json()["detail"]
