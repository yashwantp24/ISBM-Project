# setup_tracking_tables.py
"""
Creates all tables required by DowntimeTracker and ProductionCounter.
Run once before starting the tracking runner:

    python setup_tracking_tables.py

Tables created
──────────────
downtime_events           Raw downtime intervals — one row per completed event
daily_downtime_live       Running daily downtime total, upserted after every event
shift_downtime_live       Running shift downtime total + event count  (NEW)
production_live           Running daily bottle count, upserted every N cycles
daily_archive             End-of-day snapshot combining downtime + production
shift_downtime_archive    End-of-shift snapshot (written at shift boundary)  (NEW)

Shifts:
    Shift 1  00:00 – 08:00
    Shift 2  08:00 – 16:00
    Shift 3  16:00 – 00:00

All tables are intentionally separate from the existing machine_data table.
"""

from database.connection import get_conn as _conn


def create_tables():
    conn = _conn()
    cur  = conn.cursor()

    # ── Raw downtime events ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_events (
            id               SERIAL    PRIMARY KEY,
            machine_id       INT       NOT NULL,
            mold_id          INT,
            start_time       TIMESTAMP NOT NULL,
            end_time         TIMESTAMP NOT NULL,
            duration_seconds FLOAT     NOT NULL
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_downtime_events_machine_date
        ON downtime_events (machine_id, DATE(start_time));
    """)

    # ── Running daily downtime total (live) ───────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_downtime_live (
            machine_id             INT   NOT NULL,
            mold_id                INT,
            date                   DATE  NOT NULL,
            total_downtime_seconds FLOAT NOT NULL DEFAULT 0,
            PRIMARY KEY (machine_id, date)
        );
    """)

    # ── Running shift downtime total (live) ── NEW ────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_downtime_live (
            machine_id             INT   NOT NULL,
            mold_id                INT,
            date                   DATE  NOT NULL,
            shift                  INT   NOT NULL CHECK (shift IN (1, 2, 3)),
            total_downtime_seconds FLOAT NOT NULL DEFAULT 0,
            event_count            INT   NOT NULL DEFAULT 0,
            PRIMARY KEY (machine_id, date, shift)
        );
    """)

    # ── Running daily production total (live) ─────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS production_live (
            machine_id    INT  NOT NULL,
            mold_id       INT,
            date          DATE NOT NULL,
            total_bottles INT  NOT NULL DEFAULT 0,
            PRIMARY KEY (machine_id, date)
        );
    """)

    # ── End-of-day archive snapshot (shift columns included) ──────────────────
    # One row per machine per day. Each shift's downtime and event count are
    # stored as dedicated columns so no join is needed for reporting.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_archive (
            machine_id               INT   NOT NULL,
            mold_id                  INT,
            date                     DATE  NOT NULL,
            total_bottles            INT   NOT NULL DEFAULT 0,
            total_downtime_seconds   FLOAT NOT NULL DEFAULT 0,
            downtime_event_count     INT   NOT NULL DEFAULT 0,
            shift_1_downtime_seconds FLOAT NOT NULL DEFAULT 0,
            shift_1_events           INT   NOT NULL DEFAULT 0,
            shift_2_downtime_seconds FLOAT NOT NULL DEFAULT 0,
            shift_2_events           INT   NOT NULL DEFAULT 0,
            shift_3_downtime_seconds FLOAT NOT NULL DEFAULT 0,
            shift_3_events           INT   NOT NULL DEFAULT 0,
            PRIMARY KEY (machine_id, date)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("✓  downtime_events          created / verified")
    print("✓  daily_downtime_live      created / verified")
    print("✓  shift_downtime_live      created / verified")
    print("✓  production_live          created / verified")
    print("✓  daily_archive            created / verified  (includes shift columns)")


if __name__ == "__main__":
    create_tables()


def reset_tables():
    """
    DROP and recreate all tracking tables. Wipes all data — use intentionally.
    Run with:  python -c "from setup_tracking_tables import reset_tables; reset_tables()"
    """
    conn = _conn()
    cur  = conn.cursor()
    tables = [
        "daily_archive",
        "shift_downtime_live",
        "daily_downtime_live",
        "downtime_events",
        "production_live",
    ]
    for t in tables:
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
        print(f"✗  {t:<30s} dropped")
    conn.commit()
    cur.close()
    conn.close()
    print("\nRecreating...")
    create_tables()
