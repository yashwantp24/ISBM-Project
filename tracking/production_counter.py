# production_counter.py
"""
Tracks bottle production using the PLC's Production Quantity tag as the source.

The PLC already accounts for cavity count — its Production Quantity register
increments by the actual number of bottles produced each cycle. So we read
the delta from that tag directly via the cycle row, with no need to know or
configure cavity count separately.

Design:
  - Called with notify_cycle(bottles_this_cycle, ...) on every completed cycle.
    bottles_this_cycle comes straight from the Production Quantity delta the
    PLC reports — already multiplied by cavities by the machine itself.
  - On startup: reloads today's committed count from DB so the counter
    NEVER starts from 0 after a process restart.
  - At midnight: writes the archive snapshot for the completed day,
    resets the live counter for the new day.
  - Every `flush_every` bottles: upserts the live total to DB so it
    survives unexpected crashes without waiting until midnight.

Tables used (separate from machine_data):
  production_live  –  running daily total per machine (upserted every N bottles)
  daily_archive    –  end-of-day snapshot at midnight (shared with DowntimeTracker)
"""

from __future__ import annotations
from collections import deque
from datetime import datetime, date, timedelta
from typing import Deque, Tuple

from database.connection import get_conn as _conn


# ─── low-level DB helpers ─────────────────────────────────────────────────────

def _upsert_live(machine_id: int, mold_id: int, day: date, total_bottles: int):
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO production_live (machine_id, mold_id, date, total_bottles)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (machine_id, date) DO UPDATE SET
                    mold_id       = EXCLUDED.mold_id,
                    total_bottles = EXCLUDED.total_bottles
                """,
                (machine_id, mold_id, day, total_bottles),
            )


def _load_committed_today(machine_id: int, day: date) -> int:
    """Read today's committed bottle count on startup so we never start from 0."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(total_bottles, 0)
                FROM production_live
                WHERE machine_id = %s AND date = %s
                """,
                (machine_id, day),
            )
            row = cur.fetchone()
    return int(row[0]) if row else 0


def _write_production_archive(machine_id: int, mold_id: int, day: date, total_bottles: int):
    """
    Called once at midnight. Upserts total_bottles + mold_id into daily_archive.
    Only touches these two columns — DowntimeTracker handles the downtime columns
    in a separate upsert, so execution order does not matter.
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_archive (machine_id, mold_id, date, total_bottles)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (machine_id, date) DO UPDATE SET
                    mold_id       = EXCLUDED.mold_id,
                    total_bottles = EXCLUDED.total_bottles
                """,
                (machine_id, mold_id, day, total_bottles),
            )


# ─── ProductionCounter ────────────────────────────────────────────────────────

class ProductionCounter:
    """
    One instance per machine. Wire into your polling loop:

        counter.notify_cycle(bottles, mold_id, timestamp)   # every completed cycle
        counter.live_state()                                 # from dashboard
        counter.flush(mold_id)                               # on process shutdown
    """

    def __init__(self, machine_id: int, flush_every: int = 10):
        self.machine_id = machine_id
        self._flush_every = flush_every
        self._today: date = date.today()

        # Resume from committed value — never starts from 0 after a restart
        self._bottles_today: int = _load_committed_today(machine_id, self._today)
        self._since_last_flush: int = 0

        # Ring buffer of (timestamp, cumulative_count) for rolling rate calculation
        self._ring: Deque[Tuple[datetime, int]] = deque()

    # ── private ───────────────────────────────────────────────────────────────

    def _midnight_rollover(self, mold_id: int, now: datetime):
        yesterday = self._today
        _write_production_archive(self.machine_id, mold_id, yesterday, self._bottles_today)
        self._today = now.date()
        self._bottles_today = _load_committed_today(self.machine_id, self._today)
        self._since_last_flush = 0
        self._ring.clear()

    def _prune_ring(self, now: datetime):
        cutoff = now - timedelta(hours=1)
        while self._ring and self._ring[0][0] < cutoff:
            self._ring.popleft()

    # ── public API ────────────────────────────────────────────────────────────

    def notify_cycle(self, bottles: int, mold_id: int, timestamp: datetime | None = None):
        """
        Call ONCE every time CycleLogger returns a valid cycle row.

        bottles    – Production Quantity delta for this cycle, as reported by
                     the PLC. The machine already accounts for cavity count,
                     so this is the actual number of bottles produced this cycle.
        mold_id    – from information.get_machine(m)["mold"]
        timestamp  – the cycle's timestamp; defaults to datetime.now()
        """
        if bottles is None or bottles <= 0:
            return  # skip invalid / missing reads

        now = timestamp or datetime.now()

        if now.date() != self._today:
            self._midnight_rollover(mold_id, now)

        self._bottles_today += bottles
        self._since_last_flush += bottles

        self._prune_ring(now)
        self._ring.append((now, self._bottles_today))

        if self._since_last_flush >= self._flush_every:
            _upsert_live(self.machine_id, mold_id, self._today, self._bottles_today)
            self._since_last_flush = 0

    def bottles_per_hour(self) -> float:
        """Rolling bottles/hr over the last hour of cycle data."""
        if len(self._ring) < 2:
            return 0.0
        oldest_ts, oldest_count = self._ring[0]
        newest_ts, newest_count = self._ring[-1]
        elapsed_hr = (newest_ts - oldest_ts).total_seconds() / 3600
        if elapsed_hr < 1e-9:
            return 0.0
        return round((newest_count - oldest_count) / elapsed_hr, 1)

    def live_state(self) -> dict:
        """
        Returns a snapshot for the dashboard live counter.

        Keys:
            machine_id       int
            date             str
            bottles_today    int
            bottles_per_hour float
        """
        return {
            "machine_id":       self.machine_id,
            "date":             self._today.isoformat(),
            "bottles_today":    self._bottles_today,
            "bottles_per_hour": self.bottles_per_hour(),
        }

    def flush(self, mold_id: int):
        """Persist current live total and archive snapshot on clean shutdown."""
        _upsert_live(self.machine_id, mold_id, self._today, self._bottles_today)
        _write_production_archive(self.machine_id, mold_id, self._today, self._bottles_today)
