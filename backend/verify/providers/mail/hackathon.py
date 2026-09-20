from __future__ import annotations

import json
from pathlib import Path

from verify.domain.models import AttachmentRef, EmailMessage
from verify.providers.base import MailSource


class HackathonMailSource(MailSource):
    """Reads the participant bundle (folder) or the organizer HTTP inbox."""

    name = "hackathon"

    def __init__(self, source: str | Path) -> None:
        self.source = str(source).rstrip("/")
        self.is_http = self.source.startswith("http://") or self.source.startswith("https://")

    def emails(self) -> list[EmailMessage]:
        if self.is_http:
            return self._from_http()
        return self._from_folder(Path(self.source))

    def read_bytes(self, att_path: str) -> bytes:
        if self.is_http:
            import urllib.request

            url = f"{self.source}/{att_path.lstrip('/')}"
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        return (Path(self.source) / att_path).read_bytes()

    def _from_folder(self, root: Path) -> list[EmailMessage]:
        inbox = root / "inbox"
        if not inbox.is_dir():
            raise FileNotFoundError(f"Inbox not found at {inbox}. Set VERIFY_DATA_DIR.")
        messages: list[EmailMessage] = []
        for path in sorted(inbox.glob("email_*.json")):
            messages.append(self._record_to_email(json.loads(path.read_text(encoding="utf-8"))))
        return messages

    def _from_http(self) -> list[EmailMessage]:
        import urllib.request

        with urllib.request.urlopen(f"{self.source}/emails", timeout=30) as response:
            payload = json.loads(response.read())
        return [self._record_to_email(item) for item in payload]

    def _record_to_email(self, record: dict) -> EmailMessage:
        attachments = []
        for path in record.get("attachments") or []:
            attachments.append(
                AttachmentRef(
                    path=path,
                    filename=Path(path).name,
                )
            )
        return EmailMessage(
            email_id=record["email_id"],
            sender=record.get("from") or record.get("sender") or "",
            subject=record.get("subject") or "",
            body=record.get("body") or "",
            attachments=attachments,
            source="hackathon",
        )
