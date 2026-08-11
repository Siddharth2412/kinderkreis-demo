
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @property
    def is_certified(self) -> bool:
        # Minimum QHB requirement before a profile may show as "certified"
        return self.qualification_hours >= 300 and self.practicum_hours >= 80

    @property
    def free_places(self) -> int:
        return self.capacity_total - self.capacity_used

    def to_public_dict(self) -> dict:
        data = self.model_dump(exclude={"owner_email"})
        data["is_certified"] = self.is_certified
        data["free_places"] = self.free_places
        # Never exposes owner_email itself, but the UI needs to know whether a
        # booking request is even possible (only account-linked profiles have
        # someone able to confirm one).
        data["is_bookable"] = self.owner_email is not None
        return data


class BookingStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    declined = "declined"
    cancelled = "cancelled"


class BookingCreate(BaseModel):
    provider_id: int
    child_name: str = Field(..., min_length=1, max_length=80)
    child_age_months: Optional[int] = Field(None, ge=0, le=216)
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
    # Display-only fields filled in by the API layer depending on who's
    # looking: the parent sees the provider's name/city, the provider sees
    # the parent's name. Never persisted on the row itself.
    provider_name: Optional[str] = None
    provider_city: Optional[str] = None
    parent_name: Optional[str] = None
