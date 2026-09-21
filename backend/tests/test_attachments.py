import base64

import pytest

from verify.services.attachments import write_inline_attachment


def test_write_inline_attachment(tmp_path):
    ref = write_inline_attachment(
        email_id="m1",
        filename="si.txt",
        content_base64=base64.b64encode(b"SHIPPER: ACME").decode(),
        blob_root=tmp_path,
    )
    assert ref.filename == "si.txt"
    assert (tmp_path / "manual" / "m1" / "si.txt").read_bytes() == b"SHIPPER: ACME"


def test_write_inline_attachment_rejects_oversize(tmp_path):
    with pytest.raises(ValueError, match="exceeds"):
        write_inline_attachment(
            email_id="m1",
            filename="huge.bin",
            content_base64=base64.b64encode(b"abc").decode(),
            blob_root=tmp_path,
            max_bytes=2,
        )


def test_write_inline_attachment_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="Invalid email id"):
        write_inline_attachment(
            email_id="../../etc",
            filename="note.txt",
            content_base64=base64.b64encode(b"x").decode(),
            blob_root=tmp_path,
        )
    with pytest.raises(ValueError, match="Invalid filename"):
        write_inline_attachment(
            email_id="m1",
            filename="../secret.txt",
            content_base64=base64.b64encode(b"x").decode(),
            blob_root=tmp_path,
        )
    assert not (tmp_path / "secret.txt").exists()
