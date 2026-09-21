"""Per-mailbox tenants: encrypted app-password storage, sessions, and per-tenant CaseStore.

Nothing in this module hardcodes an email or a credential. Everything is keyed
by the address the user typed at login.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from verify.services.store import CaseStore
from verify.services.synonyms import SynonymStore

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_email(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("Enter a valid email address.")
    return cleaned


def _slug(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()[:16]


def _fernet_from(secret: str) -> Fernet:
    if not secret:
        raise ValueError("VERIFY_SECRET_KEY is required to store mailbox credentials.")
    try:
        Fernet(secret.encode())
        return Fernet(secret.encode())
    except Exception:
        digest = hashlib.sha256(secret.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


@dataclass
class Tenant:
    email: str
    slug: str
    store: CaseStore
    synonyms: SynonymStore
    imap_password_encrypted: str | None = None
    created_at: str = field(default_factory=_now)
    last_login_at: str | None = None


class TenantRegistry:
    """Filesystem-backed registry. State lives under ``root``.

    ``root/index.json``     mailbox metadata plus encrypted app passwords
    ``root/sessions.json``  active bearer tokens
    ``root/<slug>/state.json`` per-mailbox CaseStore
    """

    def __init__(self, root: Path, *, secret_key: str, store_suffix: str = ".json") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._sessions_path = self.root / "sessions.json"
        self._fernet = _fernet_from(secret_key)
        self._store_suffix = store_suffix
        self._tenants: dict[str, Tenant] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ storage

    def _store_path(self, slug: str) -> Path:
        return self.root / slug / f"state{self._store_suffix}"

    def _load(self) -> None:
        if self._index_path.is_file():
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            for slug, entry in (data.get("tenants") or {}).items():
                email = entry.get("email")
                if not email:
                    continue
                (self.root / slug).mkdir(parents=True, exist_ok=True)
                self._tenants[slug] = Tenant(
                    email=email,
                    slug=slug,
                    store=CaseStore(self._store_path(slug)),
                    synonyms=SynonymStore(self.root / slug / "synonyms.json"),
                    imap_password_encrypted=entry.get("password"),
                    created_at=entry.get("created_at") or _now(),
                    last_login_at=entry.get("last_login_at"),
                )
        if self._sessions_path.is_file():
            self._sessions = json.loads(self._sessions_path.read_text(encoding="utf-8")).get(
                "sessions", {}
            )

    def _save_index(self) -> None:
        data = {
            "tenants": {
                slug: {
                    "email": t.email,
                    "password": t.imap_password_encrypted,
                    "created_at": t.created_at,
                    "last_login_at": t.last_login_at,
                }
                for slug, t in self._tenants.items()
            }
        }
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _save_sessions(self) -> None:
        self._sessions_path.write_text(
            json.dumps({"sessions": self._sessions}, indent=2), encoding="utf-8"
        )

    # --------------------------------------------------------------- tenants

    def ensure(self, email: str, *, app_password: str | None = None) -> Tenant:
        email = normalize_email(email)
        slug = _slug(email)
        if slug not in self._tenants:
            (self.root / slug).mkdir(parents=True, exist_ok=True)
            self._tenants[slug] = Tenant(
                email=email,
                slug=slug,
                store=CaseStore(self._store_path(slug)),
                synonyms=SynonymStore(self.root / slug / "synonyms.json"),
            )
        tenant = self._tenants[slug]
        if app_password is not None:
            tenant.imap_password_encrypted = self._fernet.encrypt(app_password.encode()).decode()
        tenant.last_login_at = _now()
        self._save_index()
        return tenant

    def get(self, email: str) -> Tenant | None:
        try:
            return self._tenants.get(_slug(email))
        except ValueError:
            return None

    def by_slug(self, slug: str) -> Tenant | None:
        return self._tenants.get(slug)

    def all(self) -> list[Tenant]:
        return list(self._tenants.values())

    def decrypt_password(self, tenant: Tenant) -> str | None:
        if not tenant.imap_password_encrypted:
            return None
        try:
            return self._fernet.decrypt(tenant.imap_password_encrypted.encode()).decode()
        except InvalidToken:
            return None

    def forget_password(self, tenant: Tenant) -> None:
        tenant.imap_password_encrypted = None
        self._save_index()

    # --------------------------------------------------------------- sessions

    def issue_token(self, tenant: Tenant) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {"slug": tenant.slug, "at": _now()}
        self._save_sessions()
        return token

    def resolve_token(self, token: str) -> Tenant | None:
        if not token:
            return None
        entry = self._sessions.get(token)
        if not entry:
            return None
        return self._tenants.get(entry["slug"])

    def revoke_token(self, token: str) -> None:
        if not token:
            return
        if self._sessions.pop(token, None) is not None:
            self._save_sessions()


def secret_key_or_dev(
    secret: str,
    *,
    artifacts_root: Path,
    env: str,
    require: bool = False,
) -> str:
    """Return ``secret`` when set, otherwise mint one under ``artifacts_root``.

    When ``require`` is true (typically ``VERIFY_REQUIRE_SECRET_KEY=1``) an
    empty ``secret`` is a hard error so operators cannot accidentally ship a
    process that generates a fresh key on every deploy. Otherwise a key file
    is read or created at ``<artifacts_root>/.secret_key``. Outside of the
    ``local``/``test`` environments we emit a warning so operators know they
    should set ``VERIFY_SECRET_KEY`` explicitly to keep sessions and
    encrypted app passwords stable across container restarts.
    """

    if secret:
        return secret
    if require:
        raise RuntimeError(
            "VERIFY_SECRET_KEY is required (VERIFY_REQUIRE_SECRET_KEY=1)."
        )
    dev_key_path = Path(artifacts_root) / ".secret_key"
    dev_key_path.parent.mkdir(parents=True, exist_ok=True)
    if dev_key_path.is_file():
        return dev_key_path.read_text(encoding="utf-8").strip()
    generated = Fernet.generate_key().decode()
    dev_key_path.write_text(generated, encoding="utf-8")
    try:
        dev_key_path.chmod(0o600)
    except OSError:
        pass
    if env not in {"local", "test"}:
        import sys

        print(
            f"[verify] VERIFY_SECRET_KEY was empty in env={env!r}; a key was minted at "
            f"{dev_key_path}. Set VERIFY_SECRET_KEY in your deployment to keep sessions "
            "and encrypted app passwords stable across restarts.",
            file=sys.stderr,
        )
    return generated
