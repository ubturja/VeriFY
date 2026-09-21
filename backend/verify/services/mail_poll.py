from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from verify.config import Settings
from verify.domain.models import EmailMessage, PipelineResult
from verify.pipeline.orchestrator import run_pipeline
from verify.providers.base import LLMProvider
from verify.providers.llm.factory import NullLLMProvider
from verify.providers.mail.imap import ImapMailSource
from verify.services.store import CaseStore
from verify.services.synonyms import SynonymStore
from verify.services.tenants import Tenant, TenantRegistry

ReadFn = Callable[[str], bytes]

poll_state: dict[str, Any] = {
    "running": False,
    "last_at": None,
    "last_ingested": 0,
    "last_error": None,
    "by_mailbox": {},
}


def _stamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _usable_llm(llm: LLMProvider | None) -> LLMProvider | None:
    if llm is None or isinstance(llm, NullLLMProvider):
        return None
    return llm


async def ingest_emails(
    emails: list[EmailMessage],
    *,
    store: CaseStore,
    read: ReadFn,
    llm: LLMProvider | None,
    skip_existing: bool = True,
    synonyms: SynonymStore | None = None,
) -> int:
    ingested = 0
    model = _usable_llm(llm)
    for email in emails:
        if skip_existing and store.get(email.email_id):
            continue
        result = await run_pipeline(email, read, llm=model)
        if synonyms is not None:
            synonyms.apply_to_result(result)
        store.upsert(email, result)
        ingested += 1
    return ingested


def _source_for(
    settings: Settings,
    *,
    username: str | None,
    app_password: str | None,
) -> ImapMailSource:
    source = ImapMailSource(settings, username=username, app_password=app_password)
    if not source.configured:
        raise ValueError(
            f"Set an app password for {username or settings.imap_username} before polling Gmail."
        )
    return source


def _fetch_messages(
    settings: Settings,
    *,
    unseen_only: bool,
    username: str | None,
    app_password: str | None,
) -> list[tuple[bytes, EmailMessage]]:
    return _source_for(settings, username=username, app_password=app_password).fetch_messages(
        unseen_only=unseen_only
    )


def _mark_seen(
    settings: Settings,
    uids: list[bytes],
    *,
    username: str | None,
    app_password: str | None,
) -> None:
    if not uids:
        return
    _source_for(settings, username=username, app_password=app_password).mark_seen(uids)


async def poll_mailbox(
    settings: Settings,
    *,
    store: CaseStore,
    read: ReadFn,
    llm: LLMProvider | None,
    unseen_only: bool = True,
    username: str | None = None,
    app_password: str | None = None,
    synonyms: SynonymStore | None = None,
) -> dict[str, Any]:
    mailbox = username or settings.imap_username
    fetched = await asyncio.to_thread(
        _fetch_messages,
        settings,
        unseen_only=unseen_only,
        username=username,
        app_password=app_password,
    )
    model = _usable_llm(llm)
    seen_uids: list[bytes] = []
    ingested = 0
    errors: list[str] = []
    for uid, email in fetched:
        if store.get(email.email_id):
            seen_uids.append(uid)
            continue
        try:
            result: PipelineResult = await run_pipeline(email, read, llm=model)
            if synonyms is not None:
                synonyms.apply_to_result(result)
            store.upsert(email, result)
            ingested += 1
            seen_uids.append(uid)
        except Exception as exc:  # noqa: BLE001 - surfaced to caller and logged
            errors.append(f"{email.email_id}: {exc}")
    await asyncio.to_thread(
        _mark_seen, settings, seen_uids, username=username, app_password=app_password
    )
    stamp = _stamp()
    error_message = "; ".join(errors) if errors else None
    poll_state["last_at"] = stamp
    poll_state["last_ingested"] = ingested
    poll_state["last_error"] = error_message
    poll_state["by_mailbox"][mailbox] = {
        "last_at": stamp,
        "ingested": ingested,
        "failed": len(errors),
        "error": error_message,
    }
    return {
        "ingested": ingested,
        "cases": store.count(),
        "mailbox": mailbox,
        "unseen_only": unseen_only,
        "failed": len(errors),
    }


async def poll_tenants_once(
    settings: Settings,
    *,
    registry: TenantRegistry,
    read: ReadFn,
    llm: LLMProvider | None,
) -> dict[str, Any]:
    """Poll every registered mailbox once."""
    results: dict[str, Any] = {}
    for tenant in registry.all():
        password = registry.decrypt_password(tenant)
        if not password:
            continue
        try:
            results[tenant.email] = await poll_mailbox(
                settings,
                store=tenant.store,
                read=read,
                llm=llm,
                unseen_only=True,
                username=tenant.email,
                app_password=password,
                synonyms=tenant.synonyms,
            )
        except Exception as exc:  # noqa: BLE001 - one bad mailbox must not stop the loop
            # Store the full error on the per-tenant record so an authenticated
            # reviewer can see it, but keep the shared ``poll_state`` free of
            # mailbox identifiers so no anonymous caller can correlate errors
            # to specific tenants.
            results[tenant.email] = {"error": str(exc)}
            poll_state["by_mailbox"][tenant.email] = {
                "last_at": _stamp(),
                "ingested": 0,
                "failed": 1,
                "error": str(exc),
            }
            poll_state["last_at"] = _stamp()
            poll_state["last_error"] = "one or more mailboxes failed to poll"
    return results


async def poll_loop(
    settings: Settings,
    *,
    registry: TenantRegistry,
    read: ReadFn,
    llm: LLMProvider | None,
) -> None:
    poll_state["running"] = True
    interval = max(int(settings.imap_poll_seconds), 5)
    try:
        while True:
            try:
                await poll_tenants_once(settings, registry=registry, read=read, llm=llm)
            except Exception as exc:  # noqa: BLE001
                poll_state["last_at"] = _stamp()
                poll_state["last_error"] = str(exc)
            await asyncio.sleep(interval)
    finally:
        poll_state["running"] = False


def poll_state_for(tenant: Tenant) -> dict[str, Any]:
    return poll_state["by_mailbox"].get(tenant.email, {})
