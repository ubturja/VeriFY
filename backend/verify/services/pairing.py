"""Link a 'please send the draft BL' request to the email that brings the draft.

A request with no attachments is marked pending and keeps the references found
in its subject and body. A later comparison that has a draft BL but no SI can
reuse the SI text from an earlier SI_REQUEST on the same reference.
"""

from __future__ import annotations

import re
from typing import Any

from verify.domain.enums import DocumentKind
from verify.domain.models import ExtractedDocument
from verify.pipeline.extract import extract_from_text

_BL_NUMBER = re.compile(
    r"(?:B\s*/?\s*L\s*(?:no\.?|number|#)|\bbl[-_ ]?(?:no\.?|number|#)|提单号)"
    r"\s*[:#]?\s*([A-Z][A-Z0-9\-]{3,20}\d)",
    re.IGNORECASE,
)
_BOOKING = re.compile(r"\b(?:booking|bk|oc)\s*(?:no\.?|number|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{3,16})", re.I)


def shipment_ref(text: str) -> str | None:
    match = _BL_NUMBER.search(text or "")
    if match:
        return f"bl:{match.group(1).upper()}"
    booking = _BOOKING.search(text or "")
    if booking:
        return f"bk:{booking.group(1).upper()}"
    return None


def _case_text(case: dict[str, Any]) -> str:
    return "\n".join(
        [
            case.get("subject") or "",
            case.get("body") or "",
            " ".join((item.get("filename") or "") for item in case.get("attachments") or []),
        ]
    )


def mark_pending(email_subject: str, email_body: str) -> str | None:
    return shipment_ref(f"{email_subject}\n{email_body}")


def prior_si(email_subject: str, email_body: str, priors: list[dict[str, Any]]) -> ExtractedDocument | None:
    """Find an earlier SI_REQUEST whose body contains the SI fields."""
    ref = shipment_ref(f"{email_subject}\n{email_body}")
    candidates = []
    for case in priors:
        result = case.get("result") or {}
        if result.get("category") not in {"SI_REQUEST", "BL_COMPARISON"}:
            continue
        body = case.get("body") or ""
        if "shipper" not in body.casefold() and "发货人" not in body and "penghantar" not in body.casefold():
            continue
        case_ref = result.get("shipment_ref") or shipment_ref(_case_text(case))
        if ref and case_ref == ref:
            candidates.append(case)
    if not candidates:
        return None
    # store.list() orders by email id, which is not arrival order.
    chosen = max(
        enumerate(candidates),
        key=lambda pair: (pair[1].get("processed_at") or "", pair[0]),
    )[1]
    document = extract_from_text(f"prior:{chosen.get('email_id')}", chosen.get("body") or "")
    if document.kind == DocumentKind.UNKNOWN and document.fields:
        document.kind = DocumentKind.SI
    if not document.fields:
        return None
    return document


def pair_id(email_subject: str, email_body: str, priors: list[dict[str, Any]]) -> str | None:
    ref = shipment_ref(f"{email_subject}\n{email_body}")
    if not ref:
        return None
    for case in reversed(priors):
        result = case.get("result") or {}
        if not result.get("pending_draft"):
            continue
        case_ref = result.get("shipment_ref") or shipment_ref(_case_text(case))
        if case_ref == ref:
            return case.get("email_id")
    return None
