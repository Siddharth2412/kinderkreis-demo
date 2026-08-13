
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

# Flat hourly rates for a booking's care window (start_hour..end_hour on
# start_date). Not configurable per provider/booking yet — every booking
# is priced the same way, on both sides of the transaction.
ELTERN_RATE_PER_HOUR = 25.0
TAGESPFLEGER_RATE_PER_HOUR = 18.0


class CareType(str, Enum):
    """Kindertagespflege = one person caring alone in their own home.
    Grossstagespflege = 2-3 qualified providers sharing supervised premises."""
    individual = "individual"
    group = "group"


class ProviderBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    city: str = Field(..., min_length=2, max_length=80)
    min_age_months: int = Field(..., ge=0, le=168, description="Youngest age accepted, in months")
    max_age_months: int = Field(..., ge=0, le=168, description="Oldest age accepted, in months")
    care_type: CareType
    staff_count: int = Field(..., ge=1, le=3)
    capacity_total: int = Field(..., ge=1, le=10)
    capacity_used: int = Field(0, ge=0)
    qualification_hours: int = Field(..., ge=0, description="Completed QHB units (Unterrichtseinheiten)")
    practicum_hours: int = Field(..., ge=0, description="Supervised practicum hours completed")
    has_pflegeerlaubnis: bool = Field(..., description="Valid §43 SGB VIII license from the Jugendamt")
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=30)
    contact_email: Optional[str] = Field(None, max_length=120)
    website: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def check_business_rules(self) -> "ProviderBase":
        if self.max_age_months < self.min_age_months:
            raise ValueError("max_age_months must be greater than or equal to min_age_months")
        if self.capacity_used > self.capacity_total:
            raise ValueError("capacity_used cannot exceed capacity_total")

        # Regulatory caps: solo Kindertagespflege may care for up to 5 children;
        # Grossstagespflege (2-3 providers sharing premises) may care for up to 10.
        if self.care_type == CareType.individual:
            if self.staff_count != 1:
                raise ValueError("Kindertagespflege (individual care) must have exactly 1 provider")
            if self.capacity_total > 5:
                raise ValueError("Individual Kindertagespflege capacity cannot exceed 5 children")
        else:
            if self.staff_count < 2:
                raise ValueError("Grossstagespflege requires at least 2 providers sharing premises")
            if self.capacity_total > 10:
                raise ValueError("Grossstagespflege capacity cannot exceed 10 children")

        return self

    @field_validator("qualification_hours")
    @classmethod
    def sane_hours(cls, v: int) -> int:
        if v > 2000:
            raise ValueError("qualification_hours looks implausible")
        return v


class ProviderCreate(ProviderBase):
    pass


class Provider(ProviderBase):
    id: int
    # Email of the Tagespflegeperson account that owns this listing, if any
    # (seed/legacy profiles have no owner). Never exposed in the public API.
    owner_email: Optional[str] = None
    # Uploaded Qualifikationsnachweis (certificate) metadata. Deliberately not
    # part of ProviderBase/ProviderCreate: it's written only by the dedicated
    # certificate endpoints (POST/DELETE .../me/certificate), never by saving
    # the profile form — see db._migrate_providers_table for why. The raw
    # fields are never exposed publicly, only the has_certificate flag.
    certificate_filename: Optional[str] = None
    certificate_original_name: Optional[str] = None
    certificate_content_type: Optional[str] = None
    certificate_uploaded_at: Optional[str] = None
    # Set only by an admin (POST /api/admin/providers/{id}/certificate/verify),
    # never by the owning account itself. Reset to False by db.py any time the
    # certificate file changes (re-upload or delete) — a verification always
    # refers to one specific file, never "whatever is uploaded at the moment".
    certificate_verified: bool = False
    certificate_verified_at: Optional[str] = None

    @property
    def is_certified(self) -> bool:
        # Minimum QHB requirement before a profile may show as "certified"
        return self.qualification_hours >= 300 and self.practicum_hours >= 80

    @property
    def free_places(self) -> int:
        return self.capacity_total - self.capacity_used

    @property
    def has_certificate(self) -> bool:
        return self.certificate_filename is not None

    def to_public_dict(self) -> dict:
        data = self.model_dump(exclude={
            "owner_email", "certificate_filename", "certificate_original_name",
            "certificate_content_type", "certificate_uploaded_at", "certificate_verified_at",
        })
        data["is_certified"] = self.is_certified
        data["free_places"] = self.free_places
        # Never exposes owner_email itself, but the UI needs to know whether a
        # booking request is even possible (only account-linked profiles have
        # someone able to confirm one).
        data["is_bookable"] = self.owner_email is not None
        # Whether a Qualifikationsnachweis has been uploaded, and whether an
        # admin has reviewed and confirmed it (the "verification tick") — the
        # file itself stays private to the owning account and to admins.
        data["has_certificate"] = self.has_certificate
        data["certificate_verified"] = self.certificate_verified
        return data

    def to_admin_dict(self) -> dict:
        """Everything an admin needs to review a certificate: which account
        owns it, upload metadata, verification status. Deliberately keeps
        owner_email (unlike to_public_dict) but still hides the raw on-disk
        filename/content-type — admins fetch the file itself through the
        dedicated download endpoint, not this listing."""
        data = self.model_dump(exclude={"certificate_filename", "certificate_content_type"})
        data["is_certified"] = self.is_certified
        data["free_places"] = self.free_places
        data["has_certificate"] = self.has_certificate
        return data


class BookingStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    declined = "declined"
    cancelled = "cancelled"


class ChildInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    age_months: Optional[int] = Field(None, ge=0, le=216)


class BookingCreate(BaseModel):
    provider_id: int
    # One request can cover several siblings at once (same provider, same
    # time slot) — at least one child is required.
    children: List[ChildInfo] = Field(..., min_length=1, max_length=10)
    start_date: str = Field(..., description="Requested start date, ISO format YYYY-MM-DD")
    start_hour: int = Field(..., ge=0, le=23, description="Care start time, 0-23")
    end_hour: int = Field(..., ge=0, le=23, description="Care end time, 0-23")
    parent_address: str = Field(..., min_length=3, max_length=200)
    parent_phone: str = Field(..., min_length=5, max_length=30)
    message: Optional[str] = Field(None, max_length=500)

    @field_validator("start_date")
    @classmethod
    def valid_iso_date(cls, v: str) -> str:
        # Format only — Booking subclasses this to redisplay stored rows, whose
        # start_date is often in the past by the time they're read back, so the
        # "not in the past" business rule lives at creation time (see main.py)
        # rather than here.
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("start_date must be an ISO date (YYYY-MM-DD)") from exc
        return v


class Booking(BookingCreate):
    id: int
    parent_email: str
    status: BookingStatus
    created_at: str
    updated_at: str
    # Set only when status == declined (see BookingDeclineRequest) — the
    # Tagespflegeperson's reason, shown back to the Eltern who requested it.
    decline_reason: Optional[str] = None
    # Display-only fields filled in by the API layer depending on who's
    # looking: the parent sees the provider's name/city, the provider sees
    # the parent's name. Never persisted on the row itself.
    provider_name: Optional[str] = None
    provider_city: Optional[str] = None
    parent_name: Optional[str] = None

    @computed_field
    @property
    def duration_hours(self) -> int:
        return max(0, self.end_hour - self.start_hour)

    @computed_field
    @property
    def amount_to_pay(self) -> float:
        """What the Eltern owes for this booking, at a flat €25/hour."""
        return round(self.duration_hours * ELTERN_RATE_PER_HOUR, 2)

    @computed_field
    @property
    def amount_to_receive(self) -> float:
        """What the Tagespflegeperson is paid for this booking, at a flat €18/hour."""
        return round(self.duration_hours * TAGESPFLEGER_RATE_PER_HOUR, 2)


class BookingDeclineRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
