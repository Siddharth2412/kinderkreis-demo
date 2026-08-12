from datetime import date, timedelta

from tests.conftest import auth_headers

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()

VALID_BOOKING = {
    "child_name": "Mia",
    "child_age_months": 18,
    "start_date": FUTURE_DATE,
    "start_hour": 8,
    "end_hour": 14,
    "parent_address": "Musterstraße 1, 12345 Musterstadt",
    "parent_phone": "0123456789",
    "message": "Freuen uns auf die Betreuung!",
}


def _booking_payload(provider_id: int, **overrides) -> dict:
    return {"provider_id": provider_id, **VALID_BOOKING, **overrides}


def test_create_booking_success(client, provider_profile, eltern):
    payload = _booking_payload(provider_profile["id"])
    res = client.post("/api/bookings", json=payload, headers=auth_headers(eltern["token"]))
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"
    assert body["provider_name"] == provider_profile["name"]
    assert body["parent_name"] is None  # parent-facing view doesn't echo their own name


def test_create_booking_requires_eltern_role(client, provider_profile, tagespflege):
    payload = _booking_payload(provider_profile["id"])
    res = client.post("/api/bookings", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 403


def test_create_booking_against_unclaimed_seed_provider_rejected(client, eltern):
    seed_provider = client.get("/api/providers").json()["providers"][0]
    payload = _booking_payload(seed_provider["id"])
    res = client.post("/api/bookings", json=payload, headers=auth_headers(eltern["token"]))
    assert res.status_code == 409


def test_create_booking_unknown_provider_404(client, eltern):
    payload = _booking_payload(999999)
    res = client.post("/api/bookings", json=payload, headers=auth_headers(eltern["token"]))
    assert res.status_code == 404


def test_create_booking_end_before_start_rejected(client, provider_profile, eltern):
    payload = _booking_payload(provider_profile["id"], start_hour=14, end_hour=8)
    res = client.post("/api/bookings", json=payload, headers=auth_headers(eltern["token"]))
    assert res.status_code == 422


def test_create_booking_in_the_past_rejected(client, provider_profile, eltern):
    past_date = (date.today() - timedelta(days=1)).isoformat()
    payload = _booking_payload(provider_profile["id"], start_date=past_date)
    res = client.post("/api/bookings", json=payload, headers=auth_headers(eltern["token"]))
    assert res.status_code == 422


def test_list_my_bookings(client, provider_profile, eltern):
    client.post(
        "/api/bookings", json=_booking_payload(provider_profile["id"]), headers=auth_headers(eltern["token"])
    )
    res = client.get("/api/bookings/mine", headers=auth_headers(eltern["token"]))
    assert res.status_code == 200
    assert len(res.json()["bookings"]) == 1


def test_list_my_bookings_requires_eltern_role(client, tagespflege):
    res = client.get("/api/bookings/mine", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 403


def test_provider_sees_incoming_booking(client, provider_profile, eltern, tagespflege):
    client.post(
        "/api/bookings", json=_booking_payload(provider_profile["id"]), headers=auth_headers(eltern["token"])
    )
    res = client.get("/api/bookings/provider", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    body = res.json()
    assert body["has_profile"] is True
    assert len(body["bookings"]) == 1
    assert body["bookings"][0]["parent_name"] == "Petra Eltern"


def test_provider_bookings_without_profile(client, tagespflege):
    res = client.get("/api/bookings/provider", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json() == {"bookings": [], "has_profile": False}


def _create_pending_booking(client, provider_profile, eltern) -> int:
    res = client.post(
        "/api/bookings", json=_booking_payload(provider_profile["id"]), headers=auth_headers(eltern["token"])
    )
    return res.json()["id"]


def test_confirm_booking_success(client, provider_profile, eltern, tagespflege):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    res = client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"


def test_confirm_booking_wrong_owner_rejected(client, provider_profile, eltern):
    from tests.conftest import VALID_PROVIDER_PAYLOAD, register_and_verify

    booking_id = _create_pending_booking(client, provider_profile, eltern)
    other = register_and_verify(client, "impostor@example.test", role="tagespflege", name="Impostor")
    client.post("/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(other["token"]))

    res = client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers(other["token"]))
    assert res.status_code == 403


def test_confirm_already_processed_booking_rejected(client, provider_profile, eltern, tagespflege):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers(tagespflege["token"]))
    res = client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 409


def test_decline_booking_success(client, provider_profile, eltern, tagespflege):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    res = client.post(f"/api/bookings/{booking_id}/decline", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json()["status"] == "declined"


def test_cancel_booking_success(client, provider_profile, eltern):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_cancel_someone_elses_booking_rejected(client, provider_profile, eltern):
    from tests.conftest import register_and_verify

    booking_id = _create_pending_booking(client, provider_profile, eltern)
    other_eltern = register_and_verify(client, "other-parent@example.test", role="eltern", name="Other Parent")
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(other_eltern["token"]))
    assert res.status_code == 404


def test_cancel_confirmed_booking_success(client, provider_profile, eltern, tagespflege):
    """Eltern can back out of an already-confirmed booking too, not just a
    still-pending request — plans change after confirmation as well."""
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    client.post(f"/api/bookings/{booking_id}/confirm", headers=auth_headers(tagespflege["token"]))
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


def test_cancel_declined_booking_rejected(client, provider_profile, eltern, tagespflege):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    client.post(f"/api/bookings/{booking_id}/decline", headers=auth_headers(tagespflege["token"]))
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    assert res.status_code == 409


def test_cancel_already_cancelled_booking_rejected(client, provider_profile, eltern):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    assert res.status_code == 409


def test_cancel_notifies_provider(client, provider_profile, eltern, tagespflege):
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    res = client.get("/api/notifications", headers=auth_headers(tagespflege["token"]))
    types = [n["type"] for n in res.json()["notifications"]]
    assert "booking_cancelled" in types


def test_cancel_sends_email_to_provider(client, provider_profile, eltern, tagespflege, caplog):
    """SMTP_HOST is unset in tests, so _send_email just logs (see
    app.main._send_email) — enough to prove the cancellation email was
    dispatched to the provider's account email."""
    booking_id = _create_pending_booking(client, provider_profile, eltern)
    with caplog.at_level("INFO", logger="kinderkreis"):
        res = client.post(f"/api/bookings/{booking_id}/cancel", headers=auth_headers(eltern["token"]))
    assert res.status_code == 200

    email_logs = [r.message for r in caplog.records if r.message.startswith("[DEV] Email")]
    assert any("provider@example.test" in msg and "storniert" in msg for msg in email_logs)
