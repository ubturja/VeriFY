"""Per-mailbox comparison policy. Defaults reproduce the scoreboard rules:
exact weight match and every field mandatory."""

from __future__ import annotations

from pydantic import BaseModel, Field

from verify.domain.enums import COMPARE_FIELDS


class MailboxPolicy(BaseModel):
    weight_tolerance_kg: int = 0
    mandatory_fields: list[str] = Field(default_factory=lambda: list(COMPARE_FIELDS))
    fields_may_differ: list[str] = Field(default_factory=list)

    def allows_difference(self, field: str) -> bool:
        return field in self.fields_may_differ

    def is_mandatory(self, field: str) -> bool:
        return field in self.mandatory_fields
