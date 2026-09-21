from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verify.domain.enums import COMPARE_FIELDS, Category, DecidedBy, ReviewReason, Status
from verify.domain.models import EmailMessage, PipelineResult

_SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_ALLOWED_DEFECTS = set(COMPARE_FIELDS)


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
        existing = row.get("review") or {}
        if existing.get("action") == "correct":
            raise ValueError("Case already corrected")
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

    def correct(
        self,
        email_id: str,
        *,
        reviewer: str,
        category: str | None = None,
        status: str | None = None,
        review_reason: str | None = None,
        defect_fields: list[str] | None = None,
        has_defect: bool | None = None,
        note: str | None = None,
    ) -> dict[str, Any] | None:
        row = self._items.get(email_id)
        if not row:
            return None
        result = dict(row["result"])
        previous = {
            "category": result["category"],
            "status": result["status"],
            "has_defect": result.get("has_defect"),
            "defect_fields": list(result.get("defect_fields") or []),
            "review_reason": result.get("review_reason"),
        }
        if category is not None:
            result["category"] = Category(category).value
        if status is not None:
            result["status"] = Status(status).value
        if defect_fields is not None:
            unknown = [field for field in defect_fields if field not in _ALLOWED_DEFECTS]
            if unknown:
                raise ValueError(f"Unknown defect fields: {', '.join(unknown)}")
            result["defect_fields"] = list(dict.fromkeys(defect_fields))
            result["has_defect"] = bool(result["defect_fields"])
        if has_defect is not None:
            result["has_defect"] = has_defect
            if not has_defect:
                result["defect_fields"] = []
        if result["status"] == Status.OK:
            result["has_defect"] = False
            result["defect_fields"] = []
            result["review_reason"] = None
        elif result["status"] == Status.MISMATCH:
            if not result.get("defect_fields"):
                raise ValueError("MISMATCH requires at least one defect field.")
            result["has_defect"] = True
            if review_reason is None:
                result["review_reason"] = None
        elif result["status"] == Status.NEEDS_REVIEW:
            reason = review_reason if review_reason is not None else result.get("review_reason")
            result["review_reason"] = ReviewReason(reason or ReviewReason.MISSING_VALUE).value
        if review_reason is not None and result["status"] != Status.OK:
            result["review_reason"] = ReviewReason(review_reason).value
        result["decided_by"] = DecidedBy.HUMAN.value
        row["result"] = result
        review = {
            "action": "correct",
            "at": _now(),
            "by": reviewer,
            "note": note or None,
            "previous": previous,
            "accepted_status": result["status"],
            "accepted_category": result["category"],
        }
        row["review"] = review
        self._log(email_id, "correct", reviewer=reviewer, note=note, at=review["at"])
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
        corrected = 0
        for row in rows:
            status = row["result"]["status"]
            category = row["result"]["category"]
            by_status[status] = by_status.get(status, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
            action = (row.get("review") or {}).get("action")
            if action == "confirm":
                confirmed += 1
            elif action == "correct":
                corrected += 1
        return {
            "total": len(rows),
            "by_status": by_status,
            "by_category": by_category,
            "confirmed": confirmed,
            "corrected": corrected,
        }

    def _use_sqlite(self) -> bool:
        return bool(self.path and self.path.suffix.lower() in _SQLITE_SUFFIXES)

    def _payload(self) -> dict[str, Any]:
        return {"cases": self._items, "audit": self._audit}

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        self._items = payload.get("cases") or {}
        self._audit = payload.get("audit") or []

    def _load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        if self._use_sqlite():
            with sqlite3.connect(self.path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
                row = conn.execute("SELECT payload FROM state WHERE id = 1").fetchone()
            if row:
                self._apply_payload(json.loads(row[0]))
            return
        self._apply_payload(json.loads(self.path.read_text(encoding="utf-8")))

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(self._payload(), indent=2)
        if self._use_sqlite():
            with sqlite3.connect(self.path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
                conn.execute("INSERT OR REPLACE INTO state (id, payload) VALUES (1, ?)", (encoded,))
                conn.commit()
            return
        self.path.write_text(encoded, encoding="utf-8")
