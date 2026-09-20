from email.message import EmailMessage as StdEmail

from verify.config import Settings
from verify.providers.mail.imap import ImapMailSource, safe_email_id


def test_safe_email_id_strips_brackets():
    assert safe_email_id("<abc/def@mail.gmail.com>") == "abc_def@mail.gmail.com"


def test_imap_parse_persists_attachment(tmp_path, monkeypatch):
    monkeypatch.setenv("VERIFY_LOCAL_BLOB_DIR", str(tmp_path / "blob"))
    settings = Settings()
    source = ImapMailSource(settings)
    message = StdEmail()
    message["From"] = "ops@carrier.test"
    message["Subject"] = "Draft BL for review"
    message["Message-ID"] = "<unit-imap-1@test>"
    message.set_content("Please compare the attached SI and draft BL.")
    message.add_attachment(b"SHIPPER: ACME", maintype="text", subtype="plain", filename="si.txt")
    parsed = source.parse(message.as_bytes())
    assert parsed.email_id == "unit-imap-1@test"
    assert parsed.source == "imap"
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "si.txt"
    assert source.read_bytes(parsed.attachments[0].path) == b"SHIPPER: ACME"
