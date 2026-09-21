from verify.domain.enums import DocumentKind
from verify.pipeline.doctype import detect_kind, filename_kind, is_inline_noise


def test_live_gmail_filenames():
    assert filename_kind("SI-live-test.txt") == DocumentKind.SI
    assert filename_kind("draft-BL-live-test.txt") == DocumentKind.BL
    assert filename_kind("email_009_SI.txt") == DocumentKind.SI
    assert filename_kind("email_009_BL.pdf") == DocumentKind.BL
    assert filename_kind("invoice.pdf") is None


def test_inline_images_are_noise():
    assert is_inline_noise("logo.png")
    assert not is_inline_noise("SI-live-test.txt")


def test_content_markers_beat_filename():
    kind = detect_kind("scan.txt", "BILL OF LADING (DRAFT)\nShipper: ACME")
    assert kind == DocumentKind.BL
