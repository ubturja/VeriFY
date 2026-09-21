"""Draft a plain-text reply for a case. Deterministic and template-driven so
it works with no LLM keys. Reviewers can copy, edit, and send."""

from __future__ import annotations

from typing import Any


def _humanise(field: str) -> str:
    return field.replace("_", " ")


def build_reply(case: dict[str, Any], reviewer_email: str) -> dict[str, str]:
    result = case.get("result") or {}
    status = result.get("status")
    subject_prefix = "Re: " if not (case.get("subject") or "").lower().startswith("re:") else ""
    subject = f"{subject_prefix}{case.get('subject') or 'Shipping documents'}"
    lines: list[str] = ["Hi,", ""]
    if status == "OK":
        lines.append(
            "We verified the shipping instruction against the draft bill of lading."
        )
        lines.append("All seven required fields match. Please proceed to issue.")
    elif status == "MISMATCH":
        lines.append(
            "Thanks for the draft BL. We found the following mismatches against the SI:"
        )
        comparisons = {c.get("field"): c for c in (result.get("comparisons") or [])}
        for field in result.get("defect_fields") or []:
            comp = comparisons.get(field, {})
            si = comp.get("si_value") or "(blank)"
            bl = comp.get("bl_value") or "(blank)"
            lines.append(f"  - {_humanise(field)}: SI has \"{si}\" but BL has \"{bl}\".")
        lines.append("")
        lines.append("Please amend the draft BL and resend for a re-check.")
    elif status == "NEEDS_REVIEW":
        reason = result.get("review_reason") or "we could not verify all fields"
        lines.append(
            f"We received your message but could not complete the check ({_humanise(reason)})."
        )
        lines.append(
            "Please resend the SI and the draft BL as attachments so we can re-run the comparison."
        )
    else:
        lines.append("We received your message. A team member will get back to you shortly.")
    lines += ["", "Kind regards,", reviewer_email]
    return {"subject": subject, "body": "\n".join(lines), "to": case.get("from") or ""}
