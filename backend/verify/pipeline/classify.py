from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from verify.domain.enums import Category, CompareIntent, DecidedBy
from verify.domain.models import Classification, EmailMessage
from verify.providers.base import LLMProvider
from verify.text.normalize import collapse_ws, nfkc

_QUOTE_RE = re.compile(r"\n_{10,}.*", re.DOTALL)
_SIG_RE = re.compile(
    r"\n(best regards|regards|thank you|thanks|warm regards).*$",
    re.IGNORECASE | re.DOTALL,
)
_BANNER_RE = re.compile(r"^WARNING: This email originated outside.*?\n+", re.IGNORECASE | re.DOTALL)

_SPAM_SUBJECT = (
    "won",
    "gift card",
    "parcel is on hold",
    "email storage is full",
    "90% off",
    "undelivered messages",
    "hot singles",
    "bitcoin",
    "claim now",
    "verify account",
)
_SPAM_SENDER = (
    "prize",
    "parcel-track",
    "webmail-verify",
    "crypto-invest",
    "secure-mailbox",
    "logistics-deals",
)
_INVOICE = (
    "billing",
    "missing gr",
    "cancel invoice",
    "local charges",
    "d & d",
    "d&d",
    "detention",
    "total freight",
    "thc",
)
_GENERAL = (
    "update summary",
    "berthing report",
    "_rpa_",
    "rpa bot",
    "outstanding bl",
    "pending bl release",
    "time off request",
    "welcoming the new year",
    "delivery planning",
    "miss connection",
    "submit si & aed",
)
_SI_REQUEST = (
    "request si",
    "cust si",
    "si needed",
    "latest si",
)
_BL_COMPARE = (
    "to confirm docs",
    "request bl draft",
    "draft bl",
    "amend bl",
)


class LLMClassification(BaseModel):
    category: Category
    intent: CompareIntent = CompareIntent.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


@dataclass
class Score:
    category: Category
    points: float
    reason: str


def clean_body(body: str) -> str:
    text = nfkc(body)
    text = _BANNER_RE.sub("", text)
    text = _QUOTE_RE.split(text, maxsplit=1)[0]
    text = _SIG_RE.split(text, maxsplit=1)[0]
    return collapse_ws(text)


def _contains_any(text: str, needles: tuple[str, ...]) -> str | None:
    for needle in needles:
        if needle in text:
            return needle
    return None


def score_rules(email: EmailMessage) -> tuple[Category | None, CompareIntent, float, str]:
    subject = collapse_ws(email.subject).casefold()
    sender = email.sender.casefold()
    body = clean_body(email.body).casefold()
    combined = f"{subject}\n{body}"

    if hit := _contains_any(subject, _SPAM_SUBJECT):
        return Category.SPAM, CompareIntent.UNKNOWN, 0.97, f"spam subject:{hit}"
    if any(token in sender for token in _SPAM_SENDER):
        return Category.SPAM, CompareIntent.UNKNOWN, 0.95, "spam sender"
    if "bit.ly" in body or "claim your" in body and "gift" in body:
        return Category.SPAM, CompareIntent.UNKNOWN, 0.9, "spam body"

    if hit := _contains_any(combined, _GENERAL):
        return Category.GENERAL, CompareIntent.UNKNOWN, 0.9, f"general:{hit}"

    if hit := _contains_any(combined, _INVOICE):
        return Category.INVOICE_QUERY, CompareIntent.UNKNOWN, 0.92, f"invoice:{hit}"

    if hit := _contains_any(subject, _SI_REQUEST) or re.search(r"\bsi\s*[-_]", subject):
        reason = hit if isinstance(hit, str) else "si-subject"
        return Category.SI_REQUEST, CompareIntent.UNKNOWN, 0.9, f"si:{reason}"

    if hit := _contains_any(subject, _BL_COMPARE):
        intent = _intent(body, bool(email.attachments))
        return Category.BL_COMPARISON, intent, 0.93, f"bl:{hit}"

    # Coded operational subject: DEPT - POD - CARRIER(BLNO)
    if re.search(r"\b(aie|afptme|afrt|afemy)\b", subject) and "(" in subject:
        intent = _intent(body, bool(email.attachments))
        return Category.BL_COMPARISON, intent, 0.88, "coded-bl-subject"

    if email.attachments:
        intent = _intent(body, True)
        return Category.BL_COMPARISON, intent, 0.72, "has-attachments"

    if "draft bl" in body or "bill of lading" in body:
        intent = _intent(body, bool(email.attachments))
        return Category.BL_COMPARISON, intent, 0.7, "bl-in-body"

    if "shipping instruction" in body and "draft bl" in body:
        return Category.SI_REQUEST, CompareIntent.UNKNOWN, 0.7, "si-in-body"

    return None, CompareIntent.UNKNOWN, 0.0, "no-rule"


def _intent(body: str, has_attachments: bool) -> CompareIntent:
    if "send the draft bl" in body or "assist to send the draft" in body:
        return CompareIntent.REQUEST_DRAFT
    if "still missing" in body or "have been dropped" in body:
        return CompareIntent.COMPARE_ATTACHED
    if has_attachments or "please compare" in body or "check the draft" in body:
        return CompareIntent.COMPARE_ATTACHED
    return CompareIntent.UNKNOWN


async def classify(
    email: EmailMessage,
    llm: LLMProvider | None = None,
    *,
    rule_threshold: float = 0.8,
) -> Classification:
    category, intent, confidence, reason = score_rules(email)
    if category and confidence >= rule_threshold:
        return Classification(
            category=category,
            intent=intent,
            confidence=confidence,
            decided_by=DecidedBy.RULE,
            rationale=reason,
        )

    if llm is not None:
        try:
            system = (
                "You classify shipping-operations emails. Categories:\n"
                "- BL_COMPARISON: request to check/confirm a draft Bill of Lading against a Shipping Instruction.\n"
                "- SI_REQUEST: request to prepare or send a Shipping Instruction (not yet comparing a BL).\n"
                "- INVOICE_QUERY: billing, charges, GR, cancellation, freight queries.\n"
                "- GENERAL: operational updates, berthing, SLA reminders, HR, automated RPA notices.\n"
                "- SPAM: marketing, phishing, prizes, unrelated mail.\n"
                "Intent is only for BL_COMPARISON: compare_attached vs request_draft "
                "(the sender is asking you to send the draft because it is not attached)."
            )
            user = (
                f"From: {email.sender}\nSubject: {email.subject}\n"
                f"Attachments: {[a.filename for a in email.attachments]}\n\n"
                f"{clean_body(email.body)[:4000]}"
            )
            parsed, _ = await llm.complete_json(
                task="classify",
                system=system,
                user=user,
                schema=LLMClassification,
            )
            result = parsed if isinstance(parsed, LLMClassification) else LLMClassification.model_validate(parsed)
            if intent != CompareIntent.UNKNOWN:
                result.intent = intent
            return Classification(
                category=result.category,
                intent=result.intent,
                confidence=result.confidence,
                decided_by=DecidedBy.LLM,
                rationale=result.rationale or reason,
            )
        except Exception:
            pass

    if category:
        return Classification(
            category=category,
            intent=intent,
            confidence=max(confidence, 0.55),
            decided_by=DecidedBy.RULE,
            rationale=reason + "+fallback",
        )
    return Classification(
        category=Category.GENERAL,
        intent=CompareIntent.UNKNOWN,
        confidence=0.4,
        decided_by=DecidedBy.RULE,
        rationale="default-general",
    )
