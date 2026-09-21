"""Group related cases by an inferred shipment identifier.

Priority: an explicit BL number extracted from filenames or attachments; if
none is found we fall back to a shipment tuple made of (shipper, consignee,
port_of_loading, port_of_discharge). This gives us a way to show a reviewer
the other emails on the same shipment.
"""

from __future__ import annotations

import re
from typing import Any

from verify.text.normalize import fold_party, fold_port

_BL_NUMBER = re.compile(
    r"(?:B\s*/?\s*L\s*(?:no\.?|number|#)|\bbl[-_ ]?(?:no\.?|number|#)|提单号)"
    r"\s*[:#]?\s*([A-Z][A-Z0-9\-]{3,20}\d)",
    re.IGNORECASE,
)


def _text_haystack(case: dict[str, Any]) -> str:
    parts: list[str] = [case.get("subject") or "", case.get("body") or ""]
    for att in case.get("attachments") or []:
        parts.append(att.get("filename") or "")
    result = case.get("result") or {}
    for doc_key in ("si", "bl"):
        doc = result.get(doc_key)
        if isinstance(doc, dict):
            parts.append(doc.get("raw_text") or "")
    return "\n".join(parts)


def shipment_id_for(case: dict[str, Any]) -> str | None:
    """Return a stable identifier for the shipment referenced by ``case``."""
    match = _BL_NUMBER.search(_text_haystack(case))
    if match:
        return f"bl:{match.group(1).upper()}"
    result = case.get("result") or {}
    comparisons = {c.get("field"): c for c in (result.get("comparisons") or [])}
    def _pick(field: str) -> str | None:
        comp = comparisons.get(field, {})
        return comp.get("bl_value") or comp.get("si_value")

    shipper = _pick("shipper")
    consignee = _pick("consignee")
    pol = _pick("port_of_loading")
    pod = _pick("port_of_discharge")
    if not (shipper and consignee and pol and pod):
        return None
    key = "|".join(
        [
            fold_party(shipper),
            fold_party(consignee),
            fold_port(pol),
            fold_port(pod),
        ]
    )
    return f"route:{key}"


def related_cases(target: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_id = shipment_id_for(target)
    if not target_id:
        return []
    matches: list[dict[str, Any]] = []
    for case in cases:
        if case.get("email_id") == target.get("email_id"):
            continue
        if shipment_id_for(case) == target_id:
            matches.append(
                {
                    "email_id": case.get("email_id"),
                    "subject": case.get("subject"),
                    "status": (case.get("result") or {}).get("status"),
                    "from": case.get("from"),
                }
            )
    return matches
