# Backend tests

```sh
cd backend
pip install -r requirements-dev.txt
pytest
```

Each test gets its own throwaway SQLite file and certificate folder (see
`conftest.py`'s `client` fixture) — nothing here ever touches
`app/data/kinderkreis.db`, so it's safe to run anytime, including against a
copy of the repo with real-looking demo data already in it.

Layout mirrors `app/main.py`'s route groups:

- `test_auth.py` — register/verify/login/logout/forgot+reset password
- `test_providers.py` — public directory + filters, the tagespflege's own
  profile (create/update), the Kindertagespflege/Großtagespflege business
  rules in `models.py`, capacity updates
- `test_certificates.py` — Qualifikationsnachweis upload/download/delete,
  including the validation limits (type/size/empty) and that a certificate
  is never visible to anyone but its owner
- `test_admin.py` — the separate admin username/password login, that an
  admin token and a user token are never interchangeable, the certificate
  review queue, verify/unverify, that the "✓ Geprüft" tick appears on the
  public listing only after verification, and that re-uploading or deleting
  a certificate resets it
- `test_bookings.py` — request/confirm/decline/cancel (pending *or*
  confirmed) and the permission checks around them, plus the notification +
  email a provider gets when Eltern cancels
- `test_notifications.py` — the in-app notifications those booking actions
  generate
