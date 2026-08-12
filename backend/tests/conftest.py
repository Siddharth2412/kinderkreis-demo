"""Shared pytest fixtures for the backend test suite.

Every test gets its own throwaway SQLite file and certificate folder (via the
`client` fixture below), so tests never touch the real dev database in
app/data/ and can run in any order without leaking state into each other.

IMPORTANT: the KINDERKREIS_DB_PATH env var below must be set before `app.db`
(and therefore `app.main`) is imported anywhere — db.py reads it once at
import time to compute DB_PATH. Setting it here, at conftest module level,
guarantees that happens before pytest imports any test module.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_SESSION_TMP_DIR = tempfile.mkdtemp(prefix="kinderkreis-test-")
os.environ.setdefault("KINDERKREIS_DB_PATH", str(Path(_SESSION_TMP_DIR) / "session-import.db"))

from fastapi.testclient import TestClient  # noqa: E402  (must follow the env var above)

from app import db  # noqa: E402
from app.data import SEED_PROVIDERS  # noqa: E402
from app.main import app  # noqa: E402

DEFAULT_PASSWORD = "testpass123"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient backed by a fresh SQLite DB + certificates folder per test.

    Route handlers call `db.<function>(...)`, looking up `DB_PATH`/
    `CERTIFICATES_DIR` on the module object at call time, so monkeypatching
    those attributes here is enough to redirect every db.py function without
    touching app.main at all.
    """
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "kinderkreis.db")
    monkeypatch.setattr(db, "CERTIFICATES_DIR", tmp_path / "certificates")
    db.init_db()
    db.CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
    db.seed_providers_if_empty([p.model_dump() for p in SEED_PROVIDERS])

    with TestClient(app) as c:
        yield c


def get_otp(purpose: str, email: str) -> str:
    """Reads a pending OTP straight from the DB — the app only ever "sends"
    it by email, and SMTP_HOST is unset in tests so that just logs it (see
    app.main._send_email). Going through the DB is faster and doesn't
    depend on log formatting."""
    record = db.get_otp(purpose, email.lower().strip())
    assert record, f"no pending {purpose!r} OTP for {email!r}"
    return record["otp"]


def register_and_verify(
    client: TestClient, email: str, role: str = "eltern", name: str = "Test User",
    password: str = DEFAULT_PASSWORD,
) -> dict:
    """Registers + verifies a fresh account and returns the login payload
    (token, name, email, role) exactly as /api/auth/verify-email does."""
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    assert res.status_code == 201, res.text
    otp = get_otp("verify", email)
    res = client.post("/api/auth/verify-email", json={"email": email, "otp": otp})
    assert res.status_code == 200, res.text
    return res.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


VALID_PROVIDER_PAYLOAD = {
    "name": "Test Anbieterin",
    "city": "Teststadt",
    "min_age_months": 0,
    "max_age_months": 36,
    "care_type": "individual",
    "staff_count": 1,
    "capacity_total": 5,
    "capacity_used": 0,
    "qualification_hours": 300,
    "practicum_hours": 80,
    "has_pflegeerlaubnis": True,
}


@pytest.fixture()
def tagespflege(client: TestClient) -> dict:
    """A verified tagespflege account with no provider profile yet."""
    return register_and_verify(client, "provider@example.test", role="tagespflege", name="Anke Provider")


@pytest.fixture()
def eltern(client: TestClient) -> dict:
    """A verified eltern account."""
    return register_and_verify(client, "parent@example.test", role="eltern", name="Petra Eltern")


@pytest.fixture()
def provider_profile(client: TestClient, tagespflege: dict) -> dict:
    """A bookable provider profile (owner_email set) belonging to `tagespflege`."""
    res = client.post(
        "/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(tagespflege["token"])
    )
    assert res.status_code == 201, res.text
    return res.json()
