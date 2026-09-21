from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from verify.config import get_settings
from verify.domain.enums import COMPARE_FIELDS, Category, ReviewReason, Status
from verify.domain.models import AttachmentRef, EmailMessage
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.llm.factory import NullLLMProvider, build_llm
from verify.providers.mail.hackathon import HackathonMailSource
from verify.services.attachments import read_attachment, safe_blob_segment, write_inline_attachment
from verify.services.mail_poll import ingest_emails, poll_loop, poll_mailbox, poll_state
from verify.services.store import CaseStore

settings = get_settings()
store = CaseStore(settings.state_path)
_llm = build_llm(settings)
llm = None if isinstance(_llm, NullLLMProvider) else _llm
_poll_task: asyncio.Task[None] | None = None


def _read(path: str) -> bytes:
    return read_attachment(path, data_dir=settings.inbox_url or settings.data_dir)


def _reviewer(name: str | None) -> str:
    return (name or settings.reviewer_name).strip() or settings.reviewer_name


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _poll_task
    should_poll = (
        settings.imap_autopoll
        and settings.imap_poll_seconds > 0
        and bool(settings.imap_username and settings.imap_app_password)
    )
    if should_poll:
        _poll_task = asyncio.create_task(
            poll_loop(settings, store=store, read=_read, llm=llm),
            name="verify-imap-poll",
        )
    try:
        yield
    finally:
        if _poll_task is not None:
            _poll_task.cancel()
            try:
                await _poll_task
            except (asyncio.CancelledError, Exception):
                pass
            _poll_task = None


app = FastAPI(
    title="VeriFY",
    version="0.1.0",
    description="Shipping document verification API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AttachmentIn(BaseModel):
    path: str | None = None
    filename: str | None = None
    content_base64: str | None = None


class SubmitEmailBody(BaseModel):
    email_id: str | None = None
    sender: str = ""
    subject: str
    body: str = ""
    attachments: list[AttachmentIn] = Field(default_factory=list)


class ConfirmBody(BaseModel):
    reviewer: str | None = None
    note: str | None = None


class CorrectBody(BaseModel):
    reviewer: str | None = None
    note: str | None = None
    category: Category | None = None
    status: Status | None = None
    review_reason: ReviewReason | None = None
    defect_fields: list[str] | None = None
    has_defect: bool | None = None


def _attachments_from_submit(email_id: str, items: list[AttachmentIn]) -> list[AttachmentRef]:
    attachments: list[AttachmentRef] = []
    for item in items:
        if item.content_base64:
            try:
                attachments.append(
                    write_inline_attachment(
                        email_id=email_id,
                        filename=item.filename or "attachment.bin",
                        content_base64=item.content_base64,
                        blob_root=settings.local_blob_dir,
                    )
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            continue
        if item.path:
            attachments.append(
                AttachmentRef(
                    path=item.path,
                    filename=item.filename or item.path.split("/")[-1],
                )
            )
    return attachments


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
        "imap_autopoll": poll_state["running"],
        "imap_last_poll": poll_state["last_at"],
        "imap_last_ingested": poll_state["last_ingested"],
        "imap_last_error": poll_state["last_error"],
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
    ingested = await ingest_emails(emails, store=store, read=_read, llm=llm, skip_existing=False)
    return {"ingested": ingested, "cases": store.count()}


@app.post("/inbox/submit")
async def submit_email(body: SubmitEmailBody) -> dict:
    """Accept a previously unseen email. Attachments may be bundle paths or inline base64."""
    email_id = body.email_id or f"manual-{store.count() + 1:04d}"
    try:
        email_id = safe_blob_segment(email_id, label="email id")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    email = EmailMessage(
        email_id=email_id,
        sender=body.sender,
        subject=body.subject,
        body=body.body,
        attachments=_attachments_from_submit(email_id, body.attachments),
        source="manual",
    )
    result = await run_pipeline(email, _read, llm=llm)
    store.upsert(email, result)
    return store.get(email_id) or {}


@app.post("/inbox/imap")
async def poll_imap(unseen_only: bool = False) -> dict:
    try:
        return await poll_mailbox(
            settings,
            store=store,
            read=_read,
            llm=llm,
            unseen_only=unseen_only,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(502, f"IMAP unavailable: {exc}") from exc


@app.post("/cases/{email_id}/confirm")
async def confirm_case(email_id: str, body: ConfirmBody | None = None) -> dict:
    payload = body or ConfirmBody()
    try:
        row = store.confirm(email_id, reviewer=_reviewer(payload.reviewer), note=payload.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not row:
        raise HTTPException(404, "Case not found")
    return row


@app.post("/cases/{email_id}/correct")
async def correct_case(email_id: str, body: CorrectBody) -> dict:
    if body.category is None and body.status is None and body.defect_fields is None:
        raise HTTPException(400, "Provide a category, status, or defect field override.")
    if body.defect_fields:
        unknown = [field for field in body.defect_fields if field not in COMPARE_FIELDS]
        if unknown:
            raise HTTPException(400, f"Unknown defect fields: {', '.join(unknown)}")
    try:
        row = store.correct(
            email_id,
            reviewer=_reviewer(body.reviewer),
            category=body.category.value if body.category else None,
            status=body.status.value if body.status else None,
            review_reason=body.review_reason.value if body.review_reason else None,
            defect_fields=body.defect_fields,
            has_defect=body.has_defect,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
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


@app.get("/fields")
async def fields() -> dict[str, Any]:
    return {
        "compare_fields": list(COMPARE_FIELDS),
        "categories": [item.value for item in Category],
        "statuses": [item.value for item in Status],
        "review_reasons": [item.value for item in ReviewReason],
    }
