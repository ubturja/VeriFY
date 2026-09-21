from __future__ import annotations

import json
from pathlib import Path

from verify.domain.enums import COMPARE_FIELDS
from verify.domain.policy import MailboxPolicy


class PolicyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> MailboxPolicy:
        if not self.path.is_file():
            return MailboxPolicy()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        policy = MailboxPolicy.model_validate(data)
        unknown = [field for field in policy.mandatory_fields + policy.fields_may_differ if field not in COMPARE_FIELDS]
        if unknown:
            raise ValueError(f"Unknown policy fields: {', '.join(unknown)}")
        if policy.weight_tolerance_kg < 0:
            raise ValueError("Weight tolerance cannot be negative.")
        return policy

    def save(self, policy: MailboxPolicy) -> MailboxPolicy:
        checked = self._validate(policy)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(checked.model_dump_json(indent=2), encoding="utf-8")
        return checked

    def _validate(self, policy: MailboxPolicy) -> MailboxPolicy:
        unknown = [
            field
            for field in policy.mandatory_fields + policy.fields_may_differ
            if field not in COMPARE_FIELDS
        ]
        if unknown:
            raise ValueError(f"Unknown policy fields: {', '.join(unknown)}")
        if policy.weight_tolerance_kg < 0:
            raise ValueError("Weight tolerance cannot be negative.")
        return policy
