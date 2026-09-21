"""A scanned PDF has no text layer. OCR should recover the fields when tesseract is installed."""

from __future__ import annotations

import io

import pytest

from verify.pipeline.extract import extract_from_bytes
from verify.pipeline.ocr import tesseract_available


@pytest.mark.skipif(not tesseract_available(), reason="tesseract is not installed")
def test_scanned_pdf_is_read_by_ocr():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 900), "white")
    draw = ImageDraw.Draw(image)
    font = None
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            font = ImageFont.truetype(path, 36)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    lines = [
        "SHIPPER: ACME PTE LTD",
        "CONSIGNEE: GLOBAL LOGISTICS",
        "NOTIFY PARTY: GLOBAL LOGISTICS",
        "PORT OF LOADING: SINGAPORE",
        "PORT OF DISCHARGE: HAMBURG",
        "CONTAINER COUNT: 1 x 40HC",
        "GROSS WEIGHT: 10000 KG",
    ]
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += 70
    buffer = io.BytesIO()
    image.save(buffer, format="PDF")
    document = extract_from_bytes("scan.pdf", buffer.getvalue())
    assert document.unreadable is False
    assert document.language_hint and document.language_hint.startswith("ocr:")
    assert document.fields["shipper"].value
    assert "ACME" in document.fields["shipper"].value.upper()
