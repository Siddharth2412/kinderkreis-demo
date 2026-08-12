import io

from app import db
from tests.conftest import auth_headers

PDF_BYTES = b"%PDF-1.4 fake certificate content for tests"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake png content for tests"


def _upload(client, token, filename="zertifikat.pdf", content=PDF_BYTES, content_type="application/pdf"):
    return client.post(
        "/api/providers/me/certificate",
        headers=auth_headers(token),
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_without_profile_rejected(client, tagespflege):
    res = _upload(client, tagespflege["token"])
    assert res.status_code == 404


def test_upload_requires_tagespflege_role(client, eltern):
    res = _upload(client, eltern["token"])
    assert res.status_code == 403


def test_upload_requires_authentication(client):
    res = client.post(
        "/api/providers/me/certificate", files={"file": ("x.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}
    )
    assert res.status_code == 401


def test_upload_rejects_disallowed_content_type(client, provider_profile, tagespflege):
    res = _upload(client, tagespflege["token"], filename="cert.txt", content=b"hello", content_type="text/plain")
    assert res.status_code == 415


def test_upload_rejects_empty_file(client, provider_profile, tagespflege):
    res = _upload(client, tagespflege["token"], content=b"")
    assert res.status_code == 422


def test_upload_rejects_oversized_file(client, provider_profile, tagespflege, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "CERTIFICATE_MAX_BYTES", 10)  # shrink the cap so the test stays fast
    res = _upload(client, tagespflege["token"], content=PDF_BYTES)
    assert res.status_code == 413


def test_upload_success_marks_has_certificate(client, provider_profile, tagespflege):
    res = _upload(client, tagespflege["token"])
    assert res.status_code == 200
    assert res.json()["has_certificate"] is True

    me = client.get("/api/providers/me", headers=auth_headers(tagespflege["token"])).json()
    assert me["provider"]["has_certificate"] is True


def test_upload_never_exposed_on_public_listing(client, provider_profile, tagespflege):
    _upload(client, tagespflege["token"])
    public = client.get(f"/api/providers/{provider_profile['id']}").json()
    assert public["has_certificate"] is True
    assert "certificate_filename" not in public
    assert "certificate_content_type" not in public


def test_download_roundtrips_bytes_and_metadata(client, provider_profile, tagespflege):
    _upload(client, tagespflege["token"], filename="nachweis.pdf", content=PDF_BYTES)
    res = client.get("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.content == PDF_BYTES
    assert res.headers["content-type"] == "application/pdf"
    assert "nachweis.pdf" in res.headers["content-disposition"]


def test_download_preserves_original_filename_with_spaces(client, provider_profile, tagespflege):
    # Starlette's FileResponse RFC-5987-encodes non-ASCII-safe filenames
    # (spaces included) as filename*=utf-8''..., rather than a plain
    # filename="..." — assert on the encoded form actually produced.
    _upload(client, tagespflege["token"], filename="Mein Nachweis.pdf", content=PDF_BYTES)
    res = client.get("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert "Mein%20Nachweis.pdf" in res.headers["content-disposition"]


def test_download_requires_tagespflege_role(client, eltern):
    res = client.get("/api/providers/me/certificate", headers=auth_headers(eltern["token"]))
    assert res.status_code == 403


def test_download_without_certificate_404(client, provider_profile, tagespflege):
    res = client.get("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 404


def test_reupload_with_different_extension_replaces_old_file(client, provider_profile, tagespflege, tmp_path):
    _upload(client, tagespflege["token"], filename="a.pdf", content=PDF_BYTES, content_type="application/pdf")
    on_disk_after_first = list(db.CERTIFICATES_DIR.iterdir())
    assert len(on_disk_after_first) == 1
    assert on_disk_after_first[0].suffix == ".pdf"

    _upload(client, tagespflege["token"], filename="b.png", content=PNG_BYTES, content_type="image/png")
    on_disk_after_second = list(db.CERTIFICATES_DIR.iterdir())
    assert len(on_disk_after_second) == 1  # old .pdf was removed, not left behind
    assert on_disk_after_second[0].suffix == ".png"

    res = client.get("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.content == PNG_BYTES


def test_delete_removes_file_and_flag(client, provider_profile, tagespflege):
    _upload(client, tagespflege["token"])
    assert len(list(db.CERTIFICATES_DIR.iterdir())) == 1

    res = client.delete("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json()["has_certificate"] is False
    assert list(db.CERTIFICATES_DIR.iterdir()) == []

    res = client.get("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 404


def test_delete_requires_tagespflege_role(client, eltern):
    res = client.delete("/api/providers/me/certificate", headers=auth_headers(eltern["token"]))
    assert res.status_code == 403


def test_delete_without_profile_404(client, tagespflege):
    res = client.delete("/api/providers/me/certificate", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 404


def test_certificate_is_private_to_its_own_owner(client, provider_profile, tagespflege):
    """A second tagespflege account with its own profile must never see the
    first account's certificate through the "me" endpoints."""
    _upload(client, tagespflege["token"])

    from tests.conftest import VALID_PROVIDER_PAYLOAD, register_and_verify
    other = register_and_verify(client, "other-provider@example.test", role="tagespflege", name="Other")
    client.post("/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(other["token"]))

    res = client.get("/api/providers/me/certificate", headers=auth_headers(other["token"]))
    assert res.status_code == 404
