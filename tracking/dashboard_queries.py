# dashboard_queries.py
"""
Read-only query helpers for Streamlit (or any dashboard).
All functions return plain dicts/lists — no psycopg2 objects leak out.

Live queries   →  production_live, daily_downtime_live, downtime_events
Archive queries →  daily_archive, downtime_events
"""

from __future__ import annotations
from datetime import date, timedelta

from database.connection import get_conn as _conn


# ════════════════════════════════════════════════════════════════════════════════
# LIVE QUERIES  (today's running totals)
# ════════════════════════════════════════════════════════════════════════════════

def get_live_downtime(machine_id: int) -> dict:
    """
    Today's committed downtime total.

    Returns:
        machine_id, mold_id, date,
        total_downtime_seconds, total_downtime_minutes, total_downtime_hours,
        event_count
    """
    today = date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(total_downtime_seconds, 0), mold_id
                FROM daily_downtime_live
                WHERE machine_id = %s AND date = %s
                """,
                (machine_id, today),
            )
            row = cur.fetchone()
            total_sec = float(row[0]) if row else 0.0
            mold_id   = row[1] if row else None

            cur.execute(
                """
                SELECT COUNT(*) FROM downtime_events
                WHERE machine_id = %s AND DATE(start_time) = %s
                """,
                (machine_id, today),
            )
            event_count = cur.fetchone()[0]

    return {
        "machine_id":             machine_id,
        "mold_id":                mold_id,
        "date":                   today.isoformat(),
        "total_downtime_seconds": round(total_sec, 1),
        "total_downtime_minutes": round(total_sec / 60, 2),
        "total_downtime_hours":   round(total_sec / 3600, 4),
        "event_count":            event_count,
    }


def get_live_production(machine_id: int) -> dict:
    """
    Today's committed bottle count.

    Returns:
        machine_id, mold_id, date, total_bottles
    """
    today = date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(total_bottles, 0), mold_id
                FROM production_live
                WHERE machine_id = %s AND date = %s
                """,
                (machine_id, today),
            )
            row = cur.fetchone()

    return {
        "machine_id":   machine_id,
        "mold_id":      row[1] if row else None,
        "date":         today.isoformat(),
        "total_bottles": int(row[0]) if row else 0,
    }


def get_today_downtime_events(machine_id: int, limit: int = 200) -> list[dict]:
    """
    All completed downtime events for today, newest first.
    Useful for an event log table on the dashboard.
    """
    today = date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, mold_id, start_time, end_time, duration_seconds
                FROM downtime_events
                WHERE machine_id = %s AND DATE(start_time) = %s
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (machine_id, today, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "id":               r[0],
            "mold_id":          r[1],
            "start_time":       r[2].isoformat(),
            "end_time":         r[3].isoformat(),
            "duration_seconds": round(r[4], 1),
            "duration_minutes": round(r[4] / 60, 2),
        }
        for r in rows
    ]


# ════════════════════════════════════════════════════════════════════════════════
# ARCHIVE QUERIES  (historical analysis — daily_archive)
# ════════════════════════════════════════════════════════════════════════════════

def get_archive_range(
    machine_id: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Daily archive rows for a date range.
    Use for trend charts, shift reports, and OEE analysis.

    Returns list of dicts with:
        date, mold_id, total_bottles,
        total_downtime_seconds, total_downtime_minutes,
        downtime_event_count, availability_pct
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, mold_id, total_bottles,
                       total_downtime_seconds, downtime_event_count
                FROM daily_archive
                WHERE machine_id = %s
                  AND date BETWEEN %s AND %s
                ORDER BY date
                """,
                (machine_id, start_date, end_date),
            )
            rows = cur.fetchall()

    return [
        {
            "date":                   r[0].isoformat(),
            "mold_id":                r[1],
            "total_bottles":          r[2],
            "total_downtime_seconds": round(r[3], 1),
            "total_downtime_minutes": round(r[3] / 60, 2),
            "downtime_event_count":   r[4],
            "availability_pct":       round(max(0, (86400 - r[3]) / 86400 * 100), 2),
        }
        for r in rows
    ]


def get_archive_last_n_days(machine_id: int, days: int = 7) -> list[dict]:
    """Convenience wrapper: last N completed days from the archive."""
    end   = date.today()
    start = end - timedelta(days=days)
    return get_archive_range(machine_id, start, end)


def get_multi_machine_live_summary(machine_ids: list[int]) -> list[dict]:
    """
    Fleet-level overview: one row per machine with today's live totals.

    Returns list of dicts:
        machine_id, mold_id, date, total_bottles,
        total_downtime_minutes, event_count, availability_pct
    """
    results = []
    for mid in machine_ids:
        dt   = get_live_downtime(mid)
        prod = get_live_production(mid)
        avail = round(
            max(0, (86400 - dt["total_downtime_seconds"]) / 86400 * 100), 2
        )
        results.append({
            "machine_id":             mid,
            "mold_id":                dt["mold_id"],
            "date":                   dt["date"],
            "total_bottles":          prod["total_bottles"],
            "total_downtime_minutes": dt["total_downtime_minutes"],
            "event_count":            dt["event_count"],
            "availability_pct":       avail,
        })
    return results
