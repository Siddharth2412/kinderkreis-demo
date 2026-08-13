"""Minimal RFC 5545 (iCalendar) builder for booking-confirmation emails.

No external dependency — a confirmed booking only needs a single timed
VEVENT, so a small hand-rolled builder is simpler than pulling in a full
`icalendar` package for this demo.
"""

from __future__ import annotations

from datetime import date, datetime, time


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_booking_ics(booking: dict, provider_row: dict) -> bytes:
    """A VEVENT spanning the booking's start_hour–end_hour on start_date,
    attached to both the parent's and the provider's confirmation emails so
    either can drop it straight into their calendar. Times are written as
    "floating" local time (no TZID/UTC offset) — reasonable for a demo with
    no per-account timezone setting; calendar apps show them as-is."""
    day = date.fromisoformat(booking["start_date"])
    start_dt = datetime.combine(day, time(hour=booking["start_hour"]))
    end_dt = datetime.combine(day, time(hour=booking["end_hour"]))
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = f"kinderkreis-booking-{booking['id']}@kinderkreis.demo"
    children_label = ", ".join(c["name"] for c in booking["children"])
    summary = f"Betreuung: {children_label} bei {provider_row['name']}"

    description_lines = [
        f"Kind: {c['name']}" + (f" ({c['age_months']} Monate)" if c.get("age_months") is not None else "")
        for c in booking["children"]
    ] + [
        f"Betreuungsperson: {provider_row['name']}",
        f"Adresse der Eltern: {booking['parent_address']}",
        f"Telefon der Eltern: {booking['parent_phone']}",
    ]
    if booking.get("message"):
        description_lines.append(f"Nachricht: {booking['message']}")
    description = "\\n".join(_ics_escape(line) for line in description_lines)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kinderkreis//Booking Demo//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{_ics_escape(provider_row['city'])}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
