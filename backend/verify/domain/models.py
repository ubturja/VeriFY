from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from verify.domain.enums import (
    Category,
    CompareIntent,
    DecidedBy,
    DocumentKind,
    ReviewReason,
    Status,
)


class AttachmentRef(BaseModel):
    path: str
    filename: str
    content_type: str | None = None
    size_bytes: int = 0


class EmailMessage(BaseModel):
    email_id: str
    sender: str = ""
    subject: str = ""
    body: str = ""
    received_at: datetime | None = None
    attachments: list[AttachmentRef] = Field(default_factory=list)
    source: str = "hackathon"
    raw_headers: dict[str, str] = Field(default_factory=dict)


class Evidence(BaseModel):
    attachment: str
    locator: str
    snippet: str = ""


class ExtractedField(BaseModel):
    name: str
    value: str | None = None
    confidence: float = 0.0
    evidence: Evidence | None = None
    blank_token: bool = False
    from_llm: bool = False


class ExtractedDocument(BaseModel):
    kind: DocumentKind
    attachment: str
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    unreadable: bool = False
    language_hint: str | None = None
    raw_text: str = ""


class FieldComparison(BaseModel):
    field: str
    si_value: str | None = None
    bl_value: str | None = None
    match: bool | None = None
    confidence: float = 0.0
    note: str | None = None
    si_evidence: Evidence | None = None
    bl_evidence: Evidence | None = None


class Classification(BaseModel):
    category: Category
    intent: CompareIntent = CompareIntent.UNKNOWN
    confidence: float
    decided_by: DecidedBy
    rationale: str = ""


class PipelineResult(BaseModel):
    email_id: str
    category: Category
    status: Status
    review_reason: ReviewReason | None = None
    has_defect: bool = False
    defect_fields: list[str] = Field(default_factory=list)
    decided_by: DecidedBy = DecidedBy.RULE
    comparisons: list[FieldComparison] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    si: ExtractedDocument | None = None
    bl: ExtractedDocument | None = None

    def to_submission(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "status": self.status.value,
            "review_reason": self.review_reason.value if self.review_reason else None,
            "has_defect": self.has_defect,
            "defect_fields": self.defect_fields,
            "decided_by": self.decided_by.value,
        }


class CaseRecord(BaseModel):
    id: str
    email: EmailMessage
    result: PipelineResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assignee: str | None = None
    human_verdict: dict[str, Any] | None = None
