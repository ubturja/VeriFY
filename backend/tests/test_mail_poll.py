import pytest

from verify.config import Settings
from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, PipelineResult
from verify.providers.mail.imap import rfc822_from_payload
from verify.services import mail_poll
from verify.services.mail_poll import ingest_emails, poll_mailbox
from verify.services.store import CaseStore


def test_rfc822_from_payload_reads_tuple_body():
    payload = [(b"1 (UID 12 RFC822 {5}", b"From:"), b")"]
    assert rfc822_from_payload(payload) == b"From:"


@pytest.mark.asyncio
async def test_ingest_skips_existing(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "state.json")
    email = EmailMessage(email_id="keep", sender="ops@test", subject="already in")
    store.upsert(
        email,
        PipelineResult(
            email_id="keep",
            category=Category.GENERAL,
            status=Status.OK,
            decided_by=DecidedBy.RULE,
        ),
    )
    store.confirm("keep", reviewer="Ada")

    async def fake_pipeline(*_args, **_kwargs):
        raise AssertionError("existing mail must not be reprocessed")

    monkeypatch.setattr(mail_poll, "run_pipeline", fake_pipeline)
    ingested = await ingest_emails(
        [email],
        store=store,
        read=lambda _path: b"",
        llm=None,
        skip_existing=True,
    )
    assert ingested == 0
    assert store.get("keep")["review"]["by"] == "Ada"


@pytest.mark.asyncio
async def test_poll_marks_seen_only_after_success(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / "state.json")
    ok_mail = EmailMessage(email_id="ok1", sender="ops@test", subject="hello", body="hi")
    fail_mail = EmailMessage(email_id="fail1", sender="ops@test", subject="boom", body="x")
    marked: list[bytes] = []

    class FakeSource:
        configured = True

        def __init__(self, _settings):
            pass

        def fetch_messages(self, *, unseen_only: bool = True):
            return [(b"11", ok_mail), (b"12", fail_mail)]

        def mark_seen(self, uids: list[bytes]) -> None:
            marked.extend(uids)

    async def fake_pipeline(email, _read, llm=None):
        if email.email_id == "fail1":
            raise RuntimeError("pipeline failed")
        return PipelineResult(
            email_id=email.email_id,
            category=Category.GENERAL,
            status=Status.OK,
            decided_by=DecidedBy.RULE,
        )

    monkeypatch.setattr(mail_poll, "ImapMailSource", FakeSource)
    monkeypatch.setattr(mail_poll, "run_pipeline", fake_pipeline)
    settings = Settings()
    result = await poll_mailbox(settings, store=store, read=lambda _path: b"", llm=None)
    assert result["ingested"] == 1
    assert result["failed"] == 1
    assert marked == [b"11"]
    assert store.get("ok1") is not None
    assert store.get("fail1") is None
