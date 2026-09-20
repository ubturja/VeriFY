from __future__ import annotations

from pathlib import Path

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
