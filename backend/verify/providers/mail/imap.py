from __future__ import annotations

import email
import imaplib
import re
import uuid
from collections.abc import Iterable
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path

from verify.config import Settings
from verify.domain.models import AttachmentRef, EmailMessage
from verify.providers.base import MailSource


def safe_email_id(raw: str | None) -> str:
    cleaned = (raw or "").strip().strip("<>")
    cleaned = re.sub(r"[^A-Za-z0-9._@+-]+", "_", cleaned)
    return cleaned[:180] or f"imap-{uuid.uuid4()}"


class ImapMailSource(MailSource):
    """Polls an IMAP mailbox. App password is read from settings, never from code."""

    name = "imap"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.blob_root = settings.local_blob_dir / "imap"
        self.blob_root.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return bool(self.settings.imap_username and self.settings.imap_app_password)

    def emails(self) -> Iterable[EmailMessage]:
        yield from self._fetch(unseen_only=False)

    def read_bytes(self, att_path: str) -> bytes:
        path = Path(att_path)
        if path.is_file():
            return path.read_bytes()
        candidate = self.blob_root / att_path
        if candidate.is_file():
            return candidate.read_bytes()
        raise FileNotFoundError(att_path)

    def parse(self, raw: bytes) -> EmailMessage:
        parsed: Message = email.message_from_bytes(raw)
        email_id = safe_email_id(parsed.get("Message-ID"))
        subject = str(make_header(decode_header(parsed.get("Subject", ""))))
        sender = str(make_header(decode_header(parsed.get("From", ""))))
        body_parts: list[str] = []
        attachments: list[AttachmentRef] = []
        out_dir = self.blob_root / email_id
        for part in parsed.walk():
            disposition = str(part.get("Content-Disposition") or "")
            filename = part.get_filename()
            if filename:
                payload = part.get_payload(decode=True) or b""
                safe_name = Path(filename).name or "attachment.bin"
                out_dir.mkdir(parents=True, exist_ok=True)
                dest = out_dir / safe_name
                dest.write_bytes(payload)
                attachments.append(
                    AttachmentRef(
                        path=str(dest),
                        filename=safe_name,
                        content_type=part.get_content_type(),
                        size_bytes=len(payload),
                    )
                )
                continue
            if part.get_content_type() == "text/plain" and "attachment" not in disposition:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True) or b""
                body_parts.append(payload.decode(charset, errors="replace"))
        return EmailMessage(
            email_id=email_id,
            sender=sender,
            subject=subject,
            body="\n".join(body_parts),
            attachments=attachments,
            source="imap",
        )

    def _fetch(self, *, unseen_only: bool) -> list[EmailMessage]:
        if not self.configured:
            raise ValueError("IMAP_USERNAME and IMAP_APP_PASSWORD must be set for IMAP ingest.")
        client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        try:
            client.login(self.settings.imap_username, self.settings.imap_app_password)
            client.select(self.settings.imap_folder, readonly=True)
            criterion = "UNSEEN" if unseen_only else "ALL"
            _, data = client.search(None, criterion)
            ids = data[0].split() if data[0] else []
            messages: list[EmailMessage] = []
            for msg_id in ids[-50:]:
                _, payload = client.fetch(msg_id, "(RFC822)")
                raw = payload[0][1]
                messages.append(self.parse(raw if isinstance(raw, bytes) else b""))
            return messages
        finally:
            try:
                client.logout()
            except Exception:
                pass
