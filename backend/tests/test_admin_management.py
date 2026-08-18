"""Super-admin-only endpoints for creating/resetting/deactivating other
admin accounts. `admin` (tests/conftest.py) is always the sole bootstrap
super admin; regular admins created here go through complete_admin_login()
themselves to prove the created-by-super-admin flow actually works
end-to-end (own enrollment, own separate secret)."""

import pyotp

from tests.conftest import auth_headers, complete_admin_login

NEW_ADMIN = {"username": "reviewer1", "password": "reviewerpass123"}


def test_super_admin_can_create_admin(client, admin):
    res = client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    assert res.status_code == 201
    body = res.json()
    assert body["username"] == NEW_ADMIN["username"]
    assert body["role"] == "admin"
    assert body["is_active"] is True
    assert body["totp_enrolled"] is False
    # never leaks credentials/secrets back through this endpoint
    assert "hashed_password" not in body
    assert "totp_secret" not in body


def test_create_admin_duplicate_username_409(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    res = client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    assert res.status_code == 409


def test_new_admin_first_login_forces_enrollment(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": NEW_ADMIN["password"]}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "enroll"
    assert body["secret"]

    session = complete_admin_login(client, NEW_ADMIN["username"], NEW_ADMIN["password"])
    assert session["is_super_admin"] is False


def test_admin_list_includes_super_admin_and_created_admins(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    res = client.get("/api/admin/admins", headers=auth_headers(admin["token"]))
    assert res.status_code == 200
    usernames = {a["username"] for a in res.json()["admins"]}
    assert usernames == {admin["username"], NEW_ADMIN["username"]}


def test_non_super_admin_cannot_reach_admin_management_endpoints(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    regular = complete_admin_login(client, NEW_ADMIN["username"], NEW_ADMIN["password"])
    headers = auth_headers(regular["token"])

    assert client.get("/api/admin/admins", headers=headers).status_code == 403
    assert client.post("/api/admin/admins", json={"username": "x", "password": "xxxxxxxx"}, headers=headers).status_code == 403
    assert client.post(
        f"/api/admin/admins/{admin['username']}/reset-password",
        json={"new_password": "whatever123"}, headers=headers,
    ).status_code == 403
    assert client.post(f"/api/admin/admins/{admin['username']}/reset-2fa", headers=headers).status_code == 403
    assert client.post(f"/api/admin/admins/{admin['username']}/deactivate", headers=headers).status_code == 403


def test_admin_management_endpoints_require_authentication(client):
    assert client.get("/api/admin/admins").status_code == 401
    assert client.post("/api/admin/admins", json=NEW_ADMIN).status_code == 401
    assert client.post("/api/admin/admins/reviewer1/reset-password", json={"new_password": "x" * 10}).status_code == 401
    assert client.post("/api/admin/admins/reviewer1/reset-2fa").status_code == 401
    assert client.post("/api/admin/admins/reviewer1/deactivate").status_code == 401


def test_reset_password_forces_relogin(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    regular = complete_admin_login(client, NEW_ADMIN["username"], NEW_ADMIN["password"])

    res = client.post(
        f"/api/admin/admins/{NEW_ADMIN['username']}/reset-password",
        json={"new_password": "brandnewpass123"},
        headers=auth_headers(admin["token"]),
    )
    assert res.status_code == 200

    # Old session is dead.
    assert client.get("/api/admin/providers", headers=auth_headers(regular["token"])).status_code == 401
    # Old password no longer works.
    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": NEW_ADMIN["password"]}
    )
    assert res.status_code == 401
    # New password does, and 2FA is still enrolled (only the password changed).
    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": "brandnewpass123"}
    )
    assert res.status_code == 200
    assert res.json()["mode"] == "verify"


def test_reset_2fa_forces_reenrollment(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": NEW_ADMIN["password"]}
    )
    original_secret = res.json()["secret"]
    old_session = client.post(
        "/api/admin/login/2fa", json={"ticket": res.json()["ticket"], "code": pyotp.TOTP(original_secret).now()}
    ).json()

    res = client.post(
        f"/api/admin/admins/{NEW_ADMIN['username']}/reset-2fa", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 200

    # The old session is dead.
    assert client.get("/api/admin/providers", headers=auth_headers(old_session["token"])).status_code == 401

    # Next login re-enrolls with a brand-new, different secret.
    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": NEW_ADMIN["password"]}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "enroll"
    new_secret = body["secret"]
    assert new_secret != original_secret

    # A code generated from the old (reset-away) secret no longer verifies.
    stale_code = pyotp.TOTP(original_secret).now()
    res = client.post("/api/admin/login/2fa", json={"ticket": body["ticket"], "code": stale_code})
    assert res.status_code == 401


def test_deactivate_blocks_login(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    complete_admin_login(client, NEW_ADMIN["username"], NEW_ADMIN["password"])

    res = client.post(
        f"/api/admin/admins/{NEW_ADMIN['username']}/deactivate", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 200

    res = client.post(
        "/api/admin/login", json={"username": NEW_ADMIN["username"], "password": NEW_ADMIN["password"]}
    )
    assert res.status_code == 401


def test_deactivate_kills_active_session(client, admin):
    client.post("/api/admin/admins", json=NEW_ADMIN, headers=auth_headers(admin["token"]))
    regular = complete_admin_login(client, NEW_ADMIN["username"], NEW_ADMIN["password"])
    assert client.get("/api/admin/providers", headers=auth_headers(regular["token"])).status_code == 200

    client.post(f"/api/admin/admins/{NEW_ADMIN['username']}/deactivate", headers=auth_headers(admin["token"]))

    assert client.get("/api/admin/providers", headers=auth_headers(regular["token"])).status_code == 401


def test_cannot_target_super_admin_via_management_endpoints(client, admin):
    headers = auth_headers(admin["token"])
    assert client.post(
        f"/api/admin/admins/{admin['username']}/reset-password",
        json={"new_password": "irrelevant123"}, headers=headers,
    ).status_code == 400
    assert client.post(f"/api/admin/admins/{admin['username']}/reset-2fa", headers=headers).status_code == 400
    assert client.post(f"/api/admin/admins/{admin['username']}/deactivate", headers=headers).status_code == 400

    # The super admin's own session/credentials are completely unaffected.
    assert client.get("/api/admin/providers", headers=headers).status_code == 200
