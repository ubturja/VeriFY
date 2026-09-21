import pytest
from fastapi.testclient import TestClient

from verify.api import app as app_module
from verify.services.tenants import TenantRegistry, secret_key_or_dev


@pytest.fixture(autouse=True)
def isolated_tenants(tmp_path, monkeypatch):
    """Give each test its own tenant registry rooted in ``tmp_path`` so state
    from one test never leaks into another. Also disables the background
    IMAP poll so tests never touch a real mailbox."""
    monkeypatch.setattr(app_module.settings, "imap_autopoll", False)
    monkeypatch.setattr(app_module.settings, "imap_poll_seconds", 0)
    monkeypatch.setattr(app_module.settings, "tenants_dir", tmp_path / "tenants")
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")
    secret = secret_key_or_dev(
        app_module.settings.secret_key,
        artifacts_root=tmp_path,
        env="test",
    )
    registry = TenantRegistry(tmp_path / "tenants", secret_key=secret)
    monkeypatch.setattr(app_module, "tenants", registry)
    return registry


@pytest.fixture
def auth_client(isolated_tenants):
    """A ``TestClient`` already logged in as ``tester@verify.local``."""
    client = TestClient(app_module.app)
    tenant = isolated_tenants.ensure("tester@verify.local")
    token = isolated_tenants.issue_token(tenant)
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.tenant = tenant  # type: ignore[attr-defined]
    return client
