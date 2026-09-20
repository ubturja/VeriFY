from __future__ import annotations

from collections.abc import Callable

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
)
from verify.pipeline.classify import classify
from verify.pipeline.compare import compare_documents
from verify.pipeline.extract import extract_from_bytes
from verify.providers.base import LLMProvider

ReadBytes = Callable[[str], bytes]


async def run_pipeline(
    email: EmailMessage,
    read_bytes: ReadBytes,
    llm: LLMProvider | None = None,
) -> PipelineResult:
    classification = await classify(email, llm)
    if classification.category != Category.BL_COMPARISON:
        return PipelineResult(
            email_id=email.email_id,
            category=classification.category,
            status=Status.OK,
            decided_by=classification.decided_by,
            notes=[classification.rationale],
        )

    return _compare_case(email, classification, read_bytes)


def _compare_case(
    email: EmailMessage,
    classification: Classification,
    read_bytes: ReadBytes,
) -> PipelineResult:
    decided = classification.decided_by
    notes = [classification.rationale]

    if classification.intent == CompareIntent.REQUEST_DRAFT and not _has_pair(email):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.OK,
            decided_by=decided,
            notes=notes + ["request-draft-no-attachments"],
        )

    if not email.attachments or not _has_pair(email):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_ATTACHMENT,
            decided_by=decided,
            notes=notes + ["missing-attachment"],
        )

    documents: list[ExtractedDocument] = []
    for attachment in email.attachments:
        payload = read_bytes(attachment.path)
        documents.append(extract_from_bytes(attachment.filename, payload))

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
    if si is None or bl is None:
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.WRONG_DOC_TYPE,
            decided_by=decided,
            notes=notes + ["could-not-identify-si-bl"],
        )

    if _has_blank(si) or _has_blank(bl):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_VALUE,
            decided_by=decided,
            notes=notes + ["blank-required-field"],
            si=si,
            bl=bl,
        )

    comparisons = compare_documents(si, bl)
    if any(item.match is None for item in comparisons):
        return PipelineResult(
            email_id=email.email_id,
            category=Category.BL_COMPARISON,
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_VALUE,
            decided_by=decided,
            comparisons=comparisons,
            si=si,
            bl=bl,
            notes=notes + ["incomplete-extraction"],
        )

    defects = [item.field for item in comparisons if item.match is False]
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
        notes=notes,
    )


def _has_pair(email: EmailMessage) -> bool:
    names = [a.filename.lower() for a in email.attachments]
    has_si = any("_si." in name or name.endswith("_si") for name in names)
    has_bl = any("_bl." in name or name.endswith("_bl") for name in names)
    return len(email.attachments) >= 2 and has_si and has_bl


def _pick(documents: list[ExtractedDocument], kind: DocumentKind) -> ExtractedDocument | None:
    for doc in documents:
        if doc.kind == kind:
            return doc
    return None


def _has_blank(doc: ExtractedDocument) -> bool:
    return any(field.blank_token for field in doc.fields.values())
