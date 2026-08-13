from datetime import date, timedelta

from tests.conftest import auth_headers

FUTURE_DATE = (date.today() + timedelta(days=30)).isoformat()

BOOKING_PAYLOAD = {
    "children": [{"name": "Ben", "age_months": 20}],
    "start_date": FUTURE_DATE,
    "start_hour": 9,
    "end_hour": 15,
    "parent_address": "Beispielweg 2, 54321 Beispielstadt",
    "parent_phone": "0987654321",
}


def test_empty_notifications_initially(client, tagespflege):
    res = client.get("/api/notifications", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json() == {"notifications": [], "unread_count": 0}


def test_booking_request_notifies_provider(client, provider_profile, eltern, tagespflege):
    client.post(
        "/api/bookings",
        json={"provider_id": provider_profile["id"], **BOOKING_PAYLOAD},
        headers=auth_headers(eltern["token"]),
    )
    res = client.get("/api/notifications", headers=auth_headers(tagespflege["token"]))
    body = res.json()
    assert body["unread_count"] == 1
    assert body["notifications"][0]["type"] == "booking_requested"
    assert body["notifications"][0]["is_read"] is False


def test_confirm_notifies_parent(client, provider_profile, eltern, tagespflege):
    booking = client.post(
        "/api/bookings",
        json={"provider_id": provider_profile["id"], **BOOKING_PAYLOAD},
        headers=auth_headers(eltern["token"]),
    ).json()
    client.post(f"/api/bookings/{booking['id']}/confirm", headers=auth_headers(tagespflege["token"]))

    res = client.get("/api/notifications", headers=auth_headers(eltern["token"]))
    types = [n["type"] for n in res.json()["notifications"]]
    assert "booking_confirmed" in types


def test_decline_notifies_parent(client, provider_profile, eltern, tagespflege):
    booking = client.post(
        "/api/bookings",
        json={"provider_id": provider_profile["id"], **BOOKING_PAYLOAD},
        headers=auth_headers(eltern["token"]),
    ).json()
    client.post(
        f"/api/bookings/{booking['id']}/decline",
        json={"reason": "Kein Platz mehr."},
        headers=auth_headers(tagespflege["token"]),
    )

    res = client.get("/api/notifications", headers=auth_headers(eltern["token"]))
    types = [n["type"] for n in res.json()["notifications"]]
    assert "booking_declined" in types


def test_mark_single_notification_read(client, provider_profile, eltern, tagespflege):
    client.post(
        "/api/bookings",
        json={"provider_id": provider_profile["id"], **BOOKING_PAYLOAD},
        headers=auth_headers(eltern["token"]),
    )
    notif_id = client.get("/api/notifications", headers=auth_headers(tagespflege["token"])).json()[
        "notifications"
    ][0]["id"]

    res = client.post(f"/api/notifications/{notif_id}/read", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200

    body = client.get("/api/notifications", headers=auth_headers(tagespflege["token"])).json()
    assert body["unread_count"] == 0


def test_mark_all_notifications_read(client, provider_profile, eltern, tagespflege):
    for _ in range(3):
        client.post(
            "/api/bookings",
            json={"provider_id": provider_profile["id"], **BOOKING_PAYLOAD},
            headers=auth_headers(eltern["token"]),
        )
    assert client.get(
        "/api/notifications", headers=auth_headers(tagespflege["token"])
    ).json()["unread_count"] == 3

    res = client.post("/api/notifications/read-all", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200

    body = client.get("/api/notifications", headers=auth_headers(tagespflege["token"])).json()
    assert body["unread_count"] == 0


def test_notifications_require_authentication(client):
    res = client.get("/api/notifications")
    assert res.status_code == 401
