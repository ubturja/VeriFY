import imaplib
from email.message import EmailMessage as StdEmail

from verify.config import Settings
from verify.providers.mail.imap import ImapMailSource, gmail_login_error, normalize_app_password, safe_email_id


def test_app_password_drops_the_spaces_google_prints():
    assert normalize_app_password("abcd efgh ijkl mnop") == "abcdefghijklmnop"
    assert normalize_app_password("  abcd\n") == "abcd"


def test_verify_login_sends_the_compact_app_password(monkeypatch):
    sent: dict[str, str] = {}

    class FakeImap:
        def __init__(self, host: str, port: int) -> None:
            sent["host"] = host

        def login(self, user: str, password: str) -> None:
            sent["user"] = user
            sent["password"] = password

        def logout(self) -> None:
            sent["logged_out"] = "yes"

    monkeypatch.setattr("verify.providers.mail.imap.imaplib.IMAP4_SSL", FakeImap)
    source = ImapMailSource(
        Settings(),
        username="wesuffertogether22@gmail.com",
        app_password="abcd efgh ijkl mnop",
    )
    source.verify_login()
    assert sent["user"] == "wesuffertogether22@gmail.com"
    assert sent["password"] == "abcdefghijklmnop"
    assert sent["logged_out"] == "yes"


def test_account_password_gets_a_specific_rejection():
    error = gmail_login_error(
        imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] Invalid credentials (Failure)"),
        "not-an-app-password",
    )
    assert "16-character app password" in str(error)


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
