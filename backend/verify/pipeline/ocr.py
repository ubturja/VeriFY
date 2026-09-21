"""OCR tier for scanned PDFs.

Runs entirely locally with pypdfium2 (rendering) and pytesseract (recognition).
Optional at runtime: if tesseract is not on PATH or the render fails, we return
an empty string and let the pipeline route the case to review as UNREADABLE.
"""

from __future__ import annotations

import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_LANGS = os.environ.get("VERIFY_OCR_LANGS", "eng+chi_sim+msa")
_DEFAULT_DPI = int(os.environ.get("VERIFY_OCR_DPI", "220"))
_MAX_PAGES = int(os.environ.get("VERIFY_OCR_MAX_PAGES", "6"))


@dataclass
class OcrOutcome:
    text: str
    pages: int
    ok: bool
    reason: str = ""


def ensure_tesseract() -> bool:
    """Use a system tesseract, or the user-local unpack under ~/.local/tesseract.

    CI and the API image install tesseract on PATH. A workstation that only has
    the unpacked debs still needs the binary, its shared library, and tessdata
    pointed at before pytesseract spawns the process.
    """
    try:
        import pytesseract
    except Exception:
        return False
    if shutil.which("tesseract") or shutil.which(getattr(pytesseract.pytesseract, "tesseract_cmd", "")):
        return True
    root = Path.home() / ".local" / "tesseract"
    binary = root / "usr" / "bin" / "tesseract"
    if not binary.is_file():
        return False
    pytesseract.pytesseract.tesseract_cmd = str(binary)
    lib_root = root / "usr" / "lib"
    lib_dir = next((path for path in lib_root.glob("*") if any(path.glob("libtesseract.so*"))), None)
    if lib_dir is not None:
        current = os.environ.get("LD_LIBRARY_PATH", "")
        parts = [part for part in current.split(":") if part]
        if str(lib_dir) not in parts:
            os.environ["LD_LIBRARY_PATH"] = ":".join([str(lib_dir), *parts])
    if not os.environ.get("TESSDATA_PREFIX"):
        for tessdata in (root / "usr" / "share").glob("tesseract-ocr/*/tessdata"):
            if tessdata.is_dir():
                os.environ["TESSDATA_PREFIX"] = str(tessdata)
                break
    return True


def tesseract_available() -> bool:
    if not ensure_tesseract():
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


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
    if not ensure_tesseract():
        return OcrOutcome(text="", pages=0, ok=False, reason="tesseract-missing")
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
