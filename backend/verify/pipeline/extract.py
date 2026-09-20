from __future__ import annotations

import io
from pathlib import Path

from verify.domain.enums import DocumentKind
from verify.domain.models import Evidence, ExtractedDocument, ExtractedField
from verify.pipeline.doctype import detect_kind
from verify.text.labels import canonical_field
from verify.text.normalize import _is_noisy, collapse_ws, is_blank_token, nfkc, party_name_only


def _field(name: str, value: str | None, attachment: str, locator: str) -> ExtractedField:
    cleaned = party_name_only(value) if name in {"shipper", "consignee", "notify_party"} else value
    blank = is_blank_token(cleaned)
    return ExtractedField(
        name=name,
        value=None if blank else (collapse_ws(cleaned) if cleaned else None),
        confidence=0.0 if blank else 0.9,
        blank_token=blank,
        evidence=Evidence(attachment=attachment, locator=locator, snippet=(value or "")[:200]),
    )


def extract_from_bytes(filename: str, payload: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    if not payload:
        return ExtractedDocument(
            kind=DocumentKind.UNREADABLE,
            attachment=filename,
            unreadable=True,
        )
    try:
        if suffix in {".txt", ".csv"}:
            text = payload.decode("utf-8", errors="replace")
            return extract_from_text(filename, text)
        if suffix in {".xlsx", ".xls"}:
            return _from_xlsx(filename, payload)
        if suffix == ".docx":
            return _from_docx(filename, payload)
        if suffix == ".pdf":
            return _from_pdf(filename, payload)
    except Exception:
        return ExtractedDocument(
            kind=DocumentKind.UNREADABLE,
            attachment=filename,
            unreadable=True,
            raw_text="",
        )
    text = payload.decode("utf-8", errors="replace")
    return extract_from_text(filename, text)


def extract_from_text(filename: str, text: str) -> ExtractedDocument:
    kind = detect_kind(filename, text)
    fields: dict[str, ExtractedField] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = nfkc(raw)
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        field = canonical_field(label)
        if not field or field in fields:
            continue
        fields[field] = _field(field, value, filename, f"line:{line_no}")
    return ExtractedDocument(
        kind=kind,
        attachment=filename,
        fields=fields,
        raw_text=text,
        unreadable=False,
    )


def _from_xlsx(filename: str, payload: bytes) -> ExtractedDocument:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(payload), data_only=True)
    ws = wb.active
    rows: list[tuple[str, str]] = []
    text_parts: list[str] = []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if cell is None else str(cell) for cell in row]
        text_parts.append(" | ".join(cells))
        if len(cells) >= 2 and cells[0] and cells[1]:
            rows.append((cells[0], cells[1]))
    text = "\n".join(text_parts)
    kind = detect_kind(filename, text)
    fields: dict[str, ExtractedField] = {}
    for label, value in rows:
        field = canonical_field(label)
        if field and field not in fields:
            fields[field] = _field(field, value, filename, f"xlsx:{label}")
    # First row is sometimes the bare shipper name with an empty label.
    if "shipper" not in fields and rows:
        first_label, first_value = rows[0]
        if not canonical_field(first_label) and first_label.strip():
            fields["shipper"] = _field("shipper", first_label, filename, "xlsx:header")
    return ExtractedDocument(kind=kind, attachment=filename, fields=fields, raw_text=text)


def _from_docx(filename: str, payload: bytes) -> ExtractedDocument:
    from docx import Document

    document = Document(io.BytesIO(payload))
    text_parts = [p.text for p in document.paragraphs]
    fields: dict[str, ExtractedField] = {}
    for table in document.tables:
        for row in table.rows:
            cells = [collapse_ws(cell.text) for cell in row.cells]
            if len(cells) >= 2:
                text_parts.append(f"{cells[0]}: {cells[1]}")
                field = canonical_field(cells[0])
                if field and field not in fields:
                    fields[field] = _field(field, cells[1], filename, f"docx:{cells[0]}")
    text = "\n".join(text_parts)
    kind = detect_kind(filename, text)
    _harvest_pdf_totals(filename, text, fields)
    return ExtractedDocument(kind=kind, attachment=filename, fields=fields, raw_text=text)


def _from_pdf(filename: str, payload: bytes) -> ExtractedDocument:
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        return ExtractedDocument(
            kind=DocumentKind.UNREADABLE,
            attachment=filename,
            unreadable=True,
        )
    text = "\n".join(pages)
    if not collapse_ws(text):
        return ExtractedDocument(
            kind=DocumentKind.UNREADABLE,
            attachment=filename,
            unreadable=True,
            raw_text="",
        )
    doc = extract_from_text(filename, text)
    for name, field in _pdf_fields(filename, text).items():
        doc.fields.setdefault(name, field)
    layout_fields = _pdf_layout_fields(filename, payload)
    for name, field in layout_fields.items():
        current = doc.fields.get(name)
        if current is None or _is_noisy(current.value):
            doc.fields[name] = field
    _harvest_pdf_totals(filename, text, doc.fields)
    return doc


def _pdf_fields(filename: str, text: str) -> dict[str, ExtractedField]:
    from verify.text.labels import LABEL_SYNONYMS

    fields: dict[str, ExtractedField] = {}
    pending: str | None = None
    for raw in text.splitlines():
        folded = collapse_ws(raw)
        if not folded:
            continue
        lower = folded.casefold()
        matched = False
        for field, labels in LABEL_SYNONYMS.items():
            for label in sorted(labels, key=len, reverse=True):
                prefix = label.casefold()
                if lower == prefix or lower.startswith(prefix + " ") or lower.startswith(prefix + ":"):
                    remainder = folded[len(label) :].lstrip(" :")
                    if remainder:
                        fields.setdefault(field, _field(field, remainder, filename, f"pdf-line:{field}"))
                        pending = None
                    else:
                        pending = field
                    matched = True
                    break
            if matched:
                break
        if matched:
            continue
        if pending and pending not in fields:
            fields[pending] = _field(pending, folded, filename, f"pdf:{pending}")
            pending = None
    return fields


def _harvest_pdf_totals(filename: str, text: str, fields: dict[str, ExtractedField]) -> None:
    import re

    if "container_count" not in fields:
        match = re.search(r"(?:no\.?\s*of\s*containers|container count)[:\s]+(\d+\s*[xX×][^\n]*)", text, re.I)
        if match:
            fields["container_count"] = _field("container_count", match.group(1), filename, "pdf:containers")
    if "gross_weight_kg" not in fields:
        match = re.search(
            r"(?:total\s+)?(?:gross\s*(?:weight|wt)[^:\n]{0,24})[:\s]+([\d,]+(?:\.\d+)?\s*(?:kg|kgs)?)",
            text,
            re.I,
        )
        if match:
            fields["gross_weight_kg"] = _field("gross_weight_kg", match.group(1), filename, "pdf:gross")


def _pdf_layout_fields(filename: str, payload: bytes) -> dict[str, ExtractedField]:
    """Use x-position so labels on the left are not merged with values on the right."""
    import pdfplumber

    from verify.text.labels import canonical_field

    fields: dict[str, ExtractedField] = {}
    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            page = pdf.pages[0]
            words = page.extract_words() or []
    except Exception:
        return fields
    rows: dict[int, list[dict]] = {}
    for word in words:
        key = int(round(float(word["top"]) / 3) * 3)
        rows.setdefault(key, []).append(word)
    for _, row in sorted(rows.items()):
        row.sort(key=lambda item: float(item["x0"]))
        left = [w["text"] for w in row if float(w["x0"]) < 150]
        right = [w["text"] for w in row if float(w["x0"]) >= 150]
        if not left or not right:
            continue
        field = canonical_field(" ".join(left))
        if field and field not in fields:
            fields[field] = _field(field, " ".join(right), filename, f"pdf-x:{field}")
    return fields

