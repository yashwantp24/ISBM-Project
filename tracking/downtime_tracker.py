# downtime_tracker.py
"""
Tracks Auto Cycle signal transitions to detect and record machine downtime.

Daily rules (unchanged):
  - Auto Cycle goes 0  →  downtime starts
  - Auto Cycle goes 1  →  downtime ends, event committed to DB
  - On startup         →  reloads today's committed downtime so the live
                          counter NEVER starts from 0 after a restart
  - At midnight        →  writes daily archive snapshot, resets daily counter

Shift rules (NEW):
  - Shifts are fixed 8-hour windows:
        Shift 1  00:00 – 08:00
        Shift 2  08:00 – 16:00
        Shift 3  16:00 – 00:00
  - On shift boundary crossing → closes any open event at the boundary,
    writes downtime_shift_archive for the completed shift, resets shift
    counters for the new shift.
  - On startup → reloads committed downtime for the current shift so the
    shift counter also resumes correctly.

Tables used (all separate from machine_data):
  downtime_events         –  one row per completed downtime interval
  daily_downtime_live     –  running daily total per machine
  shift_downtime_live     –  running shift total per machine  (NEW)
  daily_archive           –  end-of-day snapshot at midnight
  shift_downtime_archive  –  end-of-shift snapshot            (NEW)
"""

from __future__ import annotations
from datetime import datetime, date, time as dtime

from database.connection import get_conn as _conn


# ─── Shift helpers ─────────────────────────────────────────────────────────────

SHIFT_BOUNDARIES = [0, 8, 16, 24]   # hours that start each shift boundary

def get_shift(dt: datetime) -> int:
    """Return shift number (1, 2, or 3) for a given datetime."""
    h = dt.hour
    if h < 8:
        return 1
    elif h < 16:
        return 2
    else:
        return 3

def shift_start(dt: datetime) -> datetime:
    """Return the start datetime of the shift that dt falls in."""
    s = get_shift(dt)
    start_hour = {1: 0, 2: 8, 3: 16}[s]
    return dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)

def shift_end(dt: datetime) -> datetime:
    """Return the end datetime (exclusive boundary) of the shift that dt falls in."""
    s = get_shift(dt)
    end_hour = {1: 8, 2: 16, 3: 0}[s]
    if s == 3:
        # ends at midnight → next calendar day
        from datetime import timedelta
        base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return base + __import__('datetime').timedelta(days=1)
    return dt.replace(hour=end_hour, minute=0, second=0, microsecond=0)


# ─── low-level DB helpers ──────────────────────────────────────────────────────

def _insert_event(
    machine_id: int, mold_id: int, start: datetime, end: datetime
) -> float:
    """Persist a completed downtime event. Returns duration in seconds."""
    duration = (end - start).total_seconds()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO downtime_events
                    (machine_id, mold_id, start_time, end_time, duration_seconds)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (machine_id, mold_id, start, end, duration),
            )
    return duration


def _upsert_daily_live(machine_id: int, mold_id: int, day: date, total_seconds: float):
    """Keep the running daily total current for live dashboard queries."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_downtime_live
                    (machine_id, mold_id, date, total_downtime_seconds)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (machine_id, date) DO UPDATE SET
                    mold_id                = EXCLUDED.mold_id,
                    total_downtime_seconds = EXCLUDED.total_downtime_seconds
                """,
                (machine_id, mold_id, day, total_seconds),
            )


def _upsert_shift_live(
    machine_id: int, mold_id: int, day: date, shift: int,
    total_seconds: float, event_count: int,
):
    """Keep the running shift total current for live dashboard queries."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO shift_downtime_live
                    (machine_id, mold_id, date, shift, total_downtime_seconds, event_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (machine_id, date, shift) DO UPDATE SET
                    mold_id                = EXCLUDED.mold_id,
                    total_downtime_seconds = EXCLUDED.total_downtime_seconds,
                    event_count            = EXCLUDED.event_count
                """,
                (machine_id, mold_id, day, shift, total_seconds, event_count),
            )


def _load_committed_today(machine_id: int, day: date) -> float:
    """Sum all completed events already in DB for today (for restart resume)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0)
                FROM downtime_events
                WHERE machine_id = %s AND DATE(start_time) = %s
                """,
                (machine_id, day),
            )
            return float(cur.fetchone()[0])


def _load_committed_shift(machine_id: int, day: date, shift: int) -> tuple[float, int]:
    """
    Sum completed events in DB for the current shift.
    Uses exact timestamp boundaries rather than EXTRACT(HOUR) so that
    boundary-split events are attributed to the correct shift.
    Returns (total_seconds, event_count).
    """
    from datetime import datetime as _dt, timedelta as _td
    start_hour = {1: 0, 2: 8, 3: 16}[shift]
    shift_start_ts = _dt(day.year, day.month, day.day, start_hour, 0, 0)
    if shift == 3:
        shift_end_ts = _dt(day.year, day.month, day.day, 0, 0, 0) + _td(days=1)
    else:
        end_hour = {1: 8, 2: 16}[shift]
        shift_end_ts = _dt(day.year, day.month, day.day, end_hour, 0, 0)

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(duration_seconds), 0), COUNT(*)
                FROM downtime_events
                WHERE machine_id = %s
                  AND start_time >= %s
                  AND start_time < %s
                """,
                (machine_id, shift_start_ts, shift_end_ts),
            )
            row = cur.fetchone()
    return float(row[0]), int(row[1])


def _count_events_today(machine_id: int, day: date) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM downtime_events
                WHERE machine_id = %s AND DATE(start_time) = %s
                """,
                (machine_id, day),
            )
            return cur.fetchone()[0]


def _write_daily_archive(
    machine_id: int, mold_id: int, day: date,
    total_downtime_sec: float, event_count: int,
    shift_1_sec: float = 0, shift_1_ev: int = 0,
    shift_2_sec: float = 0, shift_2_ev: int = 0,
    shift_3_sec: float = 0, shift_3_ev: int = 0,
):
    """
    Upserts the daily archive row, writing both the day totals and per-shift
    breakdown in one shot. Called at midnight (full picture) or at shift
    boundaries (partial update of shift columns only).
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_archive (
                    machine_id, mold_id, date,
                    total_downtime_seconds, downtime_event_count,
                    shift_1_downtime_seconds, shift_1_events,
                    shift_2_downtime_seconds, shift_2_events,
                    shift_3_downtime_seconds, shift_3_events
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (machine_id, date) DO UPDATE SET
                    mold_id                  = EXCLUDED.mold_id,
                    total_downtime_seconds   = EXCLUDED.total_downtime_seconds,
                    downtime_event_count     = EXCLUDED.downtime_event_count,
                    shift_1_downtime_seconds = EXCLUDED.shift_1_downtime_seconds,
                    shift_1_events           = EXCLUDED.shift_1_events,
                    shift_2_downtime_seconds = EXCLUDED.shift_2_downtime_seconds,
                    shift_2_events           = EXCLUDED.shift_2_events,
                    shift_3_downtime_seconds = EXCLUDED.shift_3_downtime_seconds,
                    shift_3_events           = EXCLUDED.shift_3_events
                """,
                (
                    machine_id, mold_id, day,
                    total_downtime_sec, event_count,
                    shift_1_sec, shift_1_ev,
                    shift_2_sec, shift_2_ev,
                    shift_3_sec, shift_3_ev,
                ),
            )


# ─── DowntimeTracker ───────────────────────────────────────────────────────────

class DowntimeTracker:
    """
    One instance per machine. Wire into your polling loop:

        tracker.update(auto_cycle, mold_id, timestamp)   # every poll
        tracker.live_state()                             # from dashboard
        tracker.flush(mold_id)                           # on process shutdown
    """

    def __init__(self, machine_id: int):
        self.machine_id = machine_id
        now = datetime.now()
        self._today: date     = now.date()
        self._shift: int      = get_shift(now)

        # Resume daily total from DB
        self._committed_today: float = _load_committed_today(machine_id, self._today)

        # Resume shift totals from DB
        shift_sec, shift_cnt = _load_committed_shift(machine_id, self._today, self._shift)
        self._committed_shift: float = shift_sec
        self._shift_events:    int   = shift_cnt

        self._is_down:         bool          = False
        self._downtime_start:  datetime|None = None
        self._mold_id:         int|None      = None

    # ── private ────────────────────────────────────────────────────────────────

    def _close_event(self, mold_id: int, end: datetime):
        """Commit the current open downtime event, update daily + shift totals."""
        duration = _insert_event(self.machine_id, mold_id, self._downtime_start, end)
        self._committed_today += duration
        self._committed_shift += duration
        self._shift_events    += 1
        _upsert_daily_live(self.machine_id, mold_id, self._today, self._committed_today)
        _upsert_shift_live(
            self.machine_id, mold_id, self._today, self._shift,
            self._committed_shift, self._shift_events,
        )
        self._is_down         = False
        self._downtime_start  = None
        self._mold_id         = None

    def _shift_rollover(self, mold_id: int, new_shift: int, new_day: date, boundary: datetime):
        """
        Called when the poll timestamp crosses into a new shift.
        1. Close any open event at the exact shift boundary.
        2. Write the completed shift's totals into shift_downtime_live.
        3. Update daily_archive preserving other shifts' data.
        4. Reset shift counters for the new shift.
        """
        if self._is_down and self._downtime_start:
            self._close_event(self._mold_id or mold_id, boundary)

        # Write the completed shift's live totals
        _upsert_shift_live(
            self.machine_id, mold_id, self._today, self._shift,
            self._committed_shift, self._shift_events,
        )

        # Update daily_archive — read ALL shifts from DB so we never zero out
        # another shift's data
        s1_sec, s1_ev = _load_committed_shift(self.machine_id, self._today, 1)
        s2_sec, s2_ev = _load_committed_shift(self.machine_id, self._today, 2)
        s3_sec, s3_ev = _load_committed_shift(self.machine_id, self._today, 3)

        _write_daily_archive(
            self.machine_id, mold_id, self._today,
            total_downtime_sec=self._committed_today,
            event_count=_count_events_today(self.machine_id, self._today),
            shift_1_sec=s1_sec, shift_1_ev=s1_ev,
            shift_2_sec=s2_sec, shift_2_ev=s2_ev,
            shift_3_sec=s3_sec, shift_3_ev=s3_ev,
        )

        # Reset for new shift
        self._today  = new_day
        self._shift  = new_shift
        shift_sec, shift_cnt = _load_committed_shift(self.machine_id, new_day, new_shift)
        self._committed_shift = shift_sec
        self._shift_events    = shift_cnt

        # If machine was down, re-open the event from the boundary
        if self._is_down:
            self._downtime_start = boundary

    def _midnight_rollover(self, mold_id: int, now: datetime):
        """
        Called when the poll timestamp crosses into a new calendar day.
        Writes the complete daily archive row (totals + all shift columns),
        then resets daily and shift counters for the new day.
        Note: _shift_rollover already fires for Shift 3 → Shift 1, so by the
        time this runs the Shift 3 upsert has already been written. This final
        write merges everything into a clean end-of-day snapshot.
        """
        yesterday   = self._today
        event_count = _count_events_today(self.machine_id, yesterday)

        # Collect all three shifts' archived totals from DB for the final row
        s1_sec, s1_ev = _load_committed_shift(self.machine_id, yesterday, 1)
        s2_sec, s2_ev = _load_committed_shift(self.machine_id, yesterday, 2)
        s3_sec, s3_ev = _load_committed_shift(self.machine_id, yesterday, 3)

        _write_daily_archive(
            self.machine_id, mold_id, yesterday,
            total_downtime_sec=self._committed_today,
            event_count=event_count,
            shift_1_sec=s1_sec, shift_1_ev=s1_ev,
            shift_2_sec=s2_sec, shift_2_ev=s2_ev,
            shift_3_sec=s3_sec, shift_3_ev=s3_ev,
        )
        self._today           = now.date()
        self._committed_today = _load_committed_today(self.machine_id, self._today)

    # ── public API ─────────────────────────────────────────────────────────────

    def update(self, auto_cycle, mold_id: int, timestamp: datetime | None = None):
        """
        Call every poll cycle.

        auto_cycle  – 1 = machine running, anything else = stopped
        mold_id     – current mold from information.get_machine(m)["mold"]
        timestamp   – defaults to datetime.now()
        """
        now       = timestamp or datetime.now()
        now_shift = get_shift(now)
        now_day   = now.date()
        prev_day  = self._today

        # ── Shift rollover ────────────────────────────────────────────────────
        if now_shift != self._shift or now_day != self._today:
            # Compute exact boundary timestamp
            boundary = shift_start(now)
            self._shift_rollover(mold_id, now_shift, now_day, boundary)

        # ── Daily rollover (midnight = Shift 3 → Shift 1) ─────────────────────
        # Note: _shift_rollover already split any open event at the shift
        # boundary (which IS midnight for shift 3→1). No need to close again.
        if now_day != prev_day:
            self._midnight_rollover(mold_id, now)

        # ── Normal state machine ──────────────────────────────────────────────
        if auto_cycle != 1:
            if not self._is_down:
                self._is_down        = True
                self._downtime_start = now
                self._mold_id        = mold_id
        else:
            if self._is_down:
                self._close_event(self._mold_id or mold_id, now)

    def live_state(self) -> dict:
        """
        Returns a snapshot for the dashboard.

        Daily keys:
            machine_id, mold_id, is_down, downtime_start,
            current_event_sec, total_downtime_sec, total_downtime_min,
            total_downtime_hr, date

        Shift keys (NEW):
            shift                  int    (1, 2, or 3)
            shift_downtime_sec     float  (committed + open event for this shift)
            shift_downtime_min     float
            shift_event_count      int    (completed events this shift)
        """
        now      = datetime.now()
        open_sec = (
            (now - self._downtime_start).total_seconds()
            if self._is_down and self._downtime_start
            else 0.0
        )
        total_day   = self._committed_today + open_sec
        total_shift = self._committed_shift + open_sec

        return {
            # ── daily ──────────────────────────────────────────────────────────
            "machine_id":         self.machine_id,
            "mold_id":            self._mold_id,
            "is_down":            self._is_down,
            "downtime_start":     self._downtime_start.isoformat() if self._downtime_start else None,
            "current_event_sec":  round(open_sec, 1),
            "total_downtime_sec": round(total_day, 1),
            "total_downtime_min": round(total_day / 60, 2),
            "total_downtime_hr":  round(total_day / 3600, 4),
            "date":               self._today.isoformat(),
            # ── shift (NEW) ────────────────────────────────────────────────────
            "shift":              self._shift,
            "shift_downtime_sec": round(total_shift, 1),
            "shift_downtime_min": round(total_shift / 60, 2),
            "shift_event_count":  self._shift_events,
        }

    def flush(self, mold_id: int):
        """
        Call on clean shutdown. Saves any open event so no downtime is lost.
        Re-opens the event from the same timestamp so a restart during downtime
        resumes correctly from DB state.
        """
        if self._is_down and self._downtime_start:
            now = datetime.now()
            self._close_event(self._mold_id or mold_id, now)
            self._is_down        = True
            self._downtime_start = now
            self._mold_id        = mold_id