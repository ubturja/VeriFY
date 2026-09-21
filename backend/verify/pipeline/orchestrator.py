from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from verify.domain.enums import (
    Category,
    CompareIntent,
    DocumentKind,
    ReviewReason,
    Status,
)
from verify.domain.models import (
    Classification,
    EmailMessage,
    ExtractedDocument,
    PipelineResult,
    UsageSummaryModel,
)
from verify.domain.policy import MailboxPolicy
from verify.pipeline.classify import classify
from verify.pipeline.compare import compare_documents
from verify.pipeline.doctype import is_inline_noise
from verify.pipeline.doctype_llm import guess_kind
from verify.pipeline.extract import extract_from_bytes
from verify.pipeline.extract_llm import fill_missing_fields
from verify.pipeline.judge import resolve_gray_band
from verify.providers.base import LLMProvider
from verify.services.fewshot import FewShotStore
from verify.services.pairing import mark_pending, pair_id, prior_si, shipment_ref
from verify.services.usage import finish_usage, start_usage
from verify.version import PROMPT_VERSION, RULES_MODEL_VERSION

ReadBytes = Callable[[str], bytes]


async def run_pipeline(
    email: EmailMessage,
    read_bytes: ReadBytes,
    llm: LLMProvider | None = None,
    *,
    policy: MailboxPolicy | None = None,
    fewshots: FewShotStore | None = None,
    priors: list[dict[str, Any]] | None = None,
) -> PipelineResult:
    token = start_usage()
    started = time.perf_counter()
    try:
        result = await _execute(email, read_bytes, llm, policy=policy, fewshots=fewshots, priors=priors or [])
    finally:
        summary = finish_usage(token)
    result.usage = UsageSummaryModel.model_validate(summary.model_dump())
    result.latency_ms = int((time.perf_counter() - started) * 1000)
    result.prompt_version = PROMPT_VERSION
    result.model_version = summary.models[0] if summary.models else RULES_MODEL_VERSION
    return result


async def _execute(
    email: EmailMessage,
    read_bytes: ReadBytes,
    llm: LLMProvider | None,
    *,
    policy: MailboxPolicy | None,
    fewshots: FewShotStore | None,
    priors: list[dict[str, Any]],
) -> PipelineResult:
    classification = await classify(email, llm)
    if classification.category != Category.BL_COMPARISON:
        return PipelineResult(
            email_id=email.email_id,
            category=classification.category,
            status=Status.OK,
            decided_by=classification.decided_by,
            notes=[classification.rationale],
            shipment_ref=shipment_ref(f"{email.subject}\n{email.body}"),
        )

    return await _compare_case(
        email,
        classification,
        read_bytes,
        llm,
        policy=policy or MailboxPolicy(),
        fewshots=fewshots,
        priors=priors,
    )


async def _compare_case(
    email: EmailMessage,
    classification: Classification,
    read_bytes: ReadBytes,
    llm: LLMProvider | None,
    *,
    policy: MailboxPolicy,
    fewshots: FewShotStore | None,
    priors: list[dict[str, Any]],
) -> PipelineResult:
    decided = classification.decided_by
    notes = [classification.rationale]
    ref = mark_pending(email.subject, email.body)

    if classification.intent == CompareIntent.REQUEST_DRAFT and not _has_pair(email):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.OK,
            decided_by=decided,
            notes=notes + ["request-draft-no-attachments"],
            shipment_ref=ref,
            pending_draft=True,
        )

    borrowed_si = prior_si(email.subject, email.body, priors) if priors else None
    if not email.attachments or (not _has_pair(email) and borrowed_si is None):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_ATTACHMENT,
            decided_by=decided,
            notes=notes + ["missing-attachment"],
            shipment_ref=ref,
        )

    documents: list[ExtractedDocument] = []
    for attachment in _document_attachments(email):
        payload = read_bytes(attachment.path)
        documents.append(extract_from_bytes(attachment.filename, payload))

    if llm is not None:
        for doc in documents:
            guessed = await guess_kind(doc, llm)
            if guessed is not None:
                doc.kind = guessed
                notes.append(f"doc-type-llm:{doc.attachment}:{guessed.value}")

    if any(doc.unreadable or doc.kind == DocumentKind.UNREADABLE for doc in documents):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.UNREADABLE,
            decided_by=decided,
            notes=notes + ["unreadable-attachment"],
            si=_pick(documents, DocumentKind.SI),
            bl=_pick(documents, DocumentKind.BL),
        )

    wrong = [
        doc
        for doc in documents
        if doc.kind
        in {
            DocumentKind.INVOICE,
            DocumentKind.PACKING_LIST,
            DocumentKind.CERTIFICATE_OF_ORIGIN,
        }
    ]
    if wrong:
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.WRONG_DOC_TYPE,
            decided_by=decided,
            notes=notes + [f"wrong-type:{wrong[0].kind}"],
        )

    si = _pick(documents, DocumentKind.SI)
    bl = _pick(documents, DocumentKind.BL)
    if si is None and bl is not None and borrowed_si is not None:
        si = borrowed_si
        notes.append(f"prior-si:{borrowed_si.attachment}")
    if si is None or bl is None:
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.WRONG_DOC_TYPE,
            decided_by=decided,
            notes=notes + ["could-not-identify-si-bl"],
        )

    llm_notes: list[str] = []
    if llm is not None and (_has_blank(si, policy) or _has_blank(bl, policy)):
        filled_si = await fill_missing_fields(si, llm=llm)
        filled_bl = await fill_missing_fields(bl, llm=llm)
        if filled_si:
            llm_notes.append(f"tier-b-si:{','.join(filled_si)}")
        if filled_bl:
            llm_notes.append(f"tier-b-bl:{','.join(filled_bl)}")

    if _has_blank(si, policy) or _has_blank(bl, policy):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_VALUE,
            decided_by=decided,
            notes=notes + llm_notes + ["blank-required-field"],
            si=si,
            bl=bl,
        )

    comparisons = compare_documents(si, bl, policy=policy)
    if llm is not None or fewshots is not None:
        flipped = await resolve_gray_band(comparisons, llm=llm, fewshots=fewshots)
        if flipped:
            llm_notes.append(f"judge-flipped:{','.join(flipped)}")
    linked = pair_id(email.subject, email.body, priors)
    if any(item.match is None and policy.is_mandatory(item.field) for item in comparisons):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_VALUE,
            decided_by=decided,
            comparisons=comparisons,
            si=si,
            bl=bl,
            notes=notes + llm_notes + ["incomplete-extraction"],
        )

    defects = [
        item.field
        for item in comparisons
        if item.match is False and policy.is_mandatory(item.field)
    ]
    status = Status.MISMATCH if defects else Status.OK
    return PipelineResult(
        email_id=email.email_id,
        category=Category.BL_COMPARISON,
        status=status,
        has_defect=bool(defects),
        defect_fields=defects,
        decided_by=decided,
        comparisons=comparisons,
        si=si,
        bl=bl,
        notes=notes + llm_notes,
        shipment_ref=ref,
        paired_with=linked,
        pending_draft=False,
    )


def _document_attachments(email: EmailMessage):
    return [item for item in email.attachments if not is_inline_noise(item.filename)]


def _has_pair(email: EmailMessage) -> bool:
    """True when there are at least two real documents to compare.

    Hackathon files are named email_009_SI.txt. Live Gmail files are often
    SI-live-test.txt or arbitrary PDF names. Inline images are ignored.
    """
    return len(_document_attachments(email)) >= 2


def _pick(documents: list[ExtractedDocument], kind: DocumentKind) -> ExtractedDocument | None:
    for doc in documents:
        if doc.kind == kind:
            return doc
    return None


def _has_blank(doc: ExtractedDocument, policy: MailboxPolicy) -> bool:
    for name in policy.mandatory_fields:
        field = doc.fields.get(name)
        if field is not None and field.blank_token:
            return True
    return False
