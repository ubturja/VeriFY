import pytest

from verify.api import app as app_module


@pytest.fixture(autouse=True)
def disable_background_imap(monkeypatch):
    monkeypatch.setattr(app_module.settings, "imap_autopoll", False)
    monkeypatch.setattr(app_module.settings, "imap_poll_seconds", 0)
