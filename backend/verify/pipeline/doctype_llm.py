"""LLM fallback for document typing.

Used only when filename and header rules return UNKNOWN. A low-confidence
guess is ignored so the case still escalates instead of being mistyped.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from verify.domain.enums import DocumentKind
from verify.domain.models import ExtractedDocument
from verify.providers.base import LLMProvider

_ACCEPTED = {
    DocumentKind.SI,
    DocumentKind.BL,
    DocumentKind.INVOICE,
    DocumentKind.PACKING_LIST,
    DocumentKind.CERTIFICATE_OF_ORIGIN,
}


class DocTypeGuess(BaseModel):
    kind: DocumentKind
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""


_SYSTEM = (
    "You identify a shipping document from its opening text. "
    "Kinds: SI (shipping instruction), BL (bill of lading), INVOICE, "
    "PACKING_LIST, CERTIFICATE_OF_ORIGIN, UNKNOWN. "
    "Return UNKNOWN when the text is not one of those documents."
)


async def guess_kind(
    document: ExtractedDocument,
    llm: LLMProvider | None,
    *,
    min_confidence: float = 0.7,
) -> DocumentKind | None:
    if llm is None or document.kind != DocumentKind.UNKNOWN:
        return None
    text = (document.raw_text or "").strip()
    if not text:
        return None
    user = f"Filename: {document.attachment}\n\n---\n{text[:2000]}\n---"
    try:
        parsed, _ = await llm.complete_json(
            task="doc-type",
            system=_SYSTEM,
            user=user,
            schema=DocTypeGuess,
        )
    except Exception:
        return None
    guess = parsed if isinstance(parsed, DocTypeGuess) else DocTypeGuess.model_validate(parsed)
    if guess.kind not in _ACCEPTED or guess.confidence < min_confidence:
        return None
    return guess.kind
