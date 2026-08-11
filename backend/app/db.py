"""SQLite persistence for users, sessions, and OTPs.

Replaces the plain in-memory dicts that used to live in main.py. Uses the
stdlib sqlite3 module directly (no ORM) to keep things simple for a demo —
a fresh connection is opened per call, which is fine for SQLite's usage
pattern here.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, TypedDict

# Lives inside app/data/, which is bind-mounted by docker-compose (the whole
# app/ dir is mounted), so the file survives container restarts. Override
# with KINDERKREIS_DB_PATH for deployments (e.g. Render persistent disks).
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "kinderkreis.db"
DB_PATH = Path(os.environ.get("KINDERKREIS_DB_PATH", DEFAULT_DB_PATH))


class UserRow(TypedDict):
    email: str
    name: str
    hashed_password: str
    role: str
    verified: bool


class OtpRow(TypedDict):
    otp: str
    expires_at: str


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_bookings_table(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the `bookings` table already existed on
    someone's machine. `CREATE TABLE IF NOT EXISTS` above is a no-op once the
    table exists, so new columns need an explicit ALTER TABLE — this keeps
    existing rows (and the SQLite file itself) intact rather than requiring
    a fresh database. New columns are nullable; older rows just read back
    with NULL/blank values for them."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(bookings)")}
    new_columns = {
        "parent_address": "TEXT",
        "parent_phone": "TEXT",
        "start_hour": "INTEGER",
        "end_hour": "INTEGER",
    }
    for name, col_type in new_columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE bookings ADD COLUMN {name} {col_type}")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS otps (
                purpose TEXT NOT NULL,
                email TEXT NOT NULL,
                otp TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (purpose, email)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                parent_email TEXT NOT NULL,
                child_name TEXT NOT NULL,
                child_age_months INTEGER,
                start_date TEXT NOT NULL,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _migrate_bookings_table(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                type TEXT NOT NULL,
                booking_id INTEGER,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                min_age_months INTEGER NOT NULL,
                max_age_months INTEGER NOT NULL,
                care_type TEXT NOT NULL,
                staff_count INTEGER NOT NULL,
                capacity_total INTEGER NOT NULL,
                capacity_used INTEGER NOT NULL DEFAULT 0,
                qualification_hours INTEGER NOT NULL,
                practicum_hours INTEGER NOT NULL,
                has_pflegeerlaubnis INTEGER NOT NULL,
                bio TEXT,
                phone TEXT,
                contact_email TEXT,
                website TEXT,
                owner_email TEXT UNIQUE
            )
            """
        )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user(email: str) -> Optional[UserRow]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return None
    return {
        "email": row["email"],
        "name": row["name"],
        "hashed_password": row["hashed_password"],
        "role": row["role"],
        "verified": bool(row["verified"]),
    }


def create_user(email: str, name: str, hashed_password: str, role: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (email, name, hashed_password, role, verified) VALUES (?, ?, ?, ?, 0)",
            (email, name, hashed_password, role),
        )


def set_user_verified(email: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE users SET verified = 1 WHERE email = ?", (email,))


def set_user_password(email: str, hashed_password: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET hashed_password = ? WHERE email = ?", (hashed_password, email)
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def create_session(token: str, email: str, expires_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, email, expires_at) VALUES (?, ?, ?)",
            (token, email, expires_at),
        )


def get_session(token: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    return {"token": row["token"], "email": row["email"], "expires_at": row["expires_at"]}


def delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------------------------------------------------------------------------
# OTPs (email verification + password reset share the same table, keyed by
# a "purpose" so a user can have one of each in flight at once)
# ---------------------------------------------------------------------------

def set_otp(purpose: str, email: str, otp: str, expires_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO otps (purpose, email, otp, expires_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(purpose, email) DO UPDATE SET otp = excluded.otp, expires_at = excluded.expires_at
            """,
            (purpose, email, otp, expires_at),
        )


def get_otp(purpose: str, email: str) -> Optional[OtpRow]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT otp, expires_at FROM otps WHERE purpose = ? AND email = ?", (purpose, email)
        ).fetchone()
    if not row:
        return None
    return {"otp": row["otp"], "expires_at": row["expires_at"]}


def delete_otp(purpose: str, email: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM otps WHERE purpose = ? AND email = ?", (purpose, email))


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

_PROVIDER_FIELDS = (
    "name", "city", "min_age_months", "max_age_months", "care_type", "staff_count",
    "capacity_total", "capacity_used", "qualification_hours", "practicum_hours",
    "has_pflegeerlaubnis", "bio", "phone", "contact_email", "website", "owner_email",
)


def _row_to_provider_dict(row: sqlite3.Row) -> dict:
    data = {field: row[field] for field in _PROVIDER_FIELDS}
    data["id"] = row["id"]
    data["has_pflegeerlaubnis"] = bool(row["has_pflegeerlaubnis"])
    return data


def seed_providers_if_empty(seed_rows: list[dict]) -> None:
    """Insert seed providers (with their fixed demo ids) only on a fresh database."""
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        if count:
            return
        for row in seed_rows:
            conn.execute(
                f"""
                INSERT INTO providers (id, {", ".join(_PROVIDER_FIELDS)})
                VALUES (:id, {", ".join(f":{f}" for f in _PROVIDER_FIELDS)})
                """,
                row,
            )


def list_providers() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM providers").fetchall()
    return [_row_to_provider_dict(row) for row in rows]


def get_provider(provider_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    return _row_to_provider_dict(row) if row else None


def get_provider_by_owner(owner_email: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM providers WHERE owner_email = ?", (owner_email,)
        ).fetchone()
    return _row_to_provider_dict(row) if row else None


def insert_provider(data: dict) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO providers ({", ".join(_PROVIDER_FIELDS)})
            VALUES ({", ".join(f":{f}" for f in _PROVIDER_FIELDS)})
            """,
            data,
        )
        return cursor.lastrowid


def update_provider_capacity(provider_id: int, capacity_used: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE providers SET capacity_used = ? WHERE id = ?", (capacity_used, provider_id)
        )


def update_provider(provider_id: int, data: dict) -> None:
    """Overwrite the editable profile fields present in `data` (owner_email untouched)."""
    fields = [f for f in _PROVIDER_FIELDS if f != "owner_email" and f in data]
    set_clause = ", ".join(f"{f} = :{f}" for f in fields)
    params = {f: data[f] for f in fields}
    params["id"] = provider_id
    with _connect() as conn:
        conn.execute(f"UPDATE providers SET {set_clause} WHERE id = :id", params)


def list_cities() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT city FROM providers ORDER BY city").fetchall()
    return [row["city"] for row in rows]


# ---------------------------------------------------------------------------
# Bookings (Eltern requests care from a Tagespflegeperson; the owning account
# confirms/declines)
# ---------------------------------------------------------------------------

_BOOKING_FIELDS = (
    "provider_id", "parent_email", "child_name", "child_age_months",
    "start_date", "start_hour", "end_hour", "parent_address", "parent_phone",
    "message", "status", "created_at", "updated_at",
)


def _row_to_booking_dict(row: sqlite3.Row) -> dict:
    data = {field: row[field] for field in _BOOKING_FIELDS}
    data["id"] = row["id"]
    # Bookings created before parent_address/parent_phone/start_hour/end_hour
    # existed have NULL here (see _migrate_bookings_table) — the Booking
    # model requires real values, so backfill something valid rather than
    # fail to redisplay old rows.
    data["parent_address"] = data["parent_address"] or "Nicht angegeben"
    data["parent_phone"] = data["parent_phone"] or "Nicht angegeben"
    data["start_hour"] = data["start_hour"] if data["start_hour"] is not None else 0
    data["end_hour"] = data["end_hour"] if data["end_hour"] is not None else 0
    return data


def insert_booking(data: dict) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO bookings ({", ".join(_BOOKING_FIELDS)})
            VALUES ({", ".join(f":{f}" for f in _BOOKING_FIELDS)})
            """,
            data,
        )
        return cursor.lastrowid


def get_booking(booking_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    return _row_to_booking_dict(row) if row else None


def list_bookings_by_parent(parent_email: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE parent_email = ? ORDER BY created_at DESC", (parent_email,)
        ).fetchall()
    return [_row_to_booking_dict(row) for row in rows]


def list_bookings_by_provider(provider_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE provider_id = ? ORDER BY created_at DESC", (provider_id,)
        ).fetchall()
    return [_row_to_booking_dict(row) for row in rows]


def update_booking_status(booking_id: int, status: str, updated_at: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE bookings SET status = ?, updated_at = ? WHERE id = ?",
            (status, updated_at, booking_id),
        )


# ---------------------------------------------------------------------------
# Notifications (in-app only; one row per recipient per event)
# ---------------------------------------------------------------------------

def insert_notification(data: dict) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (recipient_email, type, booking_id, title, body, is_read, created_at)
            VALUES (:recipient_email, :type, :booking_id, :title, :body, 0, :created_at)
            """,
            data,
        )
        return cursor.lastrowid


def list_notifications(recipient_email: str, limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM notifications WHERE recipient_email = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (recipient_email, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "type": row["type"],
            "booking_id": row["booking_id"],
            "title": row["title"],
            "body": row["body"],
            "is_read": bool(row["is_read"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def count_unread_notifications(recipient_email: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE recipient_email = ? AND is_read = 0",
            (recipient_email,),
        ).fetchone()
    return row[0]


def mark_notification_read(notification_id: int, recipient_email: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_email = ?",
            (notification_id, recipient_email),
        )


def mark_all_notifications_read(recipient_email: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE recipient_email = ? AND is_read = 0",
            (recipient_email,),
        )
