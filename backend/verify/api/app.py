from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from verify.config import get_settings
from verify.domain.enums import COMPARE_FIELDS, Category, ReviewReason, Status
from verify.domain.models import AttachmentRef, EmailMessage
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.llm.factory import NullLLMProvider, build_llm
from verify.providers.mail.hackathon import HackathonMailSource
from verify.providers.mail.imap import ImapMailSource
from verify.services.attachments import read_attachment, safe_blob_segment, write_inline_attachment
from verify.services.mail_poll import (
    poll_loop,
    poll_mailbox,
    poll_state,
    poll_state_for,
)
from verify.services.reply import build_reply
from verify.services.shipments import related_cases, shipment_id_for
from verify.services.tenants import Tenant, TenantRegistry, normalize_email, secret_key_or_dev

settings = get_settings()
_secret_key = secret_key_or_dev(
    settings.secret_key,
    artifacts_root=settings.tenants_dir,
    env=settings.env,
    require=settings.require_secret_key,
)
tenants = TenantRegistry(settings.tenants_dir, secret_key=_secret_key)

# Seed a tenant from env when IMAP_USERNAME/IMAP_APP_PASSWORD are provided, so
# operators can pre-provision one mailbox for the demo. This never overrides
# a mailbox added through the UI, and empty values are ignored.
if settings.imap_username and settings.imap_app_password:
    try:
        tenants.ensure(settings.imap_username, app_password=settings.imap_app_password)
    except ValueError:
        pass

_llm = build_llm(settings)
llm = None if isinstance(_llm, NullLLMProvider) else _llm
_poll_task: asyncio.Task[None] | None = None


def _read(path: str) -> bytes:
    return read_attachment(path, data_dir=settings.inbox_url or settings.data_dir)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _poll_task
    if settings.imap_autopoll and settings.imap_poll_seconds > 0:
        _poll_task = asyncio.create_task(
            poll_loop(settings, registry=tenants, read=_read, llm=llm),
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


# ------------------------------------------------------------------ schemas


class LoginBody(BaseModel):
    email: str
    app_password: str = ""


class DevLoginBody(BaseModel):
    email: str


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
    note: str | None = None


class CorrectBody(BaseModel):
    note: str | None = None
    category: Category | None = None
    status: Status | None = None
    review_reason: ReviewReason | None = None
    defect_fields: list[str] | None = None
    has_defect: bool | None = None


# ------------------------------------------------------------------ auth


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return authorization.strip() or None


def _test_mode() -> bool:
    return settings.env in {"local", "test"}


def current_tenant(authorization: str | None = Header(default=None)) -> Tenant:
    token = _bearer(authorization)
    if token:
        tenant = tenants.resolve_token(token)
        if tenant:
            return tenant
    raise HTTPException(401, "Sign in with your mailbox to continue.")


def _reviewer(tenant: Tenant) -> str:
    return tenant.email


def _apply_tenant_synonyms(tenant: Tenant, result: Any) -> None:
    tenant.synonyms.apply_to_result(result)


# ------------------------------------------------------------------ health / auth


@app.get("/health")
async def health() -> dict:
    """Unauthenticated liveness probe. Deliberately does not include any
    per-mailbox information or the last IMAP error message: those live behind
    ``/auth/me`` so one tenant never leaks another tenant's mailbox state to
    an anonymous caller."""

    return {
        "status": "ok",
        "service": "VeriFY",
        "env": settings.env,
        "llm": llm.name if llm else "rules-only",
        "mailboxes": len(tenants.all()),
        "imap_autopoll": poll_state["running"],
    }


@app.post("/auth/login")
async def login(body: LoginBody) -> dict[str, str]:
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not body.app_password:
        raise HTTPException(400, "Gmail app password is required.")
    source = ImapMailSource(settings, username=email, app_password=body.app_password)
    try:
        await asyncio.to_thread(source.verify_login)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(502, f"Gmail unreachable: {exc}") from exc
    tenant = tenants.ensure(email, app_password=body.app_password)
    token = tenants.issue_token(tenant)
    return {"token": token, "email": tenant.email}


@app.post("/auth/dev-login")
async def dev_login(body: DevLoginBody) -> dict[str, str]:
    """Register a mailbox without Gmail verification. Local and test only."""
    if not _test_mode():
        raise HTTPException(404, "Not available")
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    tenant = tenants.ensure(email)
    token = tenants.issue_token(tenant)
    return {"token": token, "email": tenant.email}


@app.post("/auth/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    token = _bearer(authorization)
    if token:
        tenants.revoke_token(token)
    return {"ok": True}


@app.get("/auth/me")
async def me(tenant: Tenant = Depends(current_tenant)) -> dict[str, Any]:
    return {
        "email": tenant.email,
        "imap_ready": tenant.imap_password_encrypted is not None,
        "last_login_at": tenant.last_login_at,
        "poll": poll_state_for(tenant),
    }


# ------------------------------------------------------------------ cases


@app.get("/cases")
async def list_cases(
    status: str | None = None,
    category: str | None = None,
    tenant: Tenant = Depends(current_tenant),
) -> list[dict]:
    return tenant.store.list(status=status, category=category)


@app.get("/cases/{email_id}")
async def get_case(email_id: str, tenant: Tenant = Depends(current_tenant)) -> dict:
    case = tenant.store.get(email_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@app.post("/inbox/replay")
async def replay_inbox(
    limit: int | None = None,
    tenant: Tenant = Depends(current_tenant),
) -> dict:
    source = HackathonMailSource(settings.inbox_url or settings.data_dir)
    emails = list(source.emails())
    if limit:
        emails = emails[:limit]
    ingested = 0
    for email in emails:
        result = await run_pipeline(email, _read, llm=llm)
        _apply_tenant_synonyms(tenant, result)
        tenant.store.upsert(email, result)
        ingested += 1
    return {"ingested": ingested, "cases": tenant.store.count()}


def _attachments_from_submit(
    tenant: Tenant,
    email_id: str,
    items: list[AttachmentIn],
) -> list[AttachmentRef]:
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
                        tenant_slug=tenant.slug,
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


@app.post("/inbox/submit")
async def submit_email(
    body: SubmitEmailBody,
    tenant: Tenant = Depends(current_tenant),
) -> dict:
    email_id = body.email_id or f"manual-{tenant.store.count() + 1:04d}"
    try:
        email_id = safe_blob_segment(email_id, label="email id")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    email = EmailMessage(
        email_id=email_id,
        sender=body.sender or tenant.email,
        subject=body.subject,
        body=body.body,
        attachments=_attachments_from_submit(tenant, email_id, body.attachments),
        source="manual",
    )
    result = await run_pipeline(email, _read, llm=llm)
    _apply_tenant_synonyms(tenant, result)
    tenant.store.upsert(email, result)
    return tenant.store.get(email_id) or {}


@app.post("/inbox/imap")
async def poll_imap(
    unseen_only: bool = False,
    tenant: Tenant = Depends(current_tenant),
) -> dict:
    password = tenants.decrypt_password(tenant)
    if not password:
        raise HTTPException(400, "Sign in again with your Gmail app password.")
    try:
        return await poll_mailbox(
            settings,
            store=tenant.store,
            read=_read,
            llm=llm,
            unseen_only=unseen_only,
            username=tenant.email,
            app_password=password,
            synonyms=tenant.synonyms,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(502, f"IMAP unavailable: {exc}") from exc


@app.post("/cases/{email_id}/confirm")
async def confirm_case(
    email_id: str,
    body: ConfirmBody | None = None,
    tenant: Tenant = Depends(current_tenant),
) -> dict:
    payload = body or ConfirmBody()
    try:
        row = tenant.store.confirm(email_id, reviewer=_reviewer(tenant), note=payload.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not row:
        raise HTTPException(404, "Case not found")
    return row


@app.post("/cases/{email_id}/correct")
async def correct_case(
    email_id: str,
    body: CorrectBody,
    tenant: Tenant = Depends(current_tenant),
) -> dict:
    if body.category is None and body.status is None and body.defect_fields is None:
        raise HTTPException(400, "Provide a category, status, or defect field override.")
    if body.defect_fields:
        unknown = [field for field in body.defect_fields if field not in COMPARE_FIELDS]
        if unknown:
            raise HTTPException(400, f"Unknown defect fields: {', '.join(unknown)}")
    previous = tenant.store.get(email_id) or {}
    previous_defects = list((previous.get("result") or {}).get("defect_fields") or [])
    try:
        row = tenant.store.correct(
            email_id,
            reviewer=_reviewer(tenant),
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
    current_defects = list((row.get("result") or {}).get("defect_fields") or [])
    remembered = tenant.synonyms.learn_from_correction(
        previous_defects=previous_defects,
        current_defects=current_defects,
        comparisons=(row.get("result") or {}).get("comparisons") or [],
    )
    if remembered:
        tenant.store.log_action(
            email_id,
            "learn-synonym",
            reviewer=_reviewer(tenant),
            note=",".join(remembered),
        )
    return row


@app.post("/cases/{email_id}/retry")
async def retry_case(email_id: str, tenant: Tenant = Depends(current_tenant)) -> dict:
    email = tenant.store.as_email(email_id)
    if not email:
        raise HTTPException(404, "Case not found")
    result = await run_pipeline(email, _read, llm=llm)
    _apply_tenant_synonyms(tenant, result)
    tenant.store.upsert(email, result, reset_review=True)
    tenant.store.log_action(email_id, "retry", reviewer=_reviewer(tenant))
    return tenant.store.get(email_id) or {}


@app.get("/submission")
async def submission(tenant: Tenant = Depends(current_tenant)) -> dict:
    return tenant.store.submission()


@app.get("/metrics")
async def metrics(tenant: Tenant = Depends(current_tenant)) -> dict:
    return tenant.store.metrics()


@app.get("/audit")
async def audit(tenant: Tenant = Depends(current_tenant)) -> list[dict]:
    return tenant.store.audit()


@app.get("/cases/{email_id}/reply-draft")
async def reply_draft(email_id: str, tenant: Tenant = Depends(current_tenant)) -> dict[str, str]:
    case = tenant.store.get(email_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return build_reply(case, tenant.email)


@app.get("/cases/{email_id}/related")
async def related(email_id: str, tenant: Tenant = Depends(current_tenant)) -> dict[str, Any]:
    case = tenant.store.get(email_id)
    if not case:
        raise HTTPException(404, "Case not found")
    all_cases = tenant.store.list()
    return {
        "shipment_id": shipment_id_for(case),
        "matches": related_cases(case, all_cases),
    }


@app.get("/fields")
async def fields() -> dict[str, Any]:
    return {
        "compare_fields": list(COMPARE_FIELDS),
        "categories": [item.value for item in Category],
        "statuses": [item.value for item in Status],
        "review_reasons": [item.value for item in ReviewReason],
    }
