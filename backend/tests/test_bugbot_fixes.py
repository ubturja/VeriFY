"""Regression tests for the four Bugbot findings from the initial review."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from verify.api import app as app_module
from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, FieldComparison, PipelineResult
from verify.services import mail_poll as mail_poll_module
from verify.services.mail_poll import poll_mailbox
from verify.services.store import CaseStore
from verify.services.synonyms import SynonymStore
from verify.services.tenants import secret_key_or_dev


def test_secret_key_or_dev_generates_key_in_cloud_when_not_required(tmp_path: Path) -> None:
    generated = secret_key_or_dev("", artifacts_root=tmp_path, env="cloud")
    assert generated
    key_file = tmp_path / ".secret_key"
    assert key_file.is_file()
    reread = secret_key_or_dev("", artifacts_root=tmp_path, env="cloud")
    assert reread == generated


def test_secret_key_or_dev_hard_fails_when_required(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="VERIFY_SECRET_KEY is required"):
        secret_key_or_dev("", artifacts_root=tmp_path, env="cloud", require=True)


def test_health_does_not_leak_mailbox_state() -> None:
    """Bugbot: /health used to expose poll_state['last_error']."""
    client = TestClient(app_module.app)
    body = client.get("/health").json()
    assert set(body.keys()) == {
        "status",
        "service",
        "env",
        "llm",
        "mailboxes",
        "imap_autopoll",
    }
    assert "last_error" not in body
    assert "imap_last_error" not in body
    assert "imap_last_poll" not in body


def test_manual_submit_isolates_blobs_per_tenant(tmp_path, monkeypatch, isolated_tenants):
    """Two tenants uploading the same email_id must not overwrite each other."""
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")

    alice = TestClient(app_module.app)
    bob = TestClient(app_module.app)
    alice_tenant = isolated_tenants.ensure("alice@ex.com")
    bob_tenant = isolated_tenants.ensure("bob@ex.com")
    alice.headers.update({"Authorization": f"Bearer {isolated_tenants.issue_token(alice_tenant)}"})
    bob.headers.update({"Authorization": f"Bearer {isolated_tenants.issue_token(bob_tenant)}"})

    payload = {
        "email_id": "manual-collide",
        "subject": "clash",
        "body": "",
        "attachments": [{"filename": "note.txt", "content_base64": "YWxpY2U="}],  # alice
    }
    assert alice.post("/inbox/submit", json=payload).status_code == 200
    payload["attachments"] = [{"filename": "note.txt", "content_base64": "Ym9i"}]  # bob
    assert bob.post("/inbox/submit", json=payload).status_code == 200

    alice_file = (
        tmp_path / "blob" / "manual" / alice_tenant.slug / "manual-collide" / "note.txt"
    )
    bob_file = tmp_path / "blob" / "manual" / bob_tenant.slug / "manual-collide" / "note.txt"
    assert alice_file.read_bytes() == b"alice"
    assert bob_file.read_bytes() == b"bob"
    assert alice_tenant.slug != bob_tenant.slug


@pytest.mark.asyncio
async def test_poll_mailbox_applies_tenant_synonyms(tmp_path, monkeypatch):
    """Bugbot: IMAP ingest previously skipped tenant synonym promotion."""

    store = CaseStore(tmp_path / "state.json")
    synonyms = SynonymStore(tmp_path / "syn.json")
    synonyms.remember("shipper", "ACME PVT LTD", "ACME PRIVATE LIMITED")

    inbound = EmailMessage(email_id="m1", sender="ops@test", subject="draft bl")

    class FakeSource:
        configured = True

        def __init__(self, _settings, **_kwargs):
            pass

        def fetch_messages(self, *, unseen_only: bool = True):
            return [(b"1", inbound)]

        def mark_seen(self, uids):
            pass

    async def fake_pipeline(email, _read, llm=None, **_kwargs):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=["shipper"],
            decided_by=DecidedBy.RULE,
            comparisons=[
                FieldComparison(
                    field="shipper",
                    si_value="ACME PVT LTD",
                    bl_value="ACME PRIVATE LIMITED",
                    match=False,
                    confidence=0.85,
                )
            ],
        )

    monkeypatch.setattr(mail_poll_module, "ImapMailSource", FakeSource)
    monkeypatch.setattr(mail_poll_module, "run_pipeline", fake_pipeline)

    result = await poll_mailbox(
        app_module.settings,
        store=store,
        read=lambda _p: b"",
        llm=None,
        username="poll@test",
        app_password="app-pass",
        synonyms=synonyms,
    )
    assert result["ingested"] == 1
    stored = store.get("m1")
    assert stored is not None
    assert stored["result"]["status"] == "OK"
    assert stored["result"]["defect_fields"] == []
    assert any(note.startswith("synonyms-applied") for note in stored["result"].get("notes") or [])
