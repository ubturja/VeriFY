from fastapi.testclient import TestClient

from verify.api import app as app_module
from verify.domain.enums import Category, DecidedBy, Status
from verify.domain.models import EmailMessage, PipelineResult


def _seed_mismatch(store, email_id: str = "e1", field: str = "consignee") -> None:
    store.upsert(
        EmailMessage(email_id=email_id, sender="ops@test", subject="SI vs BL"),
        PipelineResult(
            email_id=email_id,
            category=Category.BL_COMPARISON,
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=[field],
            decided_by=DecidedBy.RULE,
        ),
    )


def test_confirm_endpoint_stamps_review_only(auth_client):
    _seed_mismatch(auth_client.tenant.store)
    missing = auth_client.post("/cases/missing/confirm", json={})
    assert missing.status_code == 404

    response = auth_client.post("/cases/e1/confirm", json={"note": "accepted"})
    assert response.status_code == 200
    body = response.json()
    assert body["review"]["action"] == "confirm"
    assert body["review"]["by"] == auth_client.tenant.email
    assert body["review"]["note"] == "accepted"
    assert body["result"]["status"] == "MISMATCH"
    assert body["result"]["defect_fields"] == ["consignee"]
    assert body["result"]["decided_by"] == "rule"

    audit = auth_client.get("/audit").json()
    assert audit[-1]["action"] == "confirm"
    assert auth_client.get("/metrics").json()["confirmed"] == 1


def test_correct_endpoint_rewrites_verdict(auth_client):
    _seed_mismatch(auth_client.tenant.store)
    missing = auth_client.post("/cases/missing/correct", json={"status": "OK"})
    assert missing.status_code == 404
    empty = auth_client.post("/cases/e1/correct", json={})
    assert empty.status_code == 400

    response = auth_client.post("/cases/e1/correct", json={"status": "OK", "note": "same group"})
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "OK"
    assert body["result"]["defect_fields"] == []
    assert body["result"]["decided_by"] == "human"
    assert body["review"]["action"] == "correct"
    assert body["review"]["by"] == auth_client.tenant.email
    assert auth_client.get("/metrics").json()["corrected"] == 1
    assert auth_client.get("/audit").json()[-1]["action"] == "correct"
    locked = auth_client.post("/cases/e1/confirm", json={})
    assert locked.status_code == 409
    assert auth_client.get("/metrics").json()["corrected"] == 1
    assert auth_client.get("/cases/e1").json()["review"]["action"] == "correct"


def test_submit_inline_attachment(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")
    response = auth_client.post(
        "/inbox/submit",
        json={
            "email_id": "manual-inline",
            "subject": "thanks",
            "body": "no documents",
            "attachments": [{"filename": "note.txt", "content_base64": "aGVsbG8="}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email_id"] == "manual-inline"
    assert body["attachments"][0]["filename"] == "note.txt"
    written = (
        tmp_path
        / "blob"
        / "manual"
        / auth_client.tenant.slug
        / "manual-inline"
        / "note.txt"
    )
    assert written.read_bytes() == b"hello"


def test_submit_rejects_path_traversal_email_id(auth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.settings, "local_blob_dir", tmp_path / "blob")
    response = auth_client.post(
        "/inbox/submit",
        json={
            "email_id": "../../etc/passwd",
            "subject": "thanks",
            "body": "no documents",
            "attachments": [{"filename": "note.txt", "content_base64": "aGVsbG8="}],
        },
    )
    assert response.status_code == 400
    assert "Invalid email id" in str(response.json()["detail"])
    assert not (tmp_path / "etc").exists()


def test_imap_poll_requires_app_password(auth_client):
    response = auth_client.post("/inbox/imap")
    assert response.status_code == 400
    assert "Sign in again" in response.json()["detail"]


def test_imap_poll_maps_network_errors(auth_client, isolated_tenants, monkeypatch):
    tenant = auth_client.tenant
    isolated_tenants.ensure(tenant.email, app_password="app-password-12345")

    async def boom(*_args, **_kwargs):
        raise OSError("nodename nor servname provided")

    monkeypatch.setattr(app_module, "poll_mailbox", boom)
    response = auth_client.post("/inbox/imap")
    assert response.status_code == 502
    assert "IMAP unavailable" in response.json()["detail"]


def test_cases_require_auth():
    client = TestClient(app_module.app)
    assert client.get("/cases").status_code == 401
    assert client.get("/audit").status_code == 401
    assert client.get("/metrics").status_code == 401


def test_dev_login_and_logout_flow():
    client = TestClient(app_module.app)
    login = client.post("/auth/dev-login", json={"email": "Someone@Example.com"})
    assert login.status_code == 200
    payload = login.json()
    assert payload["email"] == "someone@example.com"
    token = payload["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    me = client.get("/auth/me").json()
    assert me["email"] == "someone@example.com"
    assert me["imap_ready"] is False

    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_two_tenants_do_not_share_cases(isolated_tenants):
    alice = TestClient(app_module.app)
    bob = TestClient(app_module.app)
    alice.headers.update(
        {
            "Authorization": (
                f"Bearer {isolated_tenants.issue_token(isolated_tenants.ensure('alice@ex.com'))}"
            )
        }
    )
    bob.headers.update(
        {
            "Authorization": (
                f"Bearer {isolated_tenants.issue_token(isolated_tenants.ensure('bob@ex.com'))}"
            )
        }
    )
    alice_tenant = isolated_tenants.get("alice@ex.com")
    _seed_mismatch(alice_tenant.store, email_id="only-alice")
    alice_cases = alice.get("/cases").json()
    bob_cases = bob.get("/cases").json()
    assert [row["email_id"] for row in alice_cases] == ["only-alice"]
    assert bob_cases == []
