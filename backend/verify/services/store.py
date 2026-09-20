from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verify.domain.models import EmailMessage, PipelineResult


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CaseStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._items: dict[str, dict[str, Any]] = {}
        self._audit: list[dict[str, Any]] = []
        self._load()

    def upsert(
        self,
        email: EmailMessage,
        result: PipelineResult,
        *,
        reset_review: bool = False,
    ) -> None:
        previous = self._items.get(email.email_id, {})
        self._items[email.email_id] = {
            "email_id": email.email_id,
            "from": email.sender,
            "subject": email.subject,
            "body": email.body,
            "attachments": [a.model_dump() for a in email.attachments],
            "source": email.source,
            "result": result.model_dump(mode="json"),
            "review": None if reset_review else previous.get("review"),
        }
        self._save()

    def confirm(self, email_id: str, *, reviewer: str, note: str | None = None) -> dict[str, Any] | None:
        row = self._items.get(email_id)
        if not row:
            return None
        review = {
            "action": "confirm",
            "at": _now(),
            "by": reviewer,
            "note": note or None,
            "accepted_status": row["result"]["status"],
            "accepted_category": row["result"]["category"],
        }
        row["review"] = review
        self._log(email_id, "confirm", reviewer=reviewer, note=note, at=review["at"])
        self._save()
        return row

    def as_email(self, email_id: str) -> EmailMessage | None:
        row = self._items.get(email_id)
        if not row:
            return None
        return EmailMessage(
            email_id=row["email_id"],
            sender=row.get("from") or "",
            subject=row.get("subject") or "",
            body=row.get("body") or "",
            attachments=row.get("attachments") or [],
            source=row.get("source") or "hackathon",
        )

    def log_action(
        self,
        email_id: str,
        action: str,
        *,
        reviewer: str,
        note: str | None = None,
    ) -> None:
        self._log(email_id, action, reviewer=reviewer, note=note)
        self._save()

    def _log(
        self,
        email_id: str,
        action: str,
        *,
        reviewer: str,
        note: str | None = None,
        at: str | None = None,
    ) -> None:
        self._audit.append(
            {
                "at": at or _now(),
                "email_id": email_id,
                "action": action,
                "by": reviewer,
                "note": note or None,
            }
        )

    def get(self, email_id: str) -> dict[str, Any] | None:
        return self._items.get(email_id)

    def list(self, status: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        rows = list(self._items.values())
        if status:
            rows = [row for row in rows if row["result"]["status"] == status]
        if category:
            rows = [row for row in rows if row["result"]["category"] == category]
        return sorted(rows, key=lambda row: row["email_id"])

    def count(self) -> int:
        return len(self._items)

    def submission(self) -> dict[str, Any]:
        return {eid: row["result"] for eid, row in self._items.items()}

    def audit(self) -> list[dict[str, Any]]:
        return list(self._audit)

    def metrics(self) -> dict[str, Any]:
        rows = list(self._items.values())
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        confirmed = 0
        for row in rows:
            status = row["result"]["status"]
            category = row["result"]["category"]
            by_status[status] = by_status.get(status, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
            if row.get("review") and row["review"].get("action") == "confirm":
                confirmed += 1
        return {
            "total": len(rows),
            "by_status": by_status,
            "by_category": by_category,
            "confirmed": confirmed,
        }

    def _load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._items = payload.get("cases") or {}
        self._audit = payload.get("audit") or []

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"cases": self._items, "audit": self._audit}, indent=2),
            encoding="utf-8",
        )
