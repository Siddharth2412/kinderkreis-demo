import io

from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, VALID_PROVIDER_PAYLOAD, auth_headers, register_and_verify

PDF_BYTES = b"%PDF-1.4 fake certificate content for admin tests"


def _upload_certificate(client, token, content=PDF_BYTES):
    return client.post(
        "/api/providers/me/certificate",
        headers=auth_headers(token),
        files={"file": ("zertifikat.pdf", io.BytesIO(content), "application/pdf")},
    )


def test_admin_login_success(client):
    """Step 1 (username/password) alone never returns a session — every
    admin login requires TOTP 2FA. On a fresh DB this is the bootstrap
    admin's very first login, so it lands on the "enroll" branch (a fresh
    QR/secret to scan) rather than "verify". See test_admin_auth.py for the
    full two-step flow through to a working session."""
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["pending_2fa"] is True
    assert body["mode"] == "enroll"
    assert body["ticket"]
    assert body["otpauth_uri"]
    assert body["secret"]
    assert "token" not in body


def test_admin_login_wrong_password_rejected(client):
    res = client.post("/api/admin/login", json={"username": ADMIN_USERNAME, "password": "not-it"})
    assert res.status_code == 401


def test_admin_login_unknown_username_rejected(client):
    res = client.post("/api/admin/login", json={"username": "ghost", "password": ADMIN_PASSWORD})
    assert res.status_code == 401


def test_admin_token_is_separate_from_user_sessions(client, tagespflege):
    """A regular user's token must never work on an admin endpoint, and vice
    versa — the two auth realms use entirely separate session tables."""
    res = client.get("/api/admin/providers", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 401


def test_admin_endpoint_rejects_user_login_credentials_shape(client):
    # A tagespflege account's email/password combo isn't a valid admin
    # username/password pair either — no accidental overlap between the two
    # login forms.
    res = client.post(
        "/api/admin/login", json={"username": "provider@example.test", "password": "testpass123"}
    )
    assert res.status_code == 401


def test_admin_logout_invalidates_session(client, admin):
    res = client.get("/api/admin/providers", headers=auth_headers(admin["token"]))
    assert res.status_code == 200

    res = client.post("/api/admin/logout", json={"token": admin["token"]})
    assert res.status_code == 200

    res = client.get("/api/admin/providers", headers=auth_headers(admin["token"]))
    assert res.status_code == 401


def test_admin_endpoints_require_authentication(client):
    assert client.get("/api/admin/providers").status_code == 401
    assert client.get("/api/admin/providers/1/certificate").status_code == 401
    assert client.post("/api/admin/providers/1/certificate/verify").status_code == 401
    assert client.post("/api/admin/providers/1/certificate/unverify").status_code == 401


def test_admin_providers_list_empty_when_no_certificates(client, admin, provider_profile):
    res = client.get("/api/admin/providers", headers=auth_headers(admin["token"]))
    assert res.status_code == 200
    assert res.json() == {"providers": []}


def test_admin_providers_list_shows_uploaded_certificate(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    res = client.get("/api/admin/providers", headers=auth_headers(admin["token"]))
    assert res.status_code == 200
    providers = res.json()["providers"]
    assert len(providers) == 1
    p = providers[0]
    assert p["id"] == provider_profile["id"]
    assert p["owner_email"] == "provider@example.test"
    assert p["certificate_original_name"] == "zertifikat.pdf"
    assert p["certificate_verified"] is False
    assert p["certificate_verified_at"] is None
    # internal on-disk details are still not part of the admin dict either
    assert "certificate_filename" not in p
    assert "certificate_content_type" not in p


def test_admin_download_certificate(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    res = client.get(
        f"/api/admin/providers/{provider_profile['id']}/certificate", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 200
    assert res.content == PDF_BYTES
    assert res.headers["content-type"] == "application/pdf"


def test_admin_download_without_certificate_404(client, admin, provider_profile):
    res = client.get(
        f"/api/admin/providers/{provider_profile['id']}/certificate", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 404


def test_admin_download_unknown_provider_404(client, admin):
    res = client.get("/api/admin/providers/999999/certificate", headers=auth_headers(admin["token"]))
    assert res.status_code == 404


def test_admin_verify_certificate(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    res = client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 200
    body = res.json()
    assert body["certificate_verified"] is True
    assert body["certificate_verified_at"] is not None


def test_admin_verify_without_certificate_rejected(client, admin, provider_profile):
    res = client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 404


def test_admin_verify_unknown_provider_404(client, admin):
    res = client.post("/api/admin/providers/999999/certificate/verify", headers=auth_headers(admin["token"]))
    assert res.status_code == 404


def test_admin_unverify_certificate(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    res = client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/unverify", headers=auth_headers(admin["token"])
    )
    assert res.status_code == 200
    body = res.json()
    assert body["certificate_verified"] is False
    assert body["certificate_verified_at"] is None


def test_verification_tick_visible_on_public_listing(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    public_before = client.get(f"/api/providers/{provider_profile['id']}").json()
    assert public_before["certificate_verified"] is False

    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    public_after = client.get(f"/api/providers/{provider_profile['id']}").json()
    assert public_after["certificate_verified"] is True
    # still never leaks the admin/owner-only fields
    assert "certificate_verified_at" not in public_after
    assert "owner_email" not in public_after


def test_reupload_resets_verification(client, admin, provider_profile, tagespflege):
    """A verification is tied to one specific file — replacing it must
    require a fresh review, never silently carry the tick over."""
    _upload_certificate(client, tagespflege["token"])
    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    assert client.get(f"/api/providers/{provider_profile['id']}").json()["certificate_verified"] is True

    _upload_certificate(client, tagespflege["token"], content=b"%PDF-1.4 a completely different file")
    assert client.get(f"/api/providers/{provider_profile['id']}").json()["certificate_verified"] is False


def test_delete_certificate_resets_verification(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    client.delete("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))

    _upload_certificate(client, tagespflege["token"])
    assert client.get(f"/api/providers/{provider_profile['id']}").json()["certificate_verified"] is False


def test_admin_review_queue_excludes_providers_without_certificates(client, admin, provider_profile, tagespflege):
    other = register_and_verify(client, "second-provider@example.test", role="tagespflege", name="Second")
    client.post("/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(other["token"]))
    _upload_certificate(client, tagespflege["token"])

    res = client.get("/api/admin/providers", headers=auth_headers(admin["token"]))
    providers = res.json()["providers"]
    assert len(providers) == 1
    assert providers[0]["owner_email"] == "provider@example.test"


def test_verify_notifies_provider(client, admin, provider_profile, tagespflege):
    _upload_certificate(client, tagespflege["token"])
    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    res = client.get("/api/notifications", headers=auth_headers(tagespflege["token"]))
    types = [n["type"] for n in res.json()["notifications"]]
    assert "certificate_verified" in types


def test_verify_sends_email_to_owner(client, admin, provider_profile, tagespflege, caplog):
    """SMTP_HOST is unset in tests, so _send_email just logs instead of
    actually sending (see app.main._send_email) — good enough to prove the
    email was dispatched, to the right address, with the right content."""
    _upload_certificate(client, tagespflege["token"])
    with caplog.at_level("INFO", logger="kinderkreis"):
        res = client.post(
            f"/api/admin/providers/{provider_profile['id']}/certificate/verify",
            headers=auth_headers(admin["token"]),
        )
    assert res.status_code == 200

    email_logs = [r.message for r in caplog.records if r.message.startswith("[DEV] Email")]
    assert any("provider@example.test" in msg and "geprüft" in msg.lower() for msg in email_logs)


def test_unverify_does_not_send_email(client, admin, provider_profile, tagespflege, caplog):
    _upload_certificate(client, tagespflege["token"])
    client.post(
        f"/api/admin/providers/{provider_profile['id']}/certificate/verify", headers=auth_headers(admin["token"])
    )
    caplog.clear()
    with caplog.at_level("INFO", logger="kinderkreis"):
        client.post(
            f"/api/admin/providers/{provider_profile['id']}/certificate/unverify",
            headers=auth_headers(admin["token"]),
        )
    email_logs = [r.message for r in caplog.records if r.message.startswith("[DEV] Email")]
    assert email_logs == []
