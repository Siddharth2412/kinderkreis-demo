# Kinderkreis — Demo (React + FastAPI)

A runnable demo of the Kinderkreis concept: parents search and browse
certified Kindertagespflege / Großtagespflege providers, send a provider a
booking request, and a logged-in Tagespflegeperson manages their own profile
and confirms or declines the requests they receive.

This is a **sample/demo**, not a production system: everything — providers,
users, sessions, OTPs — is persisted in a SQLite database
(`backend/app/data/kinderkreis.db`) so data survives a container restart.
Seed providers are only inserted the first time the database is created.
Creating or editing a provider profile requires a verified account with the
`tagespflege` role; the profile is mapped 1:1 to that account by email and
is never shown or editable from the public parent-facing page.

## Stack

- **Backend**: Python 3.11 + FastAPI, Pydantic models that encode the real
  regulatory rules (solo Kindertagespflege ≤ 5 children, Großtagespflege with
  2–3 staff ≤ 10 children, "certified" requires ≥300 QHB hours and ≥80
  practicum hours). All data (providers, users, sessions, OTPs) is persisted
  in SQLite (`backend/app/db.py`, stdlib `sqlite3`).
- **Frontend**: React 18 + Vite, no extra UI framework, styled to match the
  original Kinderkreis palette (forest green / honey, Fraunces + Inter).
- **Orchestration**: Docker Compose, two services (`backend`, `frontend`).

## Run it

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)

Stop with `Ctrl+C`, or `docker compose down` to remove the containers.

This is the local-dev setup: live-reload source mounts and the Vite dev
server on both services. See **Deploying to production** below for the
lean, static-build alternative when you actually deploy somewhere
resource-constrained.

## What you can do in the demo

- **Landing page** (logged-out front door): whoever isn't logged in lands
  here first, not directly in the directory — a hero with "Jetzt
  registrieren"/"Anmelden", a 3-step "So funktioniert's" explainer, a short
  "Warum Kinderkreis" section highlighting the QHB qualification display and
  the admin-verified certificate tick, and a contact section. A "Oder direkt
  Betreuungsangebote ansehen →" link lets you skip straight to the directory
  without an account, same as before this page existed. Contact details
  there (`frontend/src/components/LandingView.jsx`) are placeholders — swap
  them for the real ones when available.
- **Startseite** (nav link + clicking the logo): the landing page again if
  you're logged out, the directory if you're logged in — same link, the
  destination just depends on whether you have a session.
- **Directory** ("Betreuungsangebote ansehen" from the landing page, or the
  home page once logged in): visible to everyone — logged out, `eltern`, or
  `tagespflege` — filter by city, child's age, care type (individual vs.
  group), availability, and certification status. Click a card to see the
  full profile in a modal. Never shows any account or ownership info — just
  the public listing fields.
- **Profil bearbeiten** (nav link, only shown to a logged-in `tagespflege`
  account): "Mein Profil" — a page mapped to that account which shows the
  current listing (or an empty form the first time) and lets you create or
  update it. The backend validates the same regulatory constraints as the
  real workflow — e.g. it rejects a solo Kindertagespflege profile with
  capacity above 5, or a group profile with only 1 staff member — and
  returns a clear error if a rule is broken. Each account maps to at most
  one provider profile. Once a profile exists, its owner can also upload a
  Qualifikationsnachweis (PDF/JPG/PNG, ≤5MB) — the file itself is private to
  that account; the public directory only shows whether one was uploaded.
- **Buchungsanfrage** (from a provider's detail modal, `eltern` accounts
  only): send a booking request — child's name/age, desired date and
  start/end hour, the parent's address and phone number, an optional
  message — to a provider that has a linked `tagespflege` account. The
  requested date/time must be in the future and the end hour after the
  start hour; both are validated server-side. Unclaimed/seed profiles show
  an explanation instead of the form, since nobody is signed in to confirm
  a request against them.
- **Meine Anfragen** (nav link, `eltern`): the status of every booking
  request you've sent — offen/bestätigt/abgelehnt/storniert — with the
  option to cancel it, whether it's still open ("Anfrage zurückziehen") or
  already confirmed ("Buchung stornieren"); only a declined or already-
  cancelled one can't be cancelled again. Either way the owning
  Tagespflegeperson gets an in-app notification *and* an email (they may
  not be logged in when it happens, especially for an already-confirmed
  booking they may have blocked time out for).
- **Buchungsanfragen** (nav link, `tagespflege`): incoming requests for your
  own profile, with Confirm/Decline actions on open ones.
- **Notification bell** (nav, any logged-in account): an in-app inbox,
  polled every ~25s, that a `tagespflege` account uses to see new booking
  requests and an `eltern` account uses to see confirm/decline updates. When
  a `tagespflege` account confirms a booking, both sides additionally get an
  email (via the same SMTP plumbing used for OTPs — logged to the console
  in local dev if `SMTP_HOST` isn't set) with a generated `.ics` calendar
  invite attached, spanning the requested start/end hour on the agreed date
  and including the parent's address and phone in the event description, so
  either side can drop the appointment straight into their own calendar
  (`backend/app/calendar_invite.py` — no external calendar-account
  integration).

Seed data (5 sample providers across Göttingen, Hannover, and Braunschweig)
is loaded on backend startup so the directory isn't empty on first run. The
seed providers have no linked account, so — like the real workflow — they
can't receive booking requests until claimed by a `tagespflege` signup.

- **Admin** (footer link "Admin", separate from everything above): a plain
  username/password login — no email, no OTP, no `eltern`/`tagespflege`
  role, and its own session type entirely, so an admin token is never valid
  on a user endpoint or vice versa. Provisioned via `ADMIN_USERNAME`/
  `ADMIN_PASSWORD` in `.env` (defaults: `admin` / `admin123`) the first time
  the database is created — there's no admin signup form on purpose. The
  panel lists every provider that has uploaded a Qualifikationsnachweis,
  lets the admin open/download the file, and mark it "✓ Geprüft" (or
  retract that). That tick — and only that tick — is what parents see on
  the public directory next to a provider's certification status; the file
  itself always stays private to its owner and to admins. Re-uploading or
  deleting a certificate resets the tick, since a verification is tied to
  one specific file, never to "whatever is currently uploaded". Verifying
  also emails the Tagespflegeperson (same SMTP plumbing as OTPs/booking
  confirmations) in addition to the in-app notification, since they may not
  be logged in when it happens; retracting a verification does not send one.

## API endpoints

| Method | Path                              | Purpose                                   |
|--------|-----------------------------------|--------------------------------------------|
| GET    | `/api/providers`                  | List/filter providers (public)            |
| GET    | `/api/providers/{id}`             | Get one provider (public)                 |
| PATCH  | `/api/providers/{id}/capacity`    | Update how many places are currently used |
| GET    | `/api/meta/cities`                 | Distinct list of cities for the filter    |
| GET    | `/api/providers/me`                | 🔒🧑‍🍼 Own profile, or `{"provider": null}` if none yet |
| POST   | `/api/providers/me`                | 🔒🧑‍🍼 Create own profile (409 if one already exists) |
| PUT    | `/api/providers/me`                | 🔒🧑‍🍼 Update own profile                  |
| POST   | `/api/providers/me/certificate`    | 🔒🧑‍🍼 Upload/replace your Qualifikationsnachweis (PDF/JPG/PNG, ≤5MB) |
| GET    | `/api/providers/me/certificate`    | 🔒🧑‍🍼 Download your own uploaded certificate |
| DELETE | `/api/providers/me/certificate`    | 🔒🧑‍🍼 Remove your uploaded certificate     |
| POST   | `/api/auth/register`               | Create a user account (sends verification OTP) |
| POST   | `/api/auth/login`                  | Log in, returns a session token           |
| POST   | `/api/auth/logout`                 | Invalidate a session token                |
| POST   | `/api/auth/verify-email`           | Confirm the email OTP, activates the account |
| POST   | `/api/auth/resend-verification`    | Send a new email-verification OTP         |
| POST   | `/api/auth/forgot-password`        | Send a password-reset OTP                 |
| POST   | `/api/auth/reset-password`         | Consume the OTP and set a new password    |
| POST   | `/api/bookings`                    | 🔒👪 Send a booking request to a provider  |
| GET    | `/api/bookings/mine`                | 🔒👪 Your own booking requests             |
| POST   | `/api/bookings/{id}/cancel`         | 🔒👪 Cancel a pending or already-confirmed booking (emails the provider) |
| GET    | `/api/bookings/provider`            | 🔒🧑‍🍼 Requests received on your own profile |
| POST   | `/api/bookings/{id}/confirm`        | 🔒🧑‍🍼 Confirm a request (emails the parent) |
| POST   | `/api/bookings/{id}/decline`        | 🔒🧑‍🍼 Decline a request                    |
| GET    | `/api/notifications`               | 🔒 Your in-app notifications + unread count |
| POST   | `/api/notifications/{id}/read`     | 🔒 Mark one notification read              |
| POST   | `/api/notifications/read-all`      | 🔒 Mark all notifications read             |
| POST   | `/api/admin/login`                 | Admin login (username/password, returns a session token) |
| POST   | `/api/admin/logout`                | Invalidate an admin session token         |
| GET    | `/api/admin/providers`             | 🔒🛡️ Providers with an uploaded certificate, newest first |
| GET    | `/api/admin/providers/{id}/certificate` | 🔒🛡️ Download a provider's certificate |
| POST   | `/api/admin/providers/{id}/certificate/verify` | 🔒🛡️ Mark the certificate verified (parent-visible tick) |
| POST   | `/api/admin/providers/{id}/certificate/unverify` | 🔒🛡️ Retract a verification |

🔒 = requires `Authorization: Bearer <token>` (from login/verify-email).
👪 = additionally requires `role: "eltern"`.
🧑‍🍼 = additionally requires `role: "tagespflege"`.
🛡️ = admin token only (from `/api/admin/login`) — never interchangeable with a 🔒 user token.

## Project layout

```
kinderkreis-demo/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt  # + pytest/httpx, for running tests/ (never baked into the image)
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py       # FastAPI routes
│   │   ├── models.py     # Pydantic models + regulatory validation rules
│   │   ├── data.py       # Provider seed data (inserted once into SQLite)
│   │   ├── db.py         # SQLite persistence for users/sessions/OTPs/providers/bookings/notifications
│   │   ├── calendar_invite.py  # builds the .ics attached to booking-confirmation emails
│   │   └── data/
│   │       ├── kinderkreis.db  # created on first run, gitignored
│   │       └── certificates/   # uploaded Qualifikationsnachweis files, gitignored
│   └── tests/             # pytest suite — see tests/README.md
│       ├── conftest.py    # fresh SQLite DB + certificate folder per test
│       ├── test_auth.py
│       ├── test_providers.py
│       ├── test_certificates.py
│       ├── test_admin.py
│       ├── test_bookings.py
│       └── test_notifications.py
└── frontend/
    ├── Dockerfile      # multi-stage: build the bundle, then serve it via nginx
    ├── nginx.conf      # static-file serving config for the production image
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── styles.css
        └── components/
            ├── LandingView.jsx        # logged-out front door — placeholder contact details
            ├── ParentsView.jsx        # the directory ("Für Eltern")
            ├── ProfileView.jsx        # "Mein Profil" — own provider listing, create/edit
            ├── ProviderCard.jsx
            ├── ProviderDetailModal.jsx
            ├── BookingRequestForm.jsx    # sends a booking request (in the provider modal)
            ├── MyBookingsView.jsx        # "Meine Anfragen" — Eltern's own requests
            ├── ProviderBookingsView.jsx  # "Buchungsanfragen" — incoming requests, confirm/decline
            ├── NotificationBell.jsx      # nav bell, polls /api/notifications
            ├── LoginView.jsx
            ├── SignupView.jsx
            ├── VerifyEmailView.jsx
            ├── ForgotPasswordView.jsx
            ├── AdminLoginView.jsx        # separate username/password login (footer "Admin" link)
            └── AdminPanelView.jsx        # certificate review queue — view/verify/unverify
```

## Local development without Docker

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

111 tests covering auth, the provider directory + regulatory validation
rules, certificate upload/download/delete, the admin login + certificate
review/verify flow (including the verification email), bookings (including
cancelling a confirmed one and the resulting email), and notifications. Each
test runs against its own throwaway SQLite DB and certificate folder, so the
suite never touches `app/data/kinderkreis.db` — see `backend/tests/README.md`
for the breakdown.

## Deploying to production

`docker-compose.yml` as-is is tuned for local dev (Vite dev server, live
source mounts) — fine on a normal machine, too heavy on a small box (the
Vite dev server alone is a few hundred MB of RAM). For a real deployment,
build the frontend's `production` stage instead of relying on this file:

```bash
docker build --target production \
  --build-arg VITE_API_URL=https://your-real-backend-url \
  -t kinderkreis-frontend ./frontend
```

That serves the static build via `nginx:alpine` — a few MB of RAM instead
of a few hundred — instead of running `npm run dev`. A few things to know:

- **`VITE_API_URL` must be set at build time**, not after — Vite bakes
  every `VITE_*` variable into the compiled JS when it builds, so changing
  it means rebuilding the image, not just restarting the container.
- **Lock down CORS** by setting `ALLOWED_ORIGINS` in `.env` to your real
  frontend origin(s) (comma-separated) — it defaults to allowing any origin,
  which is fine for a demo but not a real deployment.
- **Sizing note**: 1 vCPU / 512MB RAM / 10GB SSD is comfortably enough for
  this app *with* the nginx-served production build above — SQLite stays a
  few MB, and the whole stack idles well under 300MB. It would not be with
  the Vite dev server in the mix, which is why that swap matters more than
  the RAM figure alone suggests.
- **Email**: if your host blocks outbound SMTP (common on free tiers of
  PaaS platforms like Render — see their own changelog on this) or a
  personal Gmail account gets flagged for automated sending, switch
  `_send_email` in `backend/app/main.py` to an HTTPS-API-based provider
  instead of SMTP; the surrounding code (attachments, categories, dev-log
  fallback) doesn't need to change, just the transport.

If you're deploying for real (not just a one-off), it's worth asking for a
small `docker-compose.prod.yml` at that point (production target + backend
without the live-source mount + `mem_limit` guard rails) rather than typing
the `docker build` command above by hand each time.

## Next steps for a real product

- Swap SQLite for Postgres (SQLAlchemy models can mirror `app/models.py`
  closely); SQLite is fine for a demo but not for concurrent production
  writes.
- Add messaging between parents and providers, and let a provider account
  see which parents viewed/contacted them.
- Verify Pflegeerlaubnis claims against Jugendamt records rather than
  trusting the self-reported checkbox on the profile form (the uploaded
  Qualifikationsnachweis itself now goes through an admin verification step
  — see the Admin panel above — but that's a manual review, not an
  automated registry check).
- Give admins actual accounts (name, multiple admins, an audit log of who
  verified what) instead of the single shared username/password login —
  fine for a demo, not for a real moderation team.
- Add photo upload for provider profiles (certificate upload already exists).
