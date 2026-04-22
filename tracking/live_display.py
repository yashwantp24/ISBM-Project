# live_display.py
"""
Live terminal display for downtime and production counters.
Connects to the real OPC server and PostgreSQL database.
Refreshes in place every second — no scrolling output.

Run with:
    python live_display.py

Press Ctrl+C to stop.
"""

import sys
import os
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
import time
from datetime import datetime, timedelta

from database.opc_client import OPCClient
from database.tags import OPC_SERVER_URL, MACHINES
from Dashboard import information
from downtime_tracker import DowntimeTracker
from production_counter import ProductionCounter


# ─── Configuration ────────────────────────────────────────────────────────────

TRACKED_MACHINES = [60]
POLL_INTERVAL    = 0.5
DISPLAY_INTERVAL = 1.0

SHIFT_NAMES = {1: "Shift 1  00:00–08:00", 2: "Shift 2  08:00–16:00", 3: "Shift 3  16:00–00:00"}


# ─── Terminal helpers ──────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def bar(value: float, total: float, width: int = 20, fill="█", empty="░") -> str:
    if total <= 0:
        ratio = 0.0
    else:
        ratio = min(1.0, value / total)
    filled = int(ratio * width)
    return fill * filled + empty * (width - filled)


def fmt_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{s}s"


def status_badge(is_down: bool) -> str:
    return "[ DOWN ]" if is_down else "[  UP  ]"


# ─── Screen renderer ───────────────────────────────────────────────────────────

def render(machine_states, started_at, poll_count, last_error):
    now    = datetime.now()
    uptime = fmt_duration((now - started_at).total_seconds())

    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════════╗")
    lines.append(f"║  LIVE TRACKING DISPLAY          {now:%Y-%m-%d  %H:%M:%S}           ║")
    lines.append(f"║  Uptime: {uptime:<12s}  Polls: {poll_count:<8d}                    ║")
    lines.append("╠══════════════════════════════════════════════════════════════════╣")

    for m, state in machine_states.items():
        dt   = state["dt"]
        prod = state["prod"]
        raw  = state["raw"]

        is_down  = dt["is_down"]
        badge    = status_badge(is_down)
        mold_id  = dt.get("mold_id") or "—"
        date_str = dt["date"]
        shift_no = dt["shift"]
        shift_lbl = SHIFT_NAMES.get(shift_no, f"Shift {shift_no}")

        # ── Production ─────────────────────────────────────────────────────────
        bottles = prod["bottles_today"]
        rate    = prod["bottles_per_hour"]

        # ── Daily downtime ─────────────────────────────────────────────────────
        dt_total_sec = dt["total_downtime_sec"]
        dt_current   = dt["current_event_sec"]
        dt_min       = dt["total_downtime_min"]

        # ── Shift downtime (NEW) ───────────────────────────────────────────────
        shift_sec    = dt["shift_downtime_sec"]
        shift_min    = dt["shift_downtime_min"]
        shift_events = dt["shift_event_count"]

        # Availability (vs elapsed time today)
        elapsed_today = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        avail_pct = max(0.0, (elapsed_today - dt_total_sec) / elapsed_today * 100) if elapsed_today > 0 else 100.0

        # ── Raw tag values ─────────────────────────────────────────────────────
        auto_val  = raw.get("Auto Cycle", "—")
        cycle_t   = raw.get("Cycle Time")
        blow_t    = raw.get("Blow Time")
        prod_qty  = raw.get("Production Quantity")
        cycle_str = f"{cycle_t:.2f}s" if isinstance(cycle_t,  (int, float)) else "—"
        blow_str  = f"{blow_t:.2f}s"  if isinstance(blow_t,   (int, float)) else "—"
        prod_str  = f"{int(prod_qty)}" if isinstance(prod_qty, (int, float)) else "—"

        lines.append(f"║                                                                  ║")
        lines.append(f"║  Machine {m:<4d}  Mold {str(mold_id):<6s}  {date_str}           {badge}  ║")
        lines.append(f"║  {shift_lbl:<64s}  ║")
        lines.append(f"║  {'─' * 64}  ║")

        # Production block
        lines.append(f"║  PRODUCTION                                                      ║")
        lines.append(f"║    Bottles today   : {bottles:>6d}                                    ║")
        lines.append(f"║    Rate (rolling)  : {rate:>6.0f} bottles / hr                        ║")
        lines.append(f"║                                                                  ║")

        # Daily downtime block
        dt_open_str = f"  (current: {fmt_duration(dt_current)})" if is_down else ""
        lines.append(f"║  DOWNTIME — DAY                                                  ║")
        lines.append(f"║    Total today     : {fmt_duration(dt_total_sec):<12s}{dt_open_str:<26s}  ║")
        lines.append(f"║    Total (minutes) : {dt_min:>6.1f} min                               ║")
        lines.append(f"║    Availability    : {avail_pct:>5.1f}%  {bar(elapsed_today - dt_total_sec, elapsed_today, 28)}  ║")
        lines.append(f"║                                                                  ║")

        # Shift downtime block (NEW)
        lines.append(f"║  DOWNTIME — {shift_lbl:<52s}  ║")
        lines.append(f"║    Shift total     : {fmt_duration(shift_sec):<12s}  ({shift_min:.1f} min)              ║")
        lines.append(f"║    Events this shift: {shift_events:<4d}                                    ║")
        lines.append(f"║                                                                  ║")

        # Raw OPC values
        lines.append(f"║  OPC TAGS (last read)                                            ║")
        lines.append(f"║    Auto Cycle      : {str(auto_val):<6}   Cycle Time : {cycle_str:<8}          ║")
        lines.append(f"║    Blow Time       : {blow_str:<8}  Prod Qty   : {prod_str:<8}          ║")

        if is_down and dt["downtime_start"]:
            started = datetime.fromisoformat(dt["downtime_start"])
            lines.append(f"║                                                                  ║")
            lines.append(f"║  ⚠  Machine DOWN since {started:%H:%M:%S}  ({fmt_duration(dt_current)} ago)           ║")

        lines.append("╠══════════════════════════════════════════════════════════════════╣")

    if last_error:
        err_short = last_error[:64]
        lines.append(f"║  ⚠  Last error: {err_short:<52s}  ║")
    else:
        lines.append(f"║  ✓  All systems OK                                               ║")
    lines.append(f"║  Refreshes every {DISPLAY_INTERVAL:.0f}s  |  Press Ctrl+C to quit               ║")
    lines.append("╚══════════════════════════════════════════════════════════════════╝")

    clear()
    print("\n".join(lines))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to OPC server...")
    client = OPCClient(OPC_SERVER_URL)

    print("Loading trackers from DB (resuming today's data)...")
    downtime_trackers   = {m: DowntimeTracker(m)   for m in TRACKED_MACHINES}
    production_counters = {m: ProductionCounter(m) for m in TRACKED_MACHINES}

    prev_prod_qty   = {m: None for m in TRACKED_MACHINES}
    prev_cycle_time = {m: None for m in TRACKED_MACHINES}

    machine_states = {
        m: {
            "dt":   downtime_trackers[m].live_state(),
            "prod": production_counters[m].live_state(),
            "raw":  {},
        }
        for m in TRACKED_MACHINES
    }

    started_at   = datetime.now()
    poll_count   = 0
    last_error   = ""
    last_display = 0.0

    try:
        while True:
            now = datetime.now()

            for m in TRACKED_MACHINES:
                try:
                    raw = client.read_machine(m, MACHINES)
                    if raw is None:
                        continue

                    mold_id    = information.get_machine(m)["mold"]
                    auto       = raw.get("Auto Cycle")
                    cycle_time = raw.get("Cycle Time")
                    blow_time  = raw.get("Blow Time")
                    prod_qty   = raw.get("Production Quantity")
                    ts         = raw.get("timestamp", now)

                    downtime_trackers[m].update(auto, mold_id, ts)

                    cycle_complete = (
                        auto == 1
                        and blow_time is not None
                        and blow_time > 2
                        and cycle_time is not None
                        and prev_cycle_time[m] is not None
                        and cycle_time != prev_cycle_time[m]
                    )
                    if cycle_complete and prod_qty is not None and prev_prod_qty[m] is not None:
                        delta = int(prod_qty) - int(prev_prod_qty[m])
                        if delta > 0:
                            production_counters[m].notify_cycle(delta, mold_id, ts)
                        elif delta < 0:
                            production_counters[m].notify_cycle(int(prod_qty), mold_id, ts)

                    prev_cycle_time[m] = cycle_time
                    if prod_qty is not None:
                        prev_prod_qty[m] = prod_qty

                    machine_states[m]["dt"]   = downtime_trackers[m].live_state()
                    machine_states[m]["prod"]  = production_counters[m].live_state()
                    machine_states[m]["raw"]   = raw
                    last_error = ""

                except Exception as e:
                    last_error = f"M{m}: {e}"

            poll_count += 1

            if time.monotonic() - last_display >= DISPLAY_INTERVAL:
                render(machine_states, started_at, poll_count, last_error)
                last_display = time.monotonic()

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        clear()
        print("\nShutting down — flushing state to DB...")

    finally:
        for m in TRACKED_MACHINES:
            try:
                mold_id = information.get_machine(m)["mold"]
                downtime_trackers[m].flush(mold_id)
                production_counters[m].flush(mold_id)
            except Exception as e:
                print(f"  Warning: flush failed for M{m}: {e}")
        client.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()
