import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, TypedDict

import mailtrap as mt
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from app.data import SEED_PROVIDERS, get_next_id
from app.models import CareType, Provider, ProviderCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kinderkreis")

SESSION_TTL = timedelta(hours=24)
OTP_TTL = timedelta(minutes=10)


class User(TypedDict):
    email: str
    name: str
    hashed_password: str
    role: str
    verified: bool


class OtpRecord(TypedDict):
    otp: str
    expires_at: datetime


app = FastAPI(
    title="Kinderkreis API",
    description="Demo backend for matching families with certified Kindertagespflege providers.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — lock this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_providers: dict[int, Provider] = {p.id: p for p in SEED_PROVIDERS}
_users: dict[str, User] = {}
_sessions: dict[str, dict] = {}          # token -> {email, expires_at}
_otps: dict[str, OtpRecord] = {}         # password-reset OTPs
_verify_otps: dict[str, OtpRecord] = {}  # email-verification OTPs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_email(email: str) -> str:
    return email.lower().strip()


def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.md5(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{digest}"


def _verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split(":", 1)
    actual = hashlib.md5(f"{salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(actual, expected)


def _generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _send_email(to_email: str, subject: str, body: str, category: str = "OTP") -> None:
    api_token = os.environ.get("MAILTRAP_TOKEN")
    if not api_token:
        logger.info("[DEV] Email → %s | %s\n%s", to_email, subject, body)
        return
    try:
        from_email = os.environ.get("FROM_EMAIL", "hello@demomailtrap.co")
        from_name = os.environ.get("FROM_NAME", "Kinderkreis")
        mail = mt.Mail(
            sender=mt.Address(email=from_email, name=from_name),
            to=[mt.Address(email=to_email)],
            subject=subject,
            text=body,
            category=category,
        )
        mt.MailtrapClient(token=api_token).send(mail)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)


def _issue_otp(store: dict, email: str, subject: str, body_template: str, category: str = "OTP") -> None:
    """Generate an OTP, persist it, and email it. body_template may contain {otp}."""
    otp = _generate_otp()
    store[email] = {"otp": otp, "expires_at": datetime.utcnow() + OTP_TTL}
    _send_email(email, subject, body_template.format(otp=otp), category)


def _validate_otp(store: dict, email: str, submitted: str) -> None:
    """Validate and consume an OTP, raising HTTPException on failure."""
    record = store.get(email)
    if not record:
        raise HTTPException(400, "Kein gültiger Code gefunden. Bitte neuen Code anfordern.")
    if datetime.utcnow() > record["expires_at"]:
        store.pop(email, None)
        raise HTTPException(400, "Code abgelaufen. Bitte neuen Code anfordern.")
    if not hmac.compare_digest(record["otp"], submitted):
        raise HTTPException(400, "Ungültiger Code")
    store.pop(email, None)


def _create_session(email: str) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = {"email": email, "expires_at": datetime.utcnow() + SESSION_TTL}
    return token


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
    if email in _users:
        raise HTTPException(409, "E-Mail-Adresse bereits registriert")
    name = payload.name.strip()
    _users[email] = {
        "email": email,
        "name": name,
        "hashed_password": _hash_password(payload.password),
        "role": payload.role,
        "verified": False,
    }
    _issue_otp(
        _verify_otps, email,
        subject="Kinderkreis – Konto bestätigen",
        body_template=f"Hallo {name},\n\nIhr Bestätigungscode lautet: {{otp}}\n\nDer Code ist 10 Minuten gültig.",
        category="Verification",
    )
    return {"needs_verification": True, "email": email}


@app.post("/api/auth/login")
def login_user(payload: UserLogin):
    email = _normalize_email(payload.email)
    user = _users.get(email)
    if not user or not _verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(401, "Ungültige E-Mail-Adresse oder Passwort")
    if not user["verified"]:
        raise HTTPException(403, "E-Mail-Adresse noch nicht bestätigt. Bitte prüfen Sie Ihr Postfach.")
    return {"token": _create_session(email), "name": user["name"], "email": email}


@app.post("/api/auth/logout")
def logout_user(payload: LogoutRequest):
    _sessions.pop(payload.token, None)
    return {"status": "ok"}


@app.post("/api/auth/verify-email")
def verify_email(payload: VerifyEmailRequest):
    email = _normalize_email(payload.email)
    user = _users.get(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if user["verified"]:
        raise HTTPException(400, "Konto bereits bestätigt")
    _validate_otp(_verify_otps, email, payload.otp)
    user["verified"] = True
    return {"token": _create_session(email), "name": user["name"], "email": email}


@app.post("/api/auth/resend-verification")
def resend_verification(payload: ResendVerificationRequest):
    email = _normalize_email(payload.email)
    user = _users.get(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if user["verified"]:
        raise HTTPException(400, "Konto bereits bestätigt")
    _issue_otp(
        _verify_otps, email,
        subject="Kinderkreis – Neuer Bestätigungscode",
        body_template="Ihr neuer Bestätigungscode lautet: {otp}\n\nDer Code ist 10 Minuten gültig.",
        category="Verification",
    )
    return {"detail": "Neuer Code gesendet"}


@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = _normalize_email(payload.email)
    if email not in _users:
        raise HTTPException(404, "Kein Konto mit dieser E-Mail-Adresse gefunden")
    _issue_otp(
        _otps, email,
        subject="Kinderkreis – Ihr Sicherheitscode",
        body_template="Ihr Sicherheitscode lautet: {otp}\n\nDer Code ist 10 Minuten gültig.",
    )
    return {"detail": "OTP gesendet"}


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    email = _normalize_email(payload.email)
    user = _users.get(email)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    _validate_otp(_otps, email, payload.otp)
    user["hashed_password"] = _hash_password(payload.new_password)
    return {"detail": "Passwort erfolgreich zurückgesetzt"}


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------

@app.get("/api/meta/cities")
def list_cities():
    return {"cities": sorted({p.city for p in _providers.values()})}


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
        (p for p in _providers.values() if matches(p)),
        key=lambda p: (-p.free_places, p.name),
    )
    return {"providers": [p.to_public_dict() for p in results], "count": len(results)}


@app.get("/api/providers/{provider_id}")
def get_provider(provider_id: int):
    provider = _providers.get(provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    return provider.to_public_dict()


@app.post("/api/providers", status_code=201)
def register_provider(payload: ProviderCreate):
    try:
        provider = Provider(id=get_next_id(), **payload.model_dump())
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc
    _providers[provider.id] = provider
    return provider.to_public_dict()


@app.patch("/api/providers/{provider_id}/capacity")
def update_capacity(provider_id: int, capacity_used: int = Query(..., ge=0)):
    provider = _providers.get(provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    if capacity_used > provider.capacity_total:
        raise HTTPException(422, "capacity_used cannot exceed capacity_total")
    updated = provider.model_copy(update={"capacity_used": capacity_used})
    _providers[provider_id] = updated
    return updated.to_public_dict()
