from tests.conftest import VALID_PROVIDER_PAYLOAD, auth_headers

SEED_COUNT = 5  # keep in sync with app/data.py


def test_list_providers_returns_seed_data(client):
    res = client.get("/api/providers")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == SEED_COUNT
    assert len(body["providers"]) == SEED_COUNT
    # Public fields present, internal ones never leaked.
    p = body["providers"][0]
    for field in ("is_certified", "free_places", "is_bookable", "has_certificate"):
        assert field in p
    assert "owner_email" not in p
    assert "certificate_filename" not in p


def test_list_providers_filters_by_city(client):
    res = client.get("/api/providers", params={"city": "göttingen"})  # case-insensitive
    assert res.status_code == 200
    body = res.json()
    assert body["count"] >= 1
    assert all(p["city"].lower() == "göttingen" for p in body["providers"])


def test_list_providers_filters_by_care_type(client):
    res = client.get("/api/providers", params={"care_type": "group"})
    assert res.status_code == 200
    assert all(p["care_type"] == "group" for p in res.json()["providers"])


def test_list_providers_filters_by_age(client):
    res = client.get("/api/providers", params={"age_months": 167})  # older than any seed range, still <= max (168)
    assert res.status_code == 200
    assert res.json()["count"] == 0


def test_list_providers_age_out_of_range_rejected(client):
    res = client.get("/api/providers", params={"age_months": 200})  # exceeds the ge=0, le=168 bound
    assert res.status_code == 422


def test_list_providers_available_only(client):
    res = client.get("/api/providers", params={"available_only": True})
    assert res.status_code == 200
    assert all(p["free_places"] > 0 for p in res.json()["providers"])


def test_list_providers_certified_only(client):
    res = client.get("/api/providers", params={"certified_only": True})
    assert res.status_code == 200
    assert all(p["is_certified"] for p in res.json()["providers"])


def test_get_provider_by_id(client):
    listed = client.get("/api/providers").json()["providers"][0]
    res = client.get(f"/api/providers/{listed['id']}")
    assert res.status_code == 200
    assert res.json()["name"] == listed["name"]


def test_get_unknown_provider_404(client):
    res = client.get("/api/providers/999999")
    assert res.status_code == 404


def test_list_cities(client):
    res = client.get("/api/meta/cities")
    assert res.status_code == 200
    assert "Göttingen" in res.json()["cities"]


def test_get_my_provider_before_profile_created(client, tagespflege):
    res = client.get("/api/providers/me", headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json() == {"provider": None}


def test_create_my_provider_success(client, tagespflege):
    res = client.post(
        "/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(tagespflege["token"])
    )
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == VALID_PROVIDER_PAYLOAD["name"]
    assert body["is_bookable"] is True
    assert body["is_certified"] is True  # 300 QHB / 80 practicum meets the threshold


def test_create_my_provider_twice_rejected(client, provider_profile, tagespflege):
    res = client.post(
        "/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(tagespflege["token"])
    )
    assert res.status_code == 409


def test_create_provider_forbidden_for_eltern(client, eltern):
    res = client.post(
        "/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(eltern["token"])
    )
    assert res.status_code == 403


def test_create_provider_age_range_validation(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "min_age_months": 40, "max_age_months": 10}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_create_provider_capacity_used_exceeds_total(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "capacity_total": 3, "capacity_used": 4}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_create_provider_individual_care_requires_one_staff(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "care_type": "individual", "staff_count": 2}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_create_provider_individual_care_capacity_cap(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "care_type": "individual", "capacity_total": 6}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_create_provider_group_care_requires_at_least_two_staff(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "care_type": "group", "staff_count": 1, "capacity_total": 8}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_create_provider_group_care_capacity_cap(client, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "care_type": "group", "staff_count": 2, "capacity_total": 11}
    res = client.post("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 422


def test_update_my_provider_without_profile_404(client, tagespflege):
    res = client.put(
        "/api/providers/me", json=VALID_PROVIDER_PAYLOAD, headers=auth_headers(tagespflege["token"])
    )
    assert res.status_code == 404


def test_update_my_provider_success(client, provider_profile, tagespflege):
    payload = {**VALID_PROVIDER_PAYLOAD, "city": "Neue Stadt"}
    res = client.put("/api/providers/me", json=payload, headers=auth_headers(tagespflege["token"]))
    assert res.status_code == 200
    assert res.json()["city"] == "Neue Stadt"
    assert res.json()["id"] == provider_profile["id"]


def test_update_capacity(client, provider_profile):
    provider_id = provider_profile["id"]
    res = client.patch(f"/api/providers/{provider_id}/capacity", params={"capacity_used": 3})
    assert res.status_code == 200
    assert res.json()["capacity_used"] == 3
    assert res.json()["free_places"] == 2


def test_update_capacity_over_total_rejected(client, provider_profile):
    provider_id = provider_profile["id"]
    res = client.patch(f"/api/providers/{provider_id}/capacity", params={"capacity_used": 999})
    assert res.status_code == 422


def test_update_capacity_unknown_provider_404(client):
    res = client.patch("/api/providers/999999/capacity", params={"capacity_used": 1})
    assert res.status_code == 404
