import hashlib
import hmac
import html
import logging
import os
import secrets
import smtplib
import sqlite3
import ssl
from datetime import date, datetime, time, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from app import db
from app.calendar_invite import build_booking_ics
from app.data import SEED_PROVIDERS
from app.models import Booking, BookingCreate, CareType, Provider, ProviderCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kinderkreis")

SESSION_TTL = timedelta(hours=24)
OTP_TTL = timedelta(minutes=10)
ADMIN_SESSION_TTL = timedelta(hours=12)

app = FastAPI(
    title="Kinderkreis API",
    description="Demo backend for matching families with certified Kindertagespflege providers.",
    version="0.1.0",
)

# Comma-separated in ALLOWED_ORIGINS (e.g. "https://kinderkreis-demo.onrender.com")
# to lock this down for a real deployment; defaults to wide open so the demo
# keeps working with zero config. Auth here is a Bearer token the frontend
# sets explicitly, never a cookie, so the browser never treats these as
# "credentialed" requests — allow_credentials + a wildcard origin is safe in
# this specific case (it would not be if anything relied on cookies).
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
allowed_origins = (
    [origin.strip() for origin in _allowed_origins_env.split(",") if origin.strip()]
    if _allowed_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()
db.seed_providers_if_empty([p.model_dump() for p in SEED_PROVIDERS])  # only runs on a fresh DB
db.CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)

# Qualifikationsnachweis (certificate) upload limits: content-type sniffed
# from the browser's Content-Type header (not re-derived from file bytes —
# fine for this demo, an authenticated user attacking their own upload isn't
# a threat model here) maps to a fixed on-disk extension, and a size cap
# keeps someone from parking a huge file on the server's disk.
CERTIFICATE_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
CERTIFICATE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _load_providers() -> dict[int, Provider]:
    return {row["id"]: Provider(**row) for row in db.list_providers()}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_email(email: str) -> str:
    return email.lower().strip()


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, expected_hex = stored.split(":", 1)
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(actual.hex(), expected_hex)


# The admin account is entirely separate from `users` — username/password
# only, no email/OTP/role — so it's provisioned via env vars rather than a
# public signup form (there must be no self-service way to become an admin).
# Like the provider seed near the top of this file, this only takes effect on
# a fresh database; changing ADMIN_USERNAME/ADMIN_PASSWORD later has no
# effect on an existing one (there's deliberately no "change admin password"
# endpoint either — swap the env vars and reset the DB if that's ever needed).
db.seed_admin_if_empty(
    os.environ.get("ADMIN_USERNAME", "admin"),
    _hash_password(os.environ.get("ADMIN_PASSWORD", "admin123")),
)


def _generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _text_to_html(text: str) -> str:
    """Every call site here composes plain text; escape it and turn newlines
    into <br> so the email still reads as one paragraph per line."""
    return html.escape(text).replace("\n", "<br>\n")


def _send_email(
    to_email: str,
    subject: str,
    body: str,
    category: str = "OTP",
    attachments: Optional[list[dict]] = None,
) -> None:
    """attachments is an optional list of {"content": bytes, "filename": str,
    "mimetype": str} dicts (used for the .ics calendar invite on booking
    confirmation). Sent over plain SMTP (stdlib smtplib, no SDK) — provider-
    agnostic via SMTP_HOST/PORT/USERNAME/PASSWORD, currently pointed at
    Gmail (smtp.gmail.com:587 with an App Password; Gmail requires FROM_EMAIL
    to match the authenticated account). `category` has no SMTP equivalent
    and is only used for the local dev log line below."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        names = ", ".join(a["filename"] for a in attachments) if attachments else ""
        suffix = f" (+ attachment: {names})" if names else ""
        logger.info("[DEV] Email → %s | %s%s [%s]\n%s", to_email, subject, suffix, category, body)
        return

    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("FROM_EMAIL", username or "hello@kinderkreis.demo")
    from_name = os.environ.get("FROM_NAME", "Kinderkreis")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(_text_to_html(body), "html"))

    for a in attachments or []:
        maintype, _, subtype = a.get("mimetype", "application/octet-stream").partition("/")
        part = MIMEBase(maintype or "application", subtype or "octet-stream")
        part.set_payload(a["content"])
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=a["filename"])
        msg.attach(part)

    try:
        if port == 465:  # implicit TLS ("SMTPS"); everything else negotiates STARTTLS
            with smtplib.SMTP_SSL(host, port, timeout=10, context=ssl.create_default_context()) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                if username:
                    server.login(username, password)
                server.send_message(msg)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to_email)


def _issue_otp(purpose: str, email: str, subject: str, body_template: str, category: str = "OTP") -> None:
    """Generate an OTP, persist it, and email it. body_template may contain {otp}."""
    otp = _generate_otp()
    expires_at = (datetime.utcnow() + OTP_TTL).isoformat()
    db.set_otp(purpose, email, otp, expires_at)
    _send_email(email, subject, body_template.format(otp=otp), category)


def _validate_otp(purpose: str, email: str, submitted: str) -> None:
    """Validate and consume an OTP, raising HTTPException on failure."""
    record = db.get_otp(purpose, email)
    if not record:
        raise HTTPException(400, "Kein gültiger Code gefunden. Bitte neuen Code anfordern.")
    if datetime.utcnow() > datetime.fromisoformat(record["expires_at"]):
        db.delete_otp(purpose, email)
        raise HTTPException(400, "Code abgelaufen. Bitte neuen Code anfordern.")
    if not hmac.compare_digest(record["otp"], submitted):
        raise HTTPException(400, "Ungültiger Code")
    db.delete_otp(purpose, email)


def _create_session(email: str) -> str:
    token = secrets.token_hex(32)
    expires_at = (datetime.utcnow() + SESSION_TTL).isoformat()
    db.create_session(token, email, expires_at)
    return token


def _current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Resolve the logged-in user from an `Authorization: Bearer <token>` header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Nicht angemeldet")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.get_session(token)
    if not session or datetime.utcnow() > datetime.fromisoformat(session["expires_at"]):
        if session:
            db.delete_session(token)
        raise HTTPException(401, "Sitzung ungültig oder abgelaufen. Bitte erneut anmelden.")
    user = db.get_user(session["email"])
    if not user:
        raise HTTPException(401, "Benutzer nicht gefunden")
    return user


def _require_tagespflege(user: dict) -> None:
    if user["role"] != "tagespflege":
        raise HTTPException(403, "Nur für Tagespflegepersonen")


def _require_eltern(user: dict) -> None:
    if user["role"] != "eltern":
        raise HTTPException(403, "Nur für Eltern")


def _create_admin_session(username: str) -> str:
    token = secrets.token_hex(32)
    expires_at = (datetime.utcnow() + ADMIN_SESSION_TTL).isoformat()
    db.create_admin_session(token, username, expires_at)
    return token


def _current_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Resolve the logged-in admin from an `Authorization: Bearer <token>`
    header — mirrors _current_user, but against admin_sessions/admins, a
    completely separate table pair from the eltern/tagespflege ones. An
    admin token is never valid on a /api/... user endpoint and vice versa,
    since each dependency only ever looks in its own session table."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Nicht angemeldet")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.get_admin_session(token)
    if not session or datetime.utcnow() > datetime.fromisoformat(session["expires_at"]):
        if session:
            db.delete_admin_session(token)
        raise HTTPException(401, "Sitzung ungültig oder abgelaufen. Bitte erneut anmelden.")
    admin = db.get_admin(session["username"])
    if not admin:
        raise HTTPException(401, "Admin nicht gefunden")
    return admin


def _notify(recipient_email: str, type_: str, booking_id: Optional[int], title: str, body: str) -> None:
    """Insert an in-app notification for a user. No email is sent here — email
    is reserved for the one moment the spec calls for it (booking confirmed),
    handled separately by the caller via _send_email."""
    db.insert_notification({
        "recipient_email": recipient_email,
        "type": type_,
        "booking_id": booking_id,
        "title": title,
        "body": body,
        "created_at": datetime.utcnow().isoformat(),
    })


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("eltern", pattern="^(eltern|tagespflege)$")


class UserLogin(BaseModel):
    email: str
    password: str


class LogoutRequest(BaseModel):
    token: str


class AdminLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class AdminLogoutRequest(BaseModel):
    token: str


class VerifyEmailRequest(BaseModel):
    email: str
    otp: str


class ResendVerificationRequest(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register_user(payload: UserRegister):
    email = _normalize_email(payload.email)
    if db.get_user(email):
        raise HTTPException(409, "E-Mail-Adresse bereits registriert")
    name = payload.name.strip()
    db.create_user(email, name, _hash_password(payload.password), payload.role)
    _issue_otp(
        "verify", email,
        subject="Kinderkreis – Konto bestätigen",
        body_template=f"Hallo {name},\n\nIhr Bestätigungscode lautet: {{otp}}\n\nDer Code ist 10 Minuten gültig.",
        category="Verification",
    )
    return {"needs_verification": True, "email": email}


@app.post("/api/auth/login")
def login_user(payload: UserLogin):
    email = _normalize_email(payload.email)
    user = db.get_user(email)
    if not user or not _verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(401, "Ungültige E-Mail-Adresse oder Passwort")
    if not user["verified"]:
        # Correct password, just never confirmed the account — send a fresh
        # code and route the client into the verification flow instead of a
        # dead-end error.
        _issue_otp(
            "verify", email,
            subject="Kinderkreis – Neuer Bestätigungscode",
            body_template="Ihr Bestätigungscode lautet: {otp}\n\nDer Code ist 10 Minuten gültig.",
            category="Verification",
        )
        return {"needs_verification": True, "email": email}
    return {"token": _create_session(email), "name": user["name"], "email": email, "role": user["role"]}


@app.post("/api/auth/logout")
def logout_user(payload: LogoutRequest):
    db.delete_session(payload.token)
    return {"status": "ok"}


@app.post("/api/auth/verify-email")
def verify_email(payload: VerifyEmailRequest):
    email = _normalize_email(payload.email)
    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if user["verified"]:
        raise HTTPException(400, "Konto bereits bestätigt")
    _validate_otp("verify", email, payload.otp)
    db.set_user_verified(email)
    return {"token": _create_session(email), "name": user["name"], "email": email, "role": user["role"]}


@app.post("/api/auth/resend-verification")
def resend_verification(payload: ResendVerificationRequest):
    email = _normalize_email(payload.email)
    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if user["verified"]:
        raise HTTPException(400, "Konto bereits bestätigt")
    _issue_otp(
        "verify", email,
        subject="Kinderkreis – Neuer Bestätigungscode",
        body_template="Ihr neuer Bestätigungscode lautet: {otp}\n\nDer Code ist 10 Minuten gültig.",
        category="Verification",
    )
    return {"detail": "Neuer Code gesendet"}


@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = _normalize_email(payload.email)
    if not db.get_user(email):
        raise HTTPException(404, "Kein Konto mit dieser E-Mail-Adresse gefunden")
    _issue_otp(
        "reset", email,
        subject="Kinderkreis – Ihr Sicherheitscode",
        body_template="Ihr Sicherheitscode lautet: {otp}\n\nDer Code ist 10 Minuten gültig.",
    )
    return {"detail": "OTP gesendet"}


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    email = _normalize_email(payload.email)
    user = db.get_user(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    _validate_otp("reset", email, payload.otp)
    db.set_user_password(email, _hash_password(payload.new_password))
    return {"detail": "Passwort erfolgreich zurückgesetzt"}


# ---------------------------------------------------------------------------
# Admin endpoints
#
# Username/password only — a completely separate login from the eltern/
# tagespflege accounts above (own tables, own session type, no email/OTP/
# role). The account itself is provisioned via ADMIN_USERNAME/ADMIN_PASSWORD
# at startup (see db.seed_admin_if_empty above); there is deliberately no
# admin signup endpoint. An admin reviews uploaded Qualifikationsnachweis
# files and marks them verified — the only way a provider gets the "✓
# geprüft" tick parents see on the public directory.
# ---------------------------------------------------------------------------

@app.post("/api/admin/login")
def admin_login(payload: AdminLogin):
    admin = db.get_admin(payload.username.strip())
    if not admin or not _verify_password(payload.password, admin["hashed_password"]):
        raise HTTPException(401, "Ungültiger Benutzername oder Passwort")
    return {"token": _create_admin_session(admin["username"]), "username": admin["username"]}


@app.post("/api/admin/logout")
def admin_logout(payload: AdminLogoutRequest):
    db.delete_admin_session(payload.token)
    return {"status": "ok"}


@app.get("/api/admin/providers")
def admin_list_providers(admin: dict = Depends(_current_admin)):
    """The review queue: only providers with a certificate on file — nothing
    to verify for the rest — newest upload first so freshly submitted ones
    surface at the top."""
    with_certificate = [Provider(**row) for row in db.list_providers() if row.get("certificate_filename")]
    with_certificate.sort(key=lambda p: p.certificate_uploaded_at or "", reverse=True)
    return {"providers": [p.to_admin_dict() for p in with_certificate]}


@app.get("/api/admin/providers/{provider_id}/certificate")
def admin_download_certificate(provider_id: int, admin: dict = Depends(_current_admin)):
    row = db.get_provider(provider_id)
    filename = row.get("certificate_filename") if row else None
    if not filename:
        raise HTTPException(404, "Kein Zertifikat hinterlegt")
    path = db.CERTIFICATES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Zertifikatsdatei nicht gefunden")
    return FileResponse(
        path,
        media_type=row["certificate_content_type"] or "application/octet-stream",
        filename=row["certificate_original_name"] or filename,
    )


@app.post("/api/admin/providers/{provider_id}/certificate/verify")
def admin_verify_certificate(
    provider_id: int, background_tasks: BackgroundTasks, admin: dict = Depends(_current_admin)
):
    row = db.get_provider(provider_id)
    if not row or not row.get("certificate_filename"):
        raise HTTPException(404, "Kein Zertifikat hinterlegt")
    db.set_certificate_verified(provider_id, True, datetime.utcnow().isoformat())
    if row.get("owner_email"):
        _notify(
            row["owner_email"], "certificate_verified", None,
            title="Zertifikat geprüft",
            body="Ihr hochgeladenes Zertifikat wurde von einem Admin geprüft und bestätigt.",
        )
        # Email, not just the in-app notification — a Tagespflegeperson may
        # not be logged in when this happens, and this is a one-time,
        # meaningful status change worth an email (same reasoning as the
        # booking-confirmed email below). Backgrounded so the admin's
        # request doesn't wait on the SMTP round-trip.
        owner = db.get_user(row["owner_email"])
        owner_name = owner["name"] if owner else row["owner_email"]
        background_tasks.add_task(
            _send_email,
            row["owner_email"],
            subject="Kinderkreis – Ihr Zertifikat wurde geprüft und bestätigt",
            body=(
                f"Hallo {owner_name},\n\n"
                f"Ihr hochgeladenes Zertifikat für „{row['name']}\" wurde von einem Admin geprüft und "
                "bestätigt. Ihr Profil zeigt Eltern ab sofort das Prüf-Häkchen „✓ Geprüft\".\n\n"
                "Vielen Dank, dass Sie Ihre Qualifikation nachgewiesen haben."
            ),
            category="Certificate",
        )
    return Provider(**db.get_provider(provider_id)).to_admin_dict()


@app.post("/api/admin/providers/{provider_id}/certificate/unverify")
def admin_unverify_certificate(provider_id: int, admin: dict = Depends(_current_admin)):
    row = db.get_provider(provider_id)
    if not row:
        raise HTTPException(404, "Provider nicht gefunden")
    db.set_certificate_verified(provider_id, False, None)
    return Provider(**db.get_provider(provider_id)).to_admin_dict()


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------

@app.get("/api/meta/cities")
def list_cities():
    return {"cities": db.list_cities()}


@app.get("/api/providers")
def list_providers(
    city: Optional[str] = None,
    care_type: Optional[CareType] = None,
    age_months: Optional[int] = Query(None, ge=0, le=168),
    available_only: bool = False,
    certified_only: bool = False,
):
    city_lower = city.lower() if city else None

    def matches(p: Provider) -> bool:
        if city_lower and p.city.lower() != city_lower:
            return False
        if care_type and p.care_type != care_type:
            return False
        if age_months is not None and not (p.min_age_months <= age_months <= p.max_age_months):
            return False
        if available_only and p.free_places == 0:
            return False
        if certified_only and not p.is_certified:
            return False
        return True

    results = sorted(
        (p for p in _load_providers().values() if matches(p)),
        key=lambda p: (-p.free_places, p.name),
    )
    return {"providers": [p.to_public_dict() for p in results], "count": len(results)}


@app.get("/api/providers/me")
def get_my_provider(user: dict = Depends(_current_user)):
    """The Tagespflegeperson's own profile, mapped by their account email. Not part
    of the public listing endpoints — only reachable when logged in."""
    _require_tagespflege(user)
    row = db.get_provider_by_owner(user["email"])
    return {"provider": Provider(**row).to_public_dict() if row else None}


@app.post("/api/providers/me", status_code=201)
def create_my_provider(payload: ProviderCreate, user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    if db.get_provider_by_owner(user["email"]):
        raise HTTPException(409, "Es existiert bereits ein Profil für dieses Konto")
    try:
        validated = Provider(id=0, owner_email=user["email"], **payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc
    try:
        new_id = db.insert_provider(validated.model_dump(exclude={"id"}))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Es existiert bereits ein Profil für dieses Konto") from exc
    provider = validated.model_copy(update={"id": new_id})
    return provider.to_public_dict()


@app.put("/api/providers/me")
def update_my_provider(payload: ProviderCreate, user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    existing = db.get_provider_by_owner(user["email"])
    if not existing:
        raise HTTPException(404, "Kein Profil gefunden. Bitte zuerst ein Profil anlegen.")
    try:
        validated = Provider(id=existing["id"], owner_email=user["email"], **payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc
    db.update_provider(existing["id"], validated.model_dump(exclude={"id", "owner_email"}))
    return validated.to_public_dict()


@app.get("/api/providers/{provider_id}")
def get_provider(provider_id: int):
    row = db.get_provider(provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    return Provider(**row).to_public_dict()


@app.patch("/api/providers/{provider_id}/capacity")
def update_capacity(provider_id: int, capacity_used: int = Query(..., ge=0)):
    row = db.get_provider(provider_id)
    if not row:
        raise HTTPException(404, "Provider not found")
    provider = Provider(**row)
    if capacity_used > provider.capacity_total:
        raise HTTPException(422, "capacity_used cannot exceed capacity_total")
    db.update_provider_capacity(provider_id, capacity_used)
    updated = provider.model_copy(update={"capacity_used": capacity_used})
    return updated.to_public_dict()


# ---------------------------------------------------------------------------
# Certificate (Qualifikationsnachweis) upload
#
# One file per provider profile, always stored as "<provider_id><ext>" so a
# re-upload naturally replaces the previous one. Only the owning
# Tagespflegeperson can upload, view, or delete it — the public directory
# only ever sees the has_certificate flag (see Provider.to_public_dict).
# ---------------------------------------------------------------------------

@app.post("/api/providers/me/certificate")
async def upload_my_certificate(file: UploadFile = File(...), user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    provider_row = db.get_provider_by_owner(user["email"])
    if not provider_row:
        raise HTTPException(404, "Bitte legen Sie zuerst Ihr Profil an, bevor Sie ein Zertifikat hochladen.")

    ext = CERTIFICATE_CONTENT_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(415, "Nur PDF-, JPG- oder PNG-Dateien werden akzeptiert.")

    content = await file.read()
    if not content:
        raise HTTPException(422, "Die Datei ist leer.")
    if len(content) > CERTIFICATE_MAX_BYTES:
        raise HTTPException(413, "Die Datei ist zu groß (maximal 5 MB).")

    provider_id = provider_row["id"]
    # Drop any previous file first — if the extension changed (e.g. a PDF
    # re-uploaded as a JPG) the new filename below wouldn't otherwise
    # overwrite it, leaving an orphaned file behind.
    old_filename = provider_row.get("certificate_filename")
    if old_filename:
        (db.CERTIFICATES_DIR / old_filename).unlink(missing_ok=True)

    filename = f"{provider_id}{ext}"
    (db.CERTIFICATES_DIR / filename).write_bytes(content)
    db.set_provider_certificate(
        provider_id, filename, file.filename or filename, file.content_type, datetime.utcnow().isoformat()
    )
    return Provider(**db.get_provider(provider_id)).to_public_dict()


@app.get("/api/providers/me/certificate")
def download_my_certificate(user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    provider_row = db.get_provider_by_owner(user["email"])
    filename = provider_row.get("certificate_filename") if provider_row else None
    if not filename:
        raise HTTPException(404, "Kein Zertifikat hinterlegt")
    path = db.CERTIFICATES_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Zertifikatsdatei nicht gefunden")
    return FileResponse(
        path,
        media_type=provider_row["certificate_content_type"] or "application/octet-stream",
        filename=provider_row["certificate_original_name"] or filename,
    )


@app.delete("/api/providers/me/certificate")
def delete_my_certificate(user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    provider_row = db.get_provider_by_owner(user["email"])
    if not provider_row:
        raise HTTPException(404, "Kein Profil gefunden")
    filename = provider_row.get("certificate_filename")
    if filename:
        (db.CERTIFICATES_DIR / filename).unlink(missing_ok=True)
        db.clear_provider_certificate(provider_row["id"])
    return Provider(**db.get_provider(provider_row["id"])).to_public_dict()


# ---------------------------------------------------------------------------
# Booking endpoints
#
# Eltern send a booking request to a specific, account-linked provider; the
# owning Tagespflegeperson confirms or declines it. Only providers created by
# a logged-in tagespflege account (owner_email set) can receive bookings —
# nobody is signed in to act on a request against an unclaimed seed profile.
# ---------------------------------------------------------------------------

def _booking_for_parent(row: dict, provider_row: Optional[dict]) -> dict:
    booking = Booking(**row, provider_name=provider_row["name"] if provider_row else None,
                       provider_city=provider_row["city"] if provider_row else None)
    return booking.model_dump()


def _booking_for_provider(row: dict, parent_name: Optional[str]) -> dict:
    booking = Booking(**row, parent_name=parent_name)
    return booking.model_dump()


@app.post("/api/bookings", status_code=201)
def create_booking(payload: BookingCreate, user: dict = Depends(_current_user)):
    _require_eltern(user)
    provider_row = db.get_provider(payload.provider_id)
    if not provider_row:
        raise HTTPException(404, "Betreuungsperson nicht gefunden")
    if not provider_row["owner_email"]:
        raise HTTPException(
            409, "Dieser Anbieter hat noch kein verknüpftes Konto — Buchungsanfragen sind derzeit nicht möglich."
        )
    if payload.end_hour <= payload.start_hour:
        raise HTTPException(422, "Die Endzeit muss nach der Startzeit liegen.")
    requested_start = datetime.combine(date.fromisoformat(payload.start_date), time(hour=payload.start_hour))
    if requested_start <= datetime.now():
        raise HTTPException(422, "Der gewünschte Termin muss in der Zukunft liegen.")
    now = datetime.utcnow().isoformat()
    data = payload.model_dump()
    data.update(parent_email=user["email"], status="pending", created_at=now, updated_at=now)
    booking_id = db.insert_booking(data)
    _notify(
        provider_row["owner_email"], "booking_requested", booking_id,
        title="Neue Buchungsanfrage",
        body=(
            f"{user['name']} möchte {payload.child_name} am {payload.start_date} von "
            f"{payload.start_hour:02d}:00 bis {payload.end_hour:02d}:00 Uhr bei Ihnen anmelden."
        ),
    )
    return _booking_for_parent(db.get_booking(booking_id), provider_row)


@app.get("/api/bookings/mine")
def list_my_bookings(user: dict = Depends(_current_user)):
    _require_eltern(user)
    bookings = []
    for row in db.list_bookings_by_parent(user["email"]):
        provider_row = db.get_provider(row["provider_id"])
        bookings.append(_booking_for_parent(row, provider_row))
    return {"bookings": bookings}


@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, background_tasks: BackgroundTasks, user: dict = Depends(_current_user)):
    _require_eltern(user)
    row = db.get_booking(booking_id)
    if not row or row["parent_email"] != user["email"]:
        raise HTTPException(404, "Buchungsanfrage nicht gefunden")
    # Eltern can cancel a still-open request or back out of an already
    # confirmed booking (plans change) — just not one that's already been
    # declined or cancelled.
    if row["status"] not in ("pending", "confirmed"):
        raise HTTPException(409, "Diese Buchung kann nicht mehr storniert werden")
    was_confirmed = row["status"] == "confirmed"
    db.update_booking_status(booking_id, "cancelled", datetime.utcnow().isoformat())
    provider_row = db.get_provider(row["provider_id"])

    # The provider always has an account by this point — booking creation
    # requires provider_row["owner_email"] to be set — but guard anyway
    # rather than assume it.
    if provider_row and provider_row.get("owner_email"):
        _notify(
            provider_row["owner_email"], "booking_cancelled", booking_id,
            title="Buchung storniert",
            body=f"{user['name']} hat die Buchung für {row['child_name']} am {row['start_date']} storniert.",
        )
        # Email too, not just the in-app notification — the provider may
        # have already blocked out the time (especially for a confirmed
        # booking) and may not be logged in when this happens.
        time_range = f"{row['start_hour']:02d}:00–{row['end_hour']:02d}:00 Uhr"
        background_tasks.add_task(
            _send_email,
            provider_row["owner_email"],
            subject=f"Kinderkreis – Buchung storniert: {row['child_name']} am {row['start_date']}",
            body=(
                f"{user['name']} hat die "
                + ("bereits bestätigte " if was_confirmed else "")
                + f"Buchung für {row['child_name']} am {row['start_date']} ({time_range}) storniert.\n\n"
                f"Adresse: {row['parent_address']}\nTelefon: {row['parent_phone']}\n\n"
                + ("Falls Sie den Platz für dieses Kind bereits eingeplant hatten, ist er jetzt wieder frei."
                   if was_confirmed else "")
            ),
            category="Booking",
        )

    return _booking_for_parent(db.get_booking(booking_id), provider_row)


@app.get("/api/bookings/provider")
def list_provider_bookings(user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    provider_row = db.get_provider_by_owner(user["email"])
    if not provider_row:
        return {"bookings": [], "has_profile": False}
    bookings = []
    for row in db.list_bookings_by_provider(provider_row["id"]):
        parent = db.get_user(row["parent_email"])
        bookings.append(_booking_for_provider(row, parent["name"] if parent else None))
    return {"bookings": bookings, "has_profile": True}


def _resolve_own_booking(booking_id: int, user: dict) -> tuple[dict, dict]:
    """Load a booking + its provider, raising if the current tagespflege user
    doesn't own that provider or the booking is no longer pending."""
    row = db.get_booking(booking_id)
    if not row:
        raise HTTPException(404, "Buchungsanfrage nicht gefunden")
    provider_row = db.get_provider(row["provider_id"])
    if not provider_row or provider_row["owner_email"] != user["email"]:
        raise HTTPException(403, "Nicht Ihre Buchungsanfrage")
    if row["status"] != "pending":
        raise HTTPException(409, "Diese Anfrage wurde bereits bearbeitet")
    return row, provider_row


def _send_confirmation_emails(row: dict, provider_row: dict, confirmed: dict, provider_email: str) -> None:
    """Both sides get a confirmation email with the same calendar invite for
    the agreed start date, so either can drop it straight into their
    calendar (no separate calendar-account integration in this demo). Runs
    as a background task so the two blocking SMTP round-trips don't add to
    the confirm request's response time."""
    ics_attachment = [{
        "content": build_booking_ics(confirmed, provider_row),
        "filename": "buchung.ics",
        "mimetype": "text/calendar",
    }]

    # Subjects include the child's name/date (not just the booking id) so
    # repeated confirmations for the same parent/provider don't collapse
    # into a single thread in Gmail and similar clients.
    time_range = f"{row['start_hour']:02d}:00–{row['end_hour']:02d}:00 Uhr"
    _send_email(
        row["parent_email"],
        subject=f"Kinderkreis – Buchung bestätigt: {row['child_name']} am {row['start_date']}",
        body=(
            f"Gute Nachrichten!\n\n{provider_row['name']} in {provider_row['city']} hat Ihre Buchungsanfrage "
            f"für {row['child_name']} am {row['start_date']} ({time_range}) bestätigt.\n\n"
            "Im Anhang finden Sie einen Kalendereintrag für den Betreuungsstart.\n\n"
            + (f"Nachricht von {provider_row['name']}: {row['message']}\n\n" if row.get("message") else "")
            + "Bei Fragen wenden Sie sich direkt an die Betreuungsperson."
        ),
        category="Booking",
        attachments=ics_attachment,
    )

    parent = db.get_user(row["parent_email"])
    parent_label = f"{parent['name']} ({row['parent_email']})" if parent else row["parent_email"]
    _send_email(
        provider_email,
        subject=f"Kinderkreis – Bestätigung gespeichert: {row['child_name']} am {row['start_date']}",
        body=(
            f"Sie haben die Buchungsanfrage bestätigt.\n\n"
            f"Kind: {row['child_name']}\nZeitraum: {row['start_date']}, {time_range}\n"
            f"Eltern: {parent_label}\nAdresse: {row['parent_address']}\nTelefon: {row['parent_phone']}\n\n"
            + (f"Nachricht der Eltern: {row['message']}\n\n" if row.get("message") else "")
            + "Im Anhang finden Sie einen Kalendereintrag für den Betreuungsstart."
        ),
        category="Booking",
        attachments=ics_attachment,
    )


@app.post("/api/bookings/{booking_id}/confirm")
def confirm_booking(booking_id: int, background_tasks: BackgroundTasks, user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    row, provider_row = _resolve_own_booking(booking_id, user)
    db.update_booking_status(booking_id, "confirmed", datetime.utcnow().isoformat())
    confirmed = db.get_booking(booking_id)
    _notify(
        row["parent_email"], "booking_confirmed", booking_id,
        title="Buchung bestätigt",
        body=f"{provider_row['name']} hat Ihre Anfrage für {row['child_name']} bestätigt.",
    )
    # the tagespflege account that just confirmed — same as provider_row["owner_email"]
    background_tasks.add_task(_send_confirmation_emails, row, provider_row, confirmed, user["email"])
    return _booking_for_parent(confirmed, provider_row)


@app.post("/api/bookings/{booking_id}/decline")
def decline_booking(booking_id: int, user: dict = Depends(_current_user)):
    _require_tagespflege(user)
    row, provider_row = _resolve_own_booking(booking_id, user)
    db.update_booking_status(booking_id, "declined", datetime.utcnow().isoformat())
    _notify(
        row["parent_email"], "booking_declined", booking_id,
        title="Buchung abgelehnt",
        body=f"{provider_row['name']} hat Ihre Anfrage für {row['child_name']} leider abgelehnt.",
    )
    return _booking_for_parent(db.get_booking(booking_id), provider_row)


# ---------------------------------------------------------------------------
# Notification endpoints (in-app only; available to any logged-in user)
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
def list_notifications(user: dict = Depends(_current_user)):
    return {
        "notifications": db.list_notifications(user["email"]),
        "unread_count": db.count_unread_notifications(user["email"]),
    }


@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, user: dict = Depends(_current_user)):
    db.mark_notification_read(notification_id, user["email"])
    return {"status": "ok"}


@app.post("/api/notifications/read-all")
def read_all_notifications(user: dict = Depends(_current_user)):
    db.mark_all_notifications_read(user["email"])
    return {"status": "ok"}
