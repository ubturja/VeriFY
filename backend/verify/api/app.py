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
from verify.domain.policy import MailboxPolicy
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.llm.factory import NullLLMProvider, build_llm
from verify.providers.mail.hackathon import HackathonMailSource
from verify.providers.mail.imap import ImapMailSource
from verify.services.attachments import read_attachment, safe_blob_segment, write_inline_attachment
from verify.services.jobqueue import JobQueue
from verify.services.mail_poll import (
    poll_loop,
    poll_mailbox,
    poll_state,
    poll_state_for,
)
from verify.services.reply import build_reply
from verify.services.shipments import related_cases, shipment_id_for
from verify.services.tenants import Tenant, TenantRegistry, normalize_email, secret_key_or_dev
from verify.services.usage import RecordingLLM
from verify.services.webhook import deliver

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
llm = None if isinstance(_llm, NullLLMProvider) else RecordingLLM(_llm)
job_queue = JobQueue(settings.tenants_dir / "queue.json")
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


class RoleBody(BaseModel):
    role: str


class PolicyBody(BaseModel):
    weight_tolerance_kg: int = 0
    mandatory_fields: list[str] = Field(default_factory=lambda: list(COMPARE_FIELDS))
    fields_may_differ: list[str] = Field(default_factory=list)


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


def _session(authorization: str | None) -> tuple[Tenant, str]:
    token = _bearer(authorization)
    if token:
        tenant = tenants.resolve_token(token)
        if tenant:
            return tenant, tenants.role_for(token)
    raise HTTPException(401, "Sign in with your mailbox to continue.")


def current_tenant(authorization: str | None = Header(default=None)) -> Tenant:
    tenant, _role = _session(authorization)
    return tenant


def require_writer(authorization: str | None = Header(default=None)) -> Tenant:
    tenant, role = _session(authorization)
    if role == "auditor":
        raise HTTPException(403, "Auditors can read cases but cannot change them.")
    return tenant


def require_supervisor(authorization: str | None = Header(default=None)) -> Tenant:
    tenant, role = _session(authorization)
    if role != "supervisor":
        raise HTTPException(403, "Only a supervisor can do that.")
    return tenant


def _reviewer(tenant: Tenant) -> str:
    return tenant.email


def _apply_tenant_synonyms(tenant: Tenant, result: Any) -> None:
    tenant.synonyms.apply_to_result(result)


async def _decide(tenant: Tenant, email: EmailMessage, *, reset_review: bool = False) -> dict:
    """Run one email through the local queue, then the pipeline.

    The queue records the attempt. Three failures move the job to the
    dead-letter list and the request fails. A success removes the job.
    """
    job_id = job_queue.enqueue(
        {
            "tenant": tenant.slug,
            "email_id": email.email_id,
            "source": email.source,
            "email": email.model_dump(mode="json"),
            "reset_review": reset_review,
        }
    )
    last_error = "processing failed"
    for _attempt in range(job_queue.max_attempts):
        try:
            priors = [row for row in tenant.store.list() if row.get("email_id") != email.email_id]
            result = await run_pipeline(
                email,
                _read,
                llm=llm,
                policy=tenant.policy.load(),
                fewshots=tenant.fewshots,
                priors=priors,
            )
            _apply_tenant_synonyms(tenant, result)
            tenant.store.upsert(email, result, reset_review=reset_review)
            case = tenant.store.get(email.email_id) or {}
            record = await deliver(case, url=settings.webhook_url or None)
            tenant.store.set_webhook(email.email_id, record)
            job_queue.complete(job_id)
            return tenant.store.get(email.email_id) or {}
        except HTTPException:
            job_queue.complete(job_id)
            raise
        except Exception as exc:  # noqa: BLE001 - retries then dead-letter
            last_error = str(exc)
            if job_queue.fail(job_id, last_error) == "dead":
                break
    raise HTTPException(502, f"Dead-lettered {job_id}: {last_error}")


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
async def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    tenant, role = _session(authorization)
    return {
        "email": tenant.email,
        "role": role,
        "imap_ready": tenant.imap_password_encrypted is not None,
        "last_login_at": tenant.last_login_at,
        "poll": poll_state_for(tenant),
    }


@app.post("/auth/role")
async def set_role(body: RoleBody, authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _bearer(authorization)
    tenant, _role = _session(authorization)
    try:
        updated = bool(token) and tenants.set_role(token, body.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(401, "Sign in with your mailbox to continue.")
    return {"email": tenant.email, "role": body.role}


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
    tenant: Tenant = Depends(require_writer),
) -> dict:
    source = HackathonMailSource(settings.inbox_url or settings.data_dir)
    emails = list(source.emails())
    if limit:
        emails = emails[:limit]
    ingested = 0
    for email in emails:
        await _decide(tenant, email)
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
    tenant: Tenant = Depends(require_writer),
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
    return await _decide(tenant, email)


@app.post("/inbox/imap")
async def poll_imap(
    unseen_only: bool = False,
    tenant: Tenant = Depends(require_writer),
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
            policy=tenant.policy.load(),
            fewshots=tenant.fewshots,
            webhook_url=settings.webhook_url or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(502, f"IMAP unavailable: {exc}") from exc


@app.post("/cases/{email_id}/confirm")
async def confirm_case(
    email_id: str,
    body: ConfirmBody | None = None,
    tenant: Tenant = Depends(require_writer),
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
    tenant: Tenant = Depends(require_writer),
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
    learned = tenant.fewshots.learn_from_correction(
        previous_defects=previous_defects,
        current_defects=current_defects,
        comparisons=(row.get("result") or {}).get("comparisons") or [],
        email_id=email_id,
        note=body.note,
    )
    if learned:
        tenant.store.log_action(
            email_id,
            "learn-fewshot",
            reviewer=_reviewer(tenant),
            note=",".join(learned),
        )
    tenant.evalset.append(
        {
            "email_id": email_id,
            "category": row["result"]["category"],
            "status": row["result"]["status"],
            "has_defect": row["result"].get("has_defect"),
            "defect_fields": current_defects,
            "previous_defect_fields": previous_defects,
            "note": body.note,
        }
    )
    return row


@app.post("/cases/{email_id}/retry")
async def retry_case(email_id: str, tenant: Tenant = Depends(require_writer)) -> dict:
    email = tenant.store.as_email(email_id)
    if not email:
        raise HTTPException(404, "Case not found")
    row = await _decide(tenant, email, reset_review=True)
    tenant.store.log_action(email_id, "retry", reviewer=_reviewer(tenant))
    return row


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
    ref = (case.get("result") or {}).get("shipment_ref")
    timeline = []
    if ref:
        for row in all_cases:
            if (row.get("result") or {}).get("shipment_ref") != ref:
                continue
            timeline.append(
                {
                    "email_id": row.get("email_id"),
                    "subject": row.get("subject"),
                    "status": (row.get("result") or {}).get("status"),
                    "pending_draft": (row.get("result") or {}).get("pending_draft"),
                    "paired_with": (row.get("result") or {}).get("paired_with"),
                    "processed_at": row.get("processed_at"),
                }
            )
    return {
        "shipment_id": shipment_id_for(case) or ref,
        "matches": related_cases(case, all_cases),
        "timeline": timeline,
    }


@app.get("/policy")
async def get_policy(tenant: Tenant = Depends(current_tenant)) -> dict:
    return tenant.policy.load().model_dump()


@app.put("/policy")
async def put_policy(body: PolicyBody, tenant: Tenant = Depends(require_supervisor)) -> dict:
    try:
        saved = tenant.policy.save(MailboxPolicy.model_validate(body.model_dump()))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return saved.model_dump()


@app.get("/webhooks")
async def webhooks(tenant: Tenant = Depends(require_supervisor)) -> list[dict]:
    return [
        {"email_id": row["email_id"], "subject": row.get("subject"), "webhook": row.get("webhook")}
        for row in tenant.store.list()
        if row.get("webhook")
    ]


@app.get("/queue/dead")
async def dead_letters(tenant: Tenant = Depends(require_supervisor)) -> list[dict]:
    return [job for job in job_queue.dead() if (job.get("body") or {}).get("tenant") == tenant.slug]


@app.post("/queue/dead/{job_id}/retry")
async def retry_dead_letter(job_id: str, tenant: Tenant = Depends(require_supervisor)) -> dict:
    match = [
        job
        for job in job_queue.dead()
        if job["id"] == job_id and (job.get("body") or {}).get("tenant") == tenant.slug
    ]
    if not match:
        raise HTTPException(404, "Dead letter not found")
    payload = match[0]["body"]
    email = EmailMessage.model_validate(payload["email"])
    job_queue.discard(job_id)
    row = await _decide(tenant, email, reset_review=bool(payload.get("reset_review")))
    return {"retried": email.email_id, "case": row}


@app.get("/fields")
async def fields() -> dict[str, Any]:
    return {
        "compare_fields": list(COMPARE_FIELDS),
        "categories": [item.value for item in Category],
        "statuses": [item.value for item in Status],
        "review_reasons": [item.value for item in ReviewReason],
    }
