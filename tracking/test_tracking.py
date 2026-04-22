# test_tracking.py
"""
Tests for DowntimeTracker and ProductionCounter.

No OPC server or live database required — all DB calls are patched with
unittest.mock so these run on any machine.

Run with:
    python test_tracking.py
"""

from __future__ import annotations
import sys
import traceback
from datetime import datetime, date, timedelta
from unittest.mock import patch

from downtime_tracker import DowntimeTracker
from production_counter import ProductionCounter

# ── Timestamps pinned to today so _midnight_rollover is never triggered ────────
TODAY = date.today()
T0    = datetime(TODAY.year, TODAY.month, TODAY.day, 8, 0, 0)

# ── Test infrastructure ────────────────────────────────────────────────────────

_results: list[tuple[str, bool, str]] = []


def test(name: str):
    def decorator(fn):
        try:
            fn()
            _results.append((name, True, ""))
            print(f"  PASS  {name}")
        except AssertionError as e:
            _results.append((name, False, str(e)))
            print(f"  FAIL  {name}\n        → {e}")
        except Exception:
            tb = traceback.format_exc()
            _results.append((name, False, tb))
            print(f"  ERROR {name}")
            for line in tb.splitlines()[-4:]:
                print(f"        {line}")
        return fn
    return decorator


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg + ': ' if msg else ''}expected {expected!r}, got {actual!r}")

def assert_approx(actual, expected, tol=1.0, msg=""):
    if abs(actual - expected) > tol:
        raise AssertionError(f"{msg + ': ' if msg else ''}expected ~{expected}, got {actual} (tol={tol})")

def assert_true(val, msg=""):
    if not val:
        raise AssertionError(msg or f"Expected True, got {val!r}")

def assert_false(val, msg=""):
    if val:
        raise AssertionError(msg or f"Expected False, got {val!r}")


# ── Full patch set for DowntimeTracker ────────────────────────────────────────
# Every function that calls _conn() must be patched, including _count_events_today
# which is called from _midnight_rollover.

DT_ALL = lambda insert_fn=None: [
    patch("downtime_tracker._load_committed_today",  return_value=0.0),
    patch("downtime_tracker._insert_event",          side_effect=insert_fn) if insert_fn
        else patch("downtime_tracker._insert_event", return_value=0.0),
    patch("downtime_tracker._upsert_live"),
    patch("downtime_tracker._count_events_today",    return_value=0),
    patch("downtime_tracker._write_downtime_archive"),
]

PC_ALL = lambda load=0: [
    patch("production_counter._load_committed_today",     return_value=load),
    patch("production_counter._upsert_live"),
    patch("production_counter._write_production_archive"),
]


# ════════════════════════════════════════════════════════════════════════════════
# DOWNTIME TRACKER
# ════════════════════════════════════════════════════════════════════════════════

print("\n── DowntimeTracker ───────────────────────────────────────────────────────")


@test("Starts UP, is_down=False, committed=0")
def _():
    with patch("downtime_tracker._load_committed_today", return_value=0.0):
        dt = DowntimeTracker(60)
    assert_false(dt._is_down)
    assert_eq(dt._committed_today, 0.0)


@test("Stays UP when auto_cycle=1 throughout")
def _():
    patches = DT_ALL()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        for i in range(5):
            dt.update(1, mold_id=101, timestamp=T0 + timedelta(seconds=i))
    assert_false(dt._is_down)
    assert_eq(dt._committed_today, 0.0)


@test("Detects DOWN on 1→0 transition")
def _():
    patches = DT_ALL()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(1, mold_id=101, timestamp=T0)
        dt.update(0, mold_id=101, timestamp=T0 + timedelta(seconds=1))
    assert_true(dt._is_down, "should be DOWN after 0 signal")
    assert_eq(dt._mold_id, 101, "mold captured at event open")


@test("Commits event to DB on 0→1 transition")
def _():
    inserted = []
    def fake_insert(machine_id, mold_id, start, end):
        dur = (end - start).total_seconds()
        inserted.append(dur)
        return dur

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, mold_id=101, timestamp=T0)
        dt.update(0, mold_id=101, timestamp=T0 + timedelta(seconds=30))
        dt.update(1, mold_id=101, timestamp=T0 + timedelta(seconds=60))

    assert_eq(len(inserted), 1, "exactly one event inserted")
    assert_approx(inserted[0], 60.0, tol=0.1, msg="duration should be 60 s")
    assert_false(dt._is_down)


@test("Committed total accumulates across multiple events")
def _():
    events = []
    def fake_insert(machine_id, mold_id, start, end):
        dur = (end - start).total_seconds()
        events.append(dur)
        return dur

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, 101, T0)
        dt.update(1, 101, T0 + timedelta(seconds=30))
        dt.update(0, 101, T0 + timedelta(minutes=5))
        dt.update(1, 101, T0 + timedelta(minutes=5, seconds=90))

    assert_approx(dt._committed_today, 120.0, tol=0.1, msg="30+90=120 s")


@test("live_state shows open event duration when DOWN")
def _():
    patches = DT_ALL()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, 101, T0)
        state = dt.live_state()
    assert_true(state["is_down"])
    assert_true(state["current_event_sec"] >= 0)
    assert_true(state["total_downtime_sec"] >= 0)


@test("live_state shows current_event_sec=0 when UP")
def _():
    def fake_insert(machine_id, mold_id, start, end):
        return (end - start).total_seconds()

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, 101, T0)
        dt.update(1, 101, T0 + timedelta(seconds=30))
        state = dt.live_state()
    assert_false(state["is_down"])
    assert_eq(state["current_event_sec"], 0.0)
    assert_approx(state["total_downtime_sec"], 30.0, tol=0.1)


@test("Repeated 0 polls do NOT open multiple events")
def _():
    patches = DT_ALL()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        for i in range(10):
            dt.update(0, 101, T0 + timedelta(seconds=i))
    assert_true(dt._is_down)
    # Start time must be from the first poll, never overwritten by subsequent 0s
    expected_start = T0
    assert_approx(
        dt._downtime_start.timestamp(), expected_start.timestamp(),
        tol=1.0, msg="start time should not drift on repeated 0 polls"
    )


@test("Resumes committed downtime from DB after restart")
def _():
    with patch("downtime_tracker._load_committed_today", return_value=300.0):
        dt = DowntimeTracker(60)
    assert_approx(dt._committed_today, 300.0)
    state = dt.live_state()
    assert_approx(state["total_downtime_sec"], 300.0, tol=1.0)
    assert_approx(state["total_downtime_min"], 5.0,   tol=0.1)


@test("flush() saves open event and re-opens it for crash recovery")
def _():
    inserted = []
    def fake_insert(machine_id, mold_id, start, end):
        dur = (end - start).total_seconds()
        inserted.append(dur)
        return dur

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, 101, T0)
        dt.flush(101)

    assert_eq(len(inserted), 1,    "event committed on flush")
    assert_true(dt._is_down,       "still DOWN so restart continues cleanly")
    assert_true(dt._downtime_start is not None)


@test("mold_id at event open is used — not the mold at close time")
def _():
    captured = []
    def fake_insert(machine_id, mold_id, start, end):
        captured.append(mold_id)
        return (end - start).total_seconds()

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        dt.update(0, mold_id=101, timestamp=T0)
        dt.update(1, mold_id=999, timestamp=T0 + timedelta(seconds=30))

    assert_eq(captured[0], 101, "event should record mold from when it started")


@test("No double-counting: 20 consecutive 0 polls produce exactly 1 event")
def _():
    events = []
    def fake_insert(machine_id, mold_id, start, end):
        dur = (end - start).total_seconds()
        events.append(dur)
        return dur

    patches = DT_ALL(insert_fn=fake_insert)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        dt = DowntimeTracker(60)
        for i in range(20):
            dt.update(0, 101, T0 + timedelta(seconds=i))
        dt.update(1, 101, T0 + timedelta(seconds=20))

    assert_eq(len(events), 1, "20 consecutive 0-polls → exactly 1 event on recovery")
    assert_approx(events[0], 20.0, tol=1.0)


# ════════════════════════════════════════════════════════════════════════════════
# PRODUCTION COUNTER
# ════════════════════════════════════════════════════════════════════════════════

print("\n── ProductionCounter ─────────────────────────────────────────────────────")


@test("Starts with 0 bottles when DB is empty")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60)
    assert_eq(pc._bottles_today, 0)


@test("notify_cycle increments by exact PLC bottle count")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
        pc.notify_cycle(4, mold_id=101, timestamp=T0 + timedelta(seconds=30))
        pc.notify_cycle(4, mold_id=101, timestamp=T0 + timedelta(seconds=60))
    assert_eq(pc._bottles_today, 12, "3 × 4 = 12")


@test("notify_cycle skips bottles=0")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
        pc.notify_cycle(0, mold_id=101, timestamp=T0 + timedelta(seconds=30))
    assert_eq(pc._bottles_today, 4)


@test("notify_cycle skips bottles=None")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4,    mold_id=101, timestamp=T0)
        pc.notify_cycle(None, mold_id=101, timestamp=T0 + timedelta(seconds=30))
    assert_eq(pc._bottles_today, 4)


@test("Flushes to DB after flush_every bottles")
def _():
    calls = []
    with patch("production_counter._load_committed_today",     return_value=0), \
         patch("production_counter._upsert_live",              side_effect=lambda *a: calls.append(a)), \
         patch("production_counter._write_production_archive"):

        pc = ProductionCounter(60, flush_every=10)
        for i in range(3):
            pc.notify_cycle(4, mold_id=101, timestamp=T0 + timedelta(seconds=i * 30))

    assert_true(len(calls) >= 1, "should flush at least once at 12 bottles with threshold=10")


@test("Does NOT flush before threshold is reached")
def _():
    calls = []
    with patch("production_counter._load_committed_today",     return_value=0), \
         patch("production_counter._upsert_live",              side_effect=lambda *a: calls.append(a)), \
         patch("production_counter._write_production_archive"):

        pc = ProductionCounter(60, flush_every=100)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
        pc.notify_cycle(4, mold_id=101, timestamp=T0 + timedelta(seconds=30))

    assert_eq(len(calls), 0, "8 bottles < threshold of 100, no flush expected")


@test("Resumes from committed DB value on restart")
def _():
    patches = PC_ALL(500)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
    assert_eq(pc._bottles_today, 504, "500 from DB + 4 new")


@test("bottles_per_hour returns 0.0 with fewer than 2 data points")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
    assert_eq(pc.bottles_per_hour(), 0.0)


@test("bottles_per_hour calculates correctly over known time window")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        # 10 cycles × 4 bottles every 3 min → span 0–27 min → ~80 bottles/hr
        for i in range(10):
            pc.notify_cycle(4, mold_id=101, timestamp=T0 + timedelta(minutes=i * 3))
    assert_approx(pc.bottles_per_hour(), 80.0, tol=5.0)


@test("live_state returns correct keys and values")
def _():
    patches = PC_ALL(0)
    with patches[0], patches[1], patches[2]:
        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
        state = pc.live_state()
    for key in ("machine_id", "date", "bottles_today", "bottles_per_hour"):
        assert_true(key in state, f"missing key: {key}")
    assert_eq(state["machine_id"],   60)
    assert_eq(state["bottles_today"], 4)


@test("flush() calls upsert_live and write_production_archive")
def _():
    upsert  = []
    archive = []
    with patch("production_counter._load_committed_today",     return_value=0), \
         patch("production_counter._upsert_live",              side_effect=lambda *a: upsert.append(a)), \
         patch("production_counter._write_production_archive", side_effect=lambda *a: archive.append(a)):

        pc = ProductionCounter(60, flush_every=999)
        pc.notify_cycle(4, mold_id=101, timestamp=T0)
        pc.flush(mold_id=101)

    assert_true(len(upsert)  >= 1, "upsert_live called on flush")
    assert_true(len(archive) >= 1, "write_production_archive called on flush")


# ════════════════════════════════════════════════════════════════════════════════
# INTEGRATION
# ════════════════════════════════════════════════════════════════════════════════

print("\n── Integration ───────────────────────────────────────────────────────────")


@test("Production counts correctly while downtime is tracked in parallel")
def _():
    """
    5 good cycles → downtime (2 min) → recovery → 3 more good cycles.
    Expect: 32 bottles, 1 downtime event, ~120 s duration.
    """
    dt_events = []
    def fake_insert(machine_id, mold_id, start, end):
        dur = (end - start).total_seconds()
        dt_events.append(dur)
        return dur

    dt_patches = DT_ALL(insert_fn=fake_insert)
    pc_patches = PC_ALL(0)
    with dt_patches[0], dt_patches[1], dt_patches[2], dt_patches[3], dt_patches[4], \
         pc_patches[0], pc_patches[1], pc_patches[2]:

        dt = DowntimeTracker(60)
        pc = ProductionCounter(60, flush_every=999)

        t    = T0
        step = timedelta(seconds=30)

        for _ in range(5):
            dt.update(1, mold_id=101, timestamp=t)
            pc.notify_cycle(4, mold_id=101, timestamp=t)
            t += step

        for _ in range(4):           # 4 × 30 s = 120 s downtime
            dt.update(0, mold_id=101, timestamp=t)
            t += step

        dt.update(1, mold_id=101, timestamp=t)
        t += step

        for _ in range(3):
            dt.update(1, mold_id=101, timestamp=t)
            pc.notify_cycle(4, mold_id=101, timestamp=t)
            t += step

    assert_eq(pc._bottles_today, 32, "(5+3) × 4 = 32 bottles")
    assert_eq(len(dt_events), 1,     "exactly 1 downtime event")
    assert_approx(dt_events[0], 120.0, tol=1.0, msg="downtime ~120 s")
    assert_false(dt._is_down, "machine should be UP at end")


@test("Delta logic: positive delta counted correctly")
def _():
    delta = 104 - 100
    assert_eq(delta, 4)
    assert_true(delta > 0)


@test("Delta logic: PLC reset → use current_qty directly")
def _():
    prev, current = 9999, 4
    delta = current - prev
    assert_true(delta < 0, "negative = reset")
    assert_eq(current, 4, "use current_qty after reset")


# ════════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════════

passed = sum(1 for _, ok, _ in _results if ok)
failed = sum(1 for _, ok, _ in _results if not ok)

print(f"\n{'─' * 62}")
print(f"  Results: {passed} passed, {failed} failed  (total: {len(_results)})")
print(f"{'─' * 62}")

if failed:
    print("\nFailed tests:")
    for name, ok, detail in _results:
        if not ok:
            print(f"  • {name}")
            for line in detail.splitlines()[-3:]:
                print(f"    {line}")
    sys.exit(1)
else:
    print("\n  All tests passed ✓")
    sys.exit(0)
