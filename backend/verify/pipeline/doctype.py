from __future__ import annotations

from verify.domain.enums import DocumentKind
from verify.text.normalize import collapse_ws

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


def detect_kind(filename: str, text: str) -> DocumentKind:
    name = filename.casefold()
    head = collapse_ws(text[:2000]).casefold()
    if "_si." in f"_{name}" or name.endswith("_si.txt") or "_si." in name:
        filename_hint = DocumentKind.SI
    elif "_bl." in name:
        filename_hint = DocumentKind.BL
    else:
        filename_hint = None

    for kind, markers in _MARKERS:
        if any(marker in head for marker in markers):
            return kind

    if filename_hint:
        return filename_hint
    return DocumentKind.UNKNOWN
