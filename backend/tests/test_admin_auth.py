"""Two-step admin login: password (step 1) then TOTP (step 2), covering
first-time enrollment, ordinary verification, and replay/expiry rejection.
See tests/conftest.py's complete_admin_login()/admin fixture for the
happy-path helper other test files rely on."""

import pyotp

from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, auth_headers, complete_admin_login


def test_admin_login_step1_returns_enroll_for_fresh_admin(client):
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["pending_2fa"] is True
    assert body["mode"] == "enroll"
    assert set(body.keys()) == {"pending_2fa", "mode", "ticket", "otpauth_uri", "secret"}
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert ADMIN_USERNAME in body["otpauth_uri"]


def test_admin_enrollment_completes_with_valid_code(client):
    session = complete_admin_login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert session["username"] == ADMIN_USERNAME
    assert session["is_super_admin"] is True
    assert session["token"]

    res = client.get("/api/admin/providers", headers=auth_headers(session["token"]))
    assert res.status_code == 200


def test_admin_enrollment_rejects_invalid_code(client):
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    ticket = res.json()["ticket"]

    res = client.post("/api/admin/login/2fa", json={"ticket": ticket, "code": "000000"})
    assert res.status_code == 401

    # A wrong code doesn't burn the ticket — the same ticket can be retried
    # with the correct code within its validity window.
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    body = res.json()
    code = pyotp.TOTP(body["secret"]).now()
    res = client.post("/api/admin/login/2fa", json={"ticket": ticket, "code": code})
    assert res.status_code == 200


def test_admin_login_step1_returns_verify_after_enrollment(client):
    complete_admin_login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "verify"
    assert body["ticket"]
    assert "otpauth_uri" not in body
    assert "secret" not in body


def test_admin_login_step2_rejects_wrong_code_when_enrolled(client):
    complete_admin_login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    ticket = res.json()["ticket"]
    res = client.post("/api/admin/login/2fa", json={"ticket": ticket, "code": "111111"})
    assert res.status_code == 401


def test_admin_login_step2_replay_rejected(client):
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    body = res.json()
    code = pyotp.TOTP(body["secret"]).now()

    res = client.post("/api/admin/login/2fa", json={"ticket": body["ticket"], "code": code})
    assert res.status_code == 200

    # Same code, fresh ticket (a second password login) — must still be
    # rejected as an already-consumed TOTP step, not accepted again.
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    ticket2 = res.json()["ticket"]
    res = client.post("/api/admin/login/2fa", json={"ticket": ticket2, "code": code})
    assert res.status_code == 401


def test_admin_login_step2_unknown_ticket_401(client):
    res = client.post("/api/admin/login/2fa", json={"ticket": "does-not-exist", "code": "123456"})
    assert res.status_code == 401


def test_admin_login_step2_expired_ticket_401(client):
    from app import db

    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    body = res.json()
    # Swap in an already-expired ticket rather than sleeping.
    db.delete_admin_login_ticket(body["ticket"])
    db.create_admin_login_ticket(body["ticket"], ADMIN_USERNAME, "2000-01-01T00:00:00")
    code = pyotp.TOTP(body["secret"]).now()
    res = client.post("/api/admin/login/2fa", json={"ticket": body["ticket"], "code": code})
    assert res.status_code == 401


def test_deactivated_admin_cannot_complete_login_step1(client, admin):
    from app import db

    db.deactivate_admin(ADMIN_USERNAME)
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert res.status_code == 401
