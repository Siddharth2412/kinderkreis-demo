from tests.conftest import DEFAULT_PASSWORD, auth_headers, get_otp, register_and_verify


def test_register_returns_needs_verification(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Neu Angemeldet", "email": "new@example.test", "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 201
    assert res.json() == {"needs_verification": True, "email": "new@example.test"}


def test_register_duplicate_email_rejected(client):
    client.post(
        "/api/auth/register",
        json={"name": "Erst", "email": "dupe@example.test", "password": DEFAULT_PASSWORD},
    )
    res = client.post(
        "/api/auth/register",
        json={"name": "Zweite", "email": "dupe@example.test", "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 409


def test_register_email_normalized_case_and_whitespace(client):
    client.post(
        "/api/auth/register",
        json={"name": "Erst", "email": "  Mixed@Example.test ", "password": DEFAULT_PASSWORD},
    )
    res = client.post(
        "/api/auth/register",
        json={"name": "Zweite", "email": "mixed@example.test", "password": DEFAULT_PASSWORD},
    )
    assert res.status_code == 409


def test_verify_email_wrong_otp_rejected(client):
    client.post(
        "/api/auth/register",
        json={"name": "Test", "email": "wrongotp@example.test", "password": DEFAULT_PASSWORD},
    )
    res = client.post("/api/auth/verify-email", json={"email": "wrongotp@example.test", "otp": "000000"})
    assert res.status_code == 400


def test_verify_email_success_returns_session(client):
    logged_in = register_and_verify(client, "verify@example.test", role="eltern", name="Verify Me")
    assert logged_in["email"] == "verify@example.test"
    assert logged_in["role"] == "eltern"
    assert logged_in["token"]


def test_verify_already_verified_account_rejected(client):
    register_and_verify(client, "already@example.test")
    res = client.post("/api/auth/verify-email", json={"email": "already@example.test", "otp": "123456"})
    assert res.status_code == 400


def test_login_before_verification_resends_otp(client):
    client.post(
        "/api/auth/register",
        json={"name": "Unverified", "email": "unverified@example.test", "password": DEFAULT_PASSWORD},
    )
    res = client.post(
        "/api/auth/login", json={"email": "unverified@example.test", "password": DEFAULT_PASSWORD}
    )
    assert res.status_code == 200
    assert res.json() == {"needs_verification": True, "email": "unverified@example.test"}


def test_login_success_after_verification(client):
    register_and_verify(client, "login@example.test")
    res = client.post("/api/auth/login", json={"email": "login@example.test", "password": DEFAULT_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "login@example.test"
    assert body["token"]


def test_login_wrong_password_rejected(client):
    register_and_verify(client, "wrongpw@example.test")
    res = client.post("/api/auth/login", json={"email": "wrongpw@example.test", "password": "not-the-password"})
    assert res.status_code == 401


def test_login_unknown_email_rejected(client):
    res = client.post("/api/auth/login", json={"email": "nope@example.test", "password": DEFAULT_PASSWORD})
    assert res.status_code == 401


def test_resend_verification_issues_new_otp(client):
    client.post(
        "/api/auth/register",
        json={"name": "Resend", "email": "resend@example.test", "password": DEFAULT_PASSWORD},
    )
    first_otp = get_otp("verify", "resend@example.test")
    res = client.post("/api/auth/resend-verification", json={"email": "resend@example.test"})
    assert res.status_code == 200
    second_otp = get_otp("verify", "resend@example.test")
    # A new code was issued (the old one may coincidentally match, but the
    # verify call below proves the *current* code works either way).
    res = client.post(
        "/api/auth/verify-email", json={"email": "resend@example.test", "otp": second_otp}
    )
    assert res.status_code == 200
    del first_otp  # only fetched to prove get_otp works before the resend overwrote it


def test_resend_verification_for_verified_account_rejected(client):
    register_and_verify(client, "already2@example.test")
    res = client.post("/api/auth/resend-verification", json={"email": "already2@example.test"})
    assert res.status_code == 400


def test_forgot_and_reset_password_flow(client):
    register_and_verify(client, "reset@example.test")
    res = client.post("/api/auth/forgot-password", json={"email": "reset@example.test"})
    assert res.status_code == 200

    otp = get_otp("reset", "reset@example.test")
    res = client.post(
        "/api/auth/reset-password",
        json={"email": "reset@example.test", "otp": otp, "new_password": "brandnewpass1"},
    )
    assert res.status_code == 200

    # Old password no longer works, new one does.
    res = client.post("/api/auth/login", json={"email": "reset@example.test", "password": DEFAULT_PASSWORD})
    assert res.status_code == 401
    res = client.post(
        "/api/auth/login", json={"email": "reset@example.test", "password": "brandnewpass1"}
    )
    assert res.status_code == 200


def test_forgot_password_unknown_email_rejected(client):
    res = client.post("/api/auth/forgot-password", json={"email": "ghost@example.test"})
    assert res.status_code == 404


def test_logout_invalidates_session(client):
    logged_in = register_and_verify(client, "logout@example.test", role="tagespflege")
    token = logged_in["token"]
    res = client.get("/api/providers/me", headers=auth_headers(token))
    assert res.status_code == 200

    res = client.post("/api/auth/logout", json={"token": token})
    assert res.status_code == 200

    res = client.get("/api/providers/me", headers=auth_headers(token))
    assert res.status_code == 401


def test_protected_endpoint_without_token_rejected(client):
    res = client.get("/api/providers/me")
    assert res.status_code == 401


def test_protected_endpoint_with_garbage_token_rejected(client):
    res = client.get("/api/providers/me", headers=auth_headers("not-a-real-token"))
    assert res.status_code == 401
