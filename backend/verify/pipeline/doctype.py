from __future__ import annotations

import re
from pathlib import Path

from verify.domain.enums import DocumentKind
from verify.text.normalize import collapse_ws

_SI_NAME = re.compile(
    r"(?:^|[_\-\s./])si(?:[_\-\s./]|$)|shipping[\s_\-]*instruction",
    re.IGNORECASE,
)
_BL_NAME = re.compile(
    r"(?:^|[_\-\s./])bl(?:[_\-\s./]|$)|bill[\s_\-]*of[\s_\-]*lading|draft[\s_\-]*bl",
    re.IGNORECASE,
)
_INLINE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp"}

_MARKERS: list[tuple[DocumentKind, tuple[str, ...]]] = [
    (
        DocumentKind.INVOICE,
        ("commercial invoice", "this is a commercial invoice", "invoice no.", "unit price"),
    ),
    (
        DocumentKind.PACKING_LIST,
        ("packing list", "carton no.", "packing list only"),
    ),
    (
        DocumentKind.CERTIFICATE_OF_ORIGIN,
        ("certificate of origin", "issuing authority", "country of origin"),
    ),
    (
        DocumentKind.SI,
        ("shipping instruction", "bill of lading instruction", "bl instruction"),
    ),
    (
        DocumentKind.BL,
        ("bill of lading (draft)", "bill of lading", "b/l no.", "b/l number"),
    ),
]


def is_inline_noise(filename: str) -> bool:
    return Path(filename).suffix.lower() in _INLINE_SUFFIXES


def filename_kind(filename: str) -> DocumentKind | None:
    """SI/BL from live mail names (SI-live-test.txt) and hackathon names (email_009_SI.txt)."""
    name = Path(filename).name
    si = bool(_SI_NAME.search(name))
    bl = bool(_BL_NAME.search(name))
    if bl and not si:
        return DocumentKind.BL
    if si and not bl:
        return DocumentKind.SI
    if bl:
        return DocumentKind.BL
    return None


def detect_kind(filename: str, text: str) -> DocumentKind:
    head = collapse_ws(text[:2000]).casefold()
    filename_hint = filename_kind(filename)

    for kind, markers in _MARKERS:
        if any(marker in head for marker in markers):
            return kind

    if filename_hint:
        return filename_hint
    return DocumentKind.UNKNOWN
