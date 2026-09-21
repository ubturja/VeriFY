from __future__ import annotations

import base64
from pathlib import Path

from verify.domain.models import AttachmentRef
from verify.providers.mail.hackathon import HackathonMailSource


def read_attachment(path: str, *, data_dir: Path | str | None = None) -> bytes:
    """Read bytes from an absolute blob path or a path under the hackathon bundle."""
    candidate = Path(path)
    if candidate.is_file():
        return candidate.read_bytes()
    if data_dir is None:
        raise FileNotFoundError(path)
    try:
        return HackathonMailSource(data_dir).read_bytes(path)
    except FileNotFoundError:
        return b""


def safe_blob_segment(value: str, *, label: str) -> str:
    text = str(value).strip()
    segment = Path(text.replace("\\", "/")).name
    if not segment or segment in {".", ".."} or segment != text:
        raise ValueError(f"Invalid {label}")
    return segment


def write_inline_attachment(
    *,
    email_id: str,
    filename: str,
    content_base64: str,
    blob_root: Path,
    tenant_slug: str,
    max_bytes: int = 15_000_000,
) -> AttachmentRef:
    """Persist a base64 attachment under ``blob_root/manual/<tenant_slug>/<email_id>/``.

    ``tenant_slug`` is required so two mailboxes that generate the same
    manual email id (for example both starting at ``manual-0001``) never
    overwrite each other's uploaded bytes on shared local disks.
    """

    raw = base64.b64decode(content_base64, validate=False)
    if len(raw) > max_bytes:
        raise ValueError(f"{filename or 'attachment'} exceeds {max_bytes} bytes")
    safe_id = safe_blob_segment(email_id, label="email id")
    safe_name = safe_blob_segment(filename or "attachment.bin", label="filename")
    safe_tenant = safe_blob_segment(tenant_slug, label="tenant")
    root = blob_root.resolve()
    tenant_root = (root / "manual" / safe_tenant).resolve()
    if not tenant_root.is_relative_to(root / "manual"):
        raise ValueError("Invalid tenant")
    dest_dir = (tenant_root / safe_id).resolve()
    if not dest_dir.is_relative_to(tenant_root):
        raise ValueError("Invalid email id")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / safe_name).resolve()
    if not dest.is_relative_to(dest_dir):
        raise ValueError("Invalid filename")
    dest.write_bytes(raw)
    return AttachmentRef(path=str(dest), filename=safe_name, size_bytes=len(raw))
