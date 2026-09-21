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


def normalize_app_password(value: str | None) -> str:
    """Google shows an app password as four groups of four. IMAP needs the 16
    characters with the spaces removed. The account password is a different secret.
    """
    return re.sub(r"\s+", "", value or "")


def gmail_login_error(exc: imaplib.IMAP4.error, password: str) -> ValueError:
    raw = exc.args[0] if exc.args else ""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    folded = text.casefold()
    if "web browser" in folded or "imap access" in folded:
        return ValueError(
            "Gmail blocked IMAP for this mailbox. Turn on IMAP in Gmail settings, "
            "then sign in with an app password."
        )
    if len(password) != 16 or not password.isalnum():
        return ValueError(
            "Gmail rejected the sign-in. Paste the 16-character app password "
            "from Google Account, not the normal account password."
        )
    return ValueError("Gmail rejected the credentials. Check the app password and try again.")


def safe_email_id(raw: str | None) -> str:
    cleaned = (raw or "").strip().strip("<>")
    cleaned = re.sub(r"[^A-Za-z0-9._@+-]+", "_", cleaned)
    return cleaned[:180] or f"imap-{uuid.uuid4()}"


def rfc822_from_payload(payload: object) -> bytes:
    if not isinstance(payload, list | tuple):
        return b""
    for part in payload:
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
            return part[1]
    return b""


class ImapMailSource(MailSource):
    """Polls an IMAP mailbox. Credentials are supplied per instance so a single
    process can service many mailboxes without ever holding one in a global."""

    name = "imap"

    def __init__(
        self,
        settings: Settings,
        *,
        username: str | None = None,
        app_password: str | None = None,
    ) -> None:
        self.settings = settings
        self.username = (username if username is not None else settings.imap_username or "").strip()
        raw_password = app_password if app_password is not None else settings.imap_app_password
        self.app_password = normalize_app_password(raw_password)
        slug = re.sub(r"[^A-Za-z0-9._@+-]+", "_", self.username or "default") or "default"
        self.blob_root = settings.local_blob_dir / "imap" / slug
        self.blob_root.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return bool(self.username and self.app_password)

    def verify_login(self) -> None:
        """Log in and log out. Raises ``ValueError`` if credentials are wrong."""
        if not self.configured:
            raise ValueError("Enter both an email and a Gmail app password.")
        client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        try:
            client.login(self.username, self.app_password)
        except imaplib.IMAP4.error as exc:
            raise gmail_login_error(exc, self.app_password) from exc
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def emails(self, *, unseen_only: bool = False) -> Iterable[EmailMessage]:
        for _uid, message in self.fetch_messages(unseen_only=unseen_only):
            yield message

    def fetch_messages(self, *, unseen_only: bool = False) -> list[tuple[bytes, EmailMessage]]:
        """Fetch messages without changing IMAP flags. Call mark_seen after ingest succeeds."""
        return self._fetch(unseen_only=unseen_only)

    def mark_seen(self, uids: list[bytes]) -> None:
        if not uids:
            return
        if not self.configured:
            raise ValueError("IMAP credentials missing for mark_seen.")
        client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        try:
            client.login(self.username, self.app_password)
            client.select(self.settings.imap_folder, readonly=False)
            for uid in uids:
                client.uid("STORE", uid, "+FLAGS", r"(\Seen)")
        finally:
            try:
                client.logout()
            except Exception:
                pass

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

    def _connect(self) -> imaplib.IMAP4_SSL:
        if not self.configured:
            raise ValueError("IMAP credentials missing.")
        client = imaplib.IMAP4_SSL(self.settings.imap_host, self.settings.imap_port)
        client.login(self.username, self.app_password)
        return client

    def _fetch(self, *, unseen_only: bool) -> list[tuple[bytes, EmailMessage]]:
        client = self._connect()
        try:
            client.select(self.settings.imap_folder, readonly=True)
            criterion = "UNSEEN" if unseen_only else "ALL"
            _, data = client.uid("SEARCH", None, criterion)
            ids = data[0].split() if data and data[0] else []
            messages: list[tuple[bytes, EmailMessage]] = []
            for uid in ids[-50:]:
                _, payload = client.uid("FETCH", uid, "(RFC822)")
                raw = rfc822_from_payload(payload)
                if not raw:
                    continue
                try:
                    messages.append((uid, self.parse(raw)))
                except Exception:
                    continue
            return messages
        finally:
            try:
                client.logout()
            except Exception:
                pass
