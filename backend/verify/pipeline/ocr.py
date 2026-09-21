"""OCR tier for scanned PDFs.

Runs entirely locally with pypdfium2 (rendering) and pytesseract (recognition).
Optional at runtime: if tesseract is not on PATH or the render fails, we return
an empty string and let the pipeline route the case to review as UNREADABLE.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

_DEFAULT_LANGS = os.environ.get("VERIFY_OCR_LANGS", "eng+chi_sim+msa")
_DEFAULT_DPI = int(os.environ.get("VERIFY_OCR_DPI", "220"))
_MAX_PAGES = int(os.environ.get("VERIFY_OCR_MAX_PAGES", "6"))


@dataclass
class OcrOutcome:
    text: str
    pages: int
    ok: bool
    reason: str = ""


def ocr_pdf(payload: bytes, *, langs: str = _DEFAULT_LANGS, dpi: int = _DEFAULT_DPI) -> OcrOutcome:
    if not payload:
        return OcrOutcome(text="", pages=0, ok=False, reason="empty")
    try:
        import pypdfium2 as pdfium  # local import so the module stays optional
    except Exception as exc:  # pragma: no cover - dep should be installed
        return OcrOutcome(text="", pages=0, ok=False, reason=f"pypdfium2:{exc}")
    try:
        import pytesseract
        from PIL import Image  # noqa: F401 - Pillow is used indirectly
    except Exception as exc:  # pragma: no cover
        return OcrOutcome(text="", pages=0, ok=False, reason=f"pytesseract:{exc}")
    try:
        document = pdfium.PdfDocument(io.BytesIO(payload))
    except Exception as exc:
        return OcrOutcome(text="", pages=0, ok=False, reason=f"pdf-open:{exc}")
    texts: list[str] = []
    page_count = min(len(document), _MAX_PAGES)
    scale = dpi / 72
    try:
        for index in range(page_count):
            page = document[index]
            image = page.render(scale=scale).to_pil()
            try:
                page_text = pytesseract.image_to_string(image, lang=langs)
            except pytesseract.TesseractNotFoundError:
                return OcrOutcome(text="", pages=page_count, ok=False, reason="tesseract-missing")
            except Exception as exc:
                return OcrOutcome(
                    text="\n".join(texts),
                    pages=index,
                    ok=False,
                    reason=f"tesseract:{exc}",
                )
            texts.append(page_text)
    finally:
        try:
            document.close()
        except Exception:
            pass
    combined = "\n".join(part for part in texts if part.strip())
    return OcrOutcome(text=combined, pages=page_count, ok=bool(combined.strip()))
