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

ReadFn = Callable[[str], bytes]

poll_state: dict[str, Any] = {
    "running": False,
    "last_at": None,
    "last_ingested": 0,
    "last_error": None,
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
) -> int:
    ingested = 0
    model = _usable_llm(llm)
    for email in emails:
        if skip_existing and store.get(email.email_id):
            continue
        result = await run_pipeline(email, read, llm=model)
        store.upsert(email, result)
        ingested += 1
    return ingested


def _fetch_messages(settings: Settings, *, unseen_only: bool) -> list[tuple[bytes, EmailMessage]]:
    source = ImapMailSource(settings)
    if not source.configured:
        raise ValueError(f"Set IMAP_APP_PASSWORD for {settings.imap_username} before polling Gmail.")
    return source.fetch_messages(unseen_only=unseen_only)


def _mark_seen(settings: Settings, uids: list[bytes]) -> None:
    if not uids:
        return
    ImapMailSource(settings).mark_seen(uids)


async def poll_mailbox(
    settings: Settings,
    *,
    store: CaseStore,
    read: ReadFn,
    llm: LLMProvider | None,
    unseen_only: bool = True,
) -> dict[str, Any]:
    fetched = await asyncio.to_thread(_fetch_messages, settings, unseen_only=unseen_only)
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
            store.upsert(email, result)
            ingested += 1
            seen_uids.append(uid)
        except Exception as exc:
            errors.append(f"{email.email_id}: {exc}")
    await asyncio.to_thread(_mark_seen, settings, seen_uids)
    poll_state["last_at"] = _stamp()
    poll_state["last_ingested"] = ingested
    poll_state["last_error"] = "; ".join(errors) if errors else None
    return {
        "ingested": ingested,
        "cases": store.count(),
        "mailbox": settings.imap_username,
        "unseen_only": unseen_only,
        "failed": len(errors),
    }


async def poll_loop(
    settings: Settings,
    *,
    store: CaseStore,
    read: ReadFn,
    llm: LLMProvider | None,
) -> None:
    poll_state["running"] = True
    interval = max(int(settings.imap_poll_seconds), 5)
    try:
        while True:
            try:
                await poll_mailbox(settings, store=store, read=read, llm=llm, unseen_only=True)
            except Exception as exc:
                poll_state["last_at"] = _stamp()
                poll_state["last_error"] = str(exc)
            await asyncio.sleep(interval)
    finally:
        poll_state["running"] = False
