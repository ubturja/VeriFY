"""File-backed job queue with a bounded retry and a dead-letter list.

This is the local stand-in for Service Bus. A job that still fails after
`max_attempts` is moved to the dead-letter list instead of being dropped.
The API drains the queue inside the request so the console stays synchronous,
and the same list is what the dead-letter page reads.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JobQueue:
    def __init__(self, path: Path, *, max_attempts: int = 3) -> None:
        self.path = Path(path)
        self.max_attempts = max_attempts
        self._pending: list[dict[str, Any]] = []
        self._dead: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._pending = data.get("pending") or []
        self._dead = data.get("dead") or []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"pending": self._pending, "dead": self._dead}, indent=2),
            encoding="utf-8",
        )

    def enqueue(self, body: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        self._pending.append(
            {
                "id": job_id,
                "body": body,
                "attempts": 0,
                "enqueued_at": _now(),
                "last_error": None,
            }
        )
        self._save()
        return job_id

    def pending(self) -> list[dict[str, Any]]:
        return list(self._pending)

    def dead(self) -> list[dict[str, Any]]:
        return list(self._dead)

    def complete(self, job_id: str) -> None:
        self._pending = [job for job in self._pending if job["id"] != job_id]
        self._save()

    def fail(self, job_id: str, error: str) -> str:
        """Record a failure. Returns `retry` or `dead`."""
        for job in self._pending:
            if job["id"] != job_id:
                continue
            job["attempts"] = int(job.get("attempts") or 0) + 1
            job["last_error"] = error
            job["failed_at"] = _now()
            if job["attempts"] >= self.max_attempts:
                self._pending = [item for item in self._pending if item["id"] != job_id]
                self._dead.append(job)
                self._save()
                return "dead"
            self._save()
            return "retry"
        return "missing"

    def discard(self, job_id: str) -> bool:
        before = len(self._pending) + len(self._dead)
        self._pending = [job for job in self._pending if job["id"] != job_id]
        self._dead = [job for job in self._dead if job["id"] != job_id]
        if len(self._pending) + len(self._dead) == before:
            return False
        self._save()
        return True

    def requeue(self, job_id: str) -> bool:
        for job in self._dead:
            if job["id"] != job_id:
                continue
            self._dead = [item for item in self._dead if item["id"] != job_id]
            job["attempts"] = 0
            job["last_error"] = None
            job["requeued_at"] = _now()
            self._pending.append(job)
            self._save()
            return True
        return False
