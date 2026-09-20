from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from verify.config import get_settings
from verify.domain.models import AttachmentRef, EmailMessage
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.llm.factory import NullLLMProvider, build_llm
from verify.providers.mail.hackathon import HackathonMailSource
from verify.providers.mail.imap import ImapMailSource
from verify.services.attachments import read_attachment
from verify.services.store import CaseStore

settings = get_settings()
store = CaseStore(settings.state_path)
_llm = build_llm(settings)
llm = None if isinstance(_llm, NullLLMProvider) else _llm

app = FastAPI(
    title="VeriFY",
    version="0.1.0",
    description="Shipping document verification API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SubmitEmailBody(BaseModel):
    email_id: str | None = None
    sender: str = ""
    subject: str
    body: str = ""
    attachments: list[dict] = Field(default_factory=list)


class ConfirmBody(BaseModel):
    reviewer: str | None = None
    note: str | None = None


def _read(path: str) -> bytes:
    return read_attachment(path, data_dir=settings.inbox_url or settings.data_dir)


async def _ingest(emails: list[EmailMessage]) -> int:
    for email in emails:
        result = await run_pipeline(email, _read, llm=llm)
        store.upsert(email, result)
    return len(emails)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "VeriFY",
        "env": settings.env,
        "llm": llm.name if llm else "rules-only",
        "cases": store.count(),
        "mailbox": settings.imap_username,
        "imap_ready": bool(settings.imap_username and settings.imap_app_password),
    }


@app.get("/cases")
async def list_cases(status: str | None = None, category: str | None = None) -> list[dict]:
    return store.list(status=status, category=category)


@app.get("/cases/{email_id}")
async def get_case(email_id: str) -> dict:
    case = store.get(email_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@app.post("/inbox/replay")
async def replay_inbox(limit: int | None = None) -> dict:
    source = HackathonMailSource(settings.inbox_url or settings.data_dir)
    emails = list(source.emails())
    if limit:
        emails = emails[:limit]
    ingested = await _ingest(emails)
    return {"ingested": ingested, "cases": store.count()}


@app.post("/inbox/submit")
async def submit_email(body: SubmitEmailBody) -> dict:
    """Accept a previously unseen email. Attachments are paths under VERIFY_DATA_DIR
    or inline {filename, content} base64 later; paths keep the demo simple and dynamic."""
    email_id = body.email_id or f"manual-{store.count() + 1:04d}"
    attachments = [
        AttachmentRef(path=item["path"], filename=item.get("filename") or item["path"].split("/")[-1])
        for item in body.attachments
        if "path" in item
    ]
    email = EmailMessage(
        email_id=email_id,
        sender=body.sender,
        subject=body.subject,
        body=body.body,
        attachments=attachments,
        source="manual",
    )
    result = await run_pipeline(email, _read, llm=llm)
    store.upsert(email, result)
    return store.get(email_id) or {}


@app.post("/inbox/imap")
async def poll_imap() -> dict:
    source = ImapMailSource(settings)
    if not source.configured:
        raise HTTPException(
            400,
            f"Set IMAP_APP_PASSWORD for {settings.imap_username} before polling Gmail.",
        )
    ingested = await _ingest(list(source.emails()))
    return {"ingested": ingested, "cases": store.count(), "mailbox": settings.imap_username}


@app.post("/cases/{email_id}/confirm")
async def confirm_case(email_id: str, body: ConfirmBody | None = None) -> dict:
    payload = body or ConfirmBody()
    row = store.confirm(
        email_id,
        reviewer=(payload.reviewer or settings.reviewer_name).strip() or settings.reviewer_name,
        note=payload.note,
    )
    if not row:
        raise HTTPException(404, "Case not found")
    return row


@app.post("/cases/{email_id}/retry")
async def retry_case(email_id: str) -> dict:
    email = store.as_email(email_id)
    if not email:
        raise HTTPException(404, "Case not found")
    result = await run_pipeline(email, _read, llm=llm)
    store.upsert(email, result, reset_review=True)
    store.log_action(email_id, "retry", reviewer=settings.reviewer_name)
    return store.get(email_id) or {}


@app.get("/submission")
async def submission() -> dict:
    return store.submission()


@app.get("/metrics")
async def metrics() -> dict:
    return store.metrics()


@app.get("/audit")
async def audit() -> list[dict]:
    return store.audit()
