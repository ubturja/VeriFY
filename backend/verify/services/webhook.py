"""Outbound action contract.

The payload is always stored on the case. It is POSTed only when WEBHOOK_URL
is set, so a demo without Teams or SAP still shows what would have been sent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_payload(case: dict[str, Any]) -> dict[str, Any]:
    result = case.get("result") or {}
    return {
        "event": "case.decided",
        "at": _now(),
        "email_id": case.get("email_id"),
        "from": case.get("from"),
        "subject": case.get("subject"),
        "category": result.get("category"),
        "status": result.get("status"),
        "review_reason": result.get("review_reason"),
        "has_defect": result.get("has_defect"),
        "defect_fields": result.get("defect_fields") or [],
        "shipment_ref": result.get("shipment_ref"),
        "pending_draft": result.get("pending_draft") or False,
        "paired_with": result.get("paired_with"),
    }


async def deliver(case: dict[str, Any], *, url: str | None, timeout: float = 5.0) -> dict[str, Any]:
    payload = build_payload(case)
    record: dict[str, Any] = {"payload": payload, "delivered": False, "error": None, "url": url or None}
    if not url:
        record["error"] = "WEBHOOK_URL is not set"
        return record
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
        record["status_code"] = response.status_code
        record["delivered"] = 200 <= response.status_code < 300
        if not record["delivered"]:
            record["error"] = response.text[:300]
    except Exception as exc:  # noqa: BLE001 - delivery failure must not fail the case
        record["error"] = str(exc)
    return record
