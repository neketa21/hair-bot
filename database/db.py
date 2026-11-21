"""SQLite storage for bookings + free-slot calculation.

Key design decision: we do NOT store "free slots". We store only real
bookings and compute free slots on the fly. This removes the whole class
of bugs where "free slot" records drift out of sync with bookings.

Race-condition protection: create_booking() runs an INSERT inside a
BEGIN IMMEDIATE transaction and re-checks that the requested interval is
still free. If two clients hit the same slot at the same moment, only one
INSERT wins, the other gets False and the handler asks to pick another slot.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta

import aiosqlite

# --- Configuration (change here to change the barbershop schedule) ----------

WORKDAY_START_HOUR = 10  # first slot starts at 10:00
WORKDAY_END_HOUR = 20    # last slot must END by 20:00
SLOT_STEP_MINUTES = 30   # slots go every 30 minutes

DB_PATH = os.path.join(os.path.dirname(__file__), "barber.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     INTEGER NOT NULL,
    client_name   TEXT    NOT NULL,
    client_phone  TEXT    NOT NULL,
    master        TEXT    NOT NULL,
    service       TEXT    NOT NULL,
    start_time    TEXT    NOT NULL,   -- 'YYYY-MM-DD HH:MM'
    end_time      TEXT    NOT NULL,   -- 'YYYY-MM-DD HH:MM'
    status        TEXT    NOT NULL DEFAULT 'active',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bookings_master_day
    ON bookings (master, start_time, status);
"""


# --- Init -------------------------------------------------------------------


async def init_db() -> None:
    """Create the table and index if they do not exist. Safe to call on every start."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# --- Helpers ----------------------------------------------------------------


def _to_dt(day: str, hhmm: str) -> datetime:
    """Build a datetime from 'YYYY-MM-DD' and 'HH:MM'."""
    h, m = hhmm.split(":")
    return datetime.combine(date.fromisoformat(day), time(int(h), int(m)))


def _to_db(dt: datetime) -> str:
    """Serialize to 'YYYY-MM-DD HH:MM' (lexicographic order == chronological)."""
    return dt.strftime("%Y-%m-%d %H:%M")


def _all_slot_starts(day: str, duration_min: int) -> list[datetime]:
    """Every possible slot start for the given day and service duration.

    A slot is generated only if start + duration <= WORKDAY_END_HOUR:00.
    """
    day_start = datetime.combine(date.fromisoformat(day), time(WORKDAY_START_HOUR, 0))
    day_end = datetime.combine(date.fromisoformat(day), time(WORKDAY_END_HOUR, 0))
    duration = timedelta(minutes=duration_min)

    slots: list[datetime] = []
    cursor = day_start
    while cursor + duration <= day_end:
        slots.append(cursor)
        cursor += timedelta(minutes=SLOT_STEP_MINUTES)
    return slots


# --- Public API -------------------------------------------------------------


async def get_free_slots(master: str, day: str, duration_min: int) -> list[str]:
    """Return free slot starts for a master on a day, as 'HH:MM' strings.

    A slot is free if it does not overlap any active booking of this master.
    Past slots (for today) are filtered out too.
    """
    duration = timedelta(minutes=duration_min)
    now = datetime.now()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT start_time, end_time FROM bookings "
            "WHERE master = ? AND status = 'active' AND start_time LIKE ?",
            (master, f"{day}%"),
        ) as cursor:
            busy = [
                (datetime.strptime(row[0], "%Y-%m-%d %H:%M"),
                 datetime.strptime(row[1], "%Y-%m-%d %H:%M"))
                for row in await cursor.fetchall()
            ]

    free: list[str] = []
    for start in _all_slot_starts(day, duration_min):
        end = start + duration
        if start < now:  # cannot book in the past
            continue
        # overlap test: [start, end) vs [b_start, b_end)
        if any(start < b_end and end > b_start for b_start, b_end in busy):
            continue
        free.append(start.strftime("%H:%M"))
    return free


async def create_booking(
    *,
    client_id: int,
    client_name: str,
    client_phone: str,
    master: str,
    service: str,
    day: str,
    start_hhmm: str,
    duration_min: int,
) -> bool:
    """Atomically create a booking. Returns True on success, False if slot is taken.

    The whole check-and-insert runs inside BEGIN IMMEDIATE, so two parallel
    clients cannot both insert the same interval.
    """
    start_dt = _to_dt(day, start_hhmm)
    end_dt = start_dt + timedelta(minutes=duration_min)
    start_s = _to_db(start_dt)
    end_s = _to_db(end_dt)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT 1 FROM bookings "
                "WHERE master = ? AND status = 'active' "
                "  AND start_time < ? AND end_time > ?",
                (master, end_s, start_s),
            ) as cursor:
                if await cursor.fetchone() is not None:
                    await db.rollback()
                    return False

            await db.execute(
                "INSERT INTO bookings "
                "(client_id, client_name, client_phone, master, service, "
                " start_time, end_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (client_id, client_name, client_phone, master, service,
                 start_s, end_s),
            )
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            raise