# tracking_runner.py
"""
Standalone downtime + production tracking process.
Run SEPARATELY alongside data.py — does not modify it in any way.

Now uses OPC UA subscriptions instead of polling reads.
client.read_machine() reads from an in-memory cache updated
by the OPC server via push notifications.

Usage:
    python tracking_runner.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import OPC_SERVER_URL, MACHINES
from Dashboard import information
from downtime_tracker import DowntimeTracker
from production_counter import ProductionCounter


# ─── Configuration ────────────────────────────────────────────────────────────

TRACKED_MACHINES = [1, 22, 23, 24, 25, 26, 57, 58, 59, 60, 61, 62, 68]

POLL_INTERVAL = 0.5             # seconds — how often we check cache
SUBSCRIPTION_INTERVAL_MS = 250  # OPC server push interval
WARMUP_SEC = 3                  # let subscriptions fill cache before starting


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    # 1. Connect & subscribe
    client = OPCClient(OPC_SERVER_URL)
    client.connect()
    client.subscribe_machines(
        TRACKED_MACHINES, MACHINES,
        interval_ms=SUBSCRIPTION_INTERVAL_MS,
    )

    # 2. Warm up cache
    print(f"Warming up subscription cache ({WARMUP_SEC}s)...")
    time.sleep(WARMUP_SEC)

    for mid in TRACKED_MACHINES:
        with client.lock:
            count = len([k for k in client.cache.get(mid, {})
                         if not k.startswith("_")])
        print(f"  Machine {mid}: {count} tags cached")

    # 3. Initialize trackers
    downtime_trackers   = {m: DowntimeTracker(m)   for m in TRACKED_MACHINES}
    production_counters = {m: ProductionCounter(m) for m in TRACKED_MACHINES}

    # ── Sync daily_archive with live state on startup ─────────────────────────
    print("Syncing daily_archive with live state...")
    for m in TRACKED_MACHINES:
        try:
            machine_info = information.get_machine(m)
            mold_id = machine_info.get("mold") if machine_info else 0
            dt = downtime_trackers[m].live_state()
            prod = production_counters[m].live_state()

            from downtime_tracker import (
                _write_daily_archive, _load_committed_shift, _count_events_today,
            )
            from datetime import date as _date
            today = _date.today()

            s1_sec, s1_ev = _load_committed_shift(m, today, 1)
            s2_sec, s2_ev = _load_committed_shift(m, today, 2)
            s3_sec, s3_ev = _load_committed_shift(m, today, 3)

            _write_daily_archive(
                m, mold_id, today,
                total_downtime_sec=dt["total_downtime_sec"],
                event_count=_count_events_today(m, today),
                shift_1_sec=s1_sec, shift_1_ev=s1_ev,
                shift_2_sec=s2_sec, shift_2_ev=s2_ev,
                shift_3_sec=s3_sec, shift_3_ev=s3_ev,
            )

            from production_counter import _write_production_archive
            _write_production_archive(m, mold_id, today, prod["bottles_today"])

            print(f"  M{m}: archive synced (bottles={prod['bottles_today']}, dt={dt['total_downtime_min']:.1f}min)")
        except Exception as e:
            print(f"  M{m}: archive sync failed: {e}")

    # Store previous PLC production counter value
    prev_prod_qty = {m: None for m in TRACKED_MACHINES}

    # Cache machine info — avoids SQLite reads every poll cycle
    machine_info_cache = {}
    for m in TRACKED_MACHINES:
        machine_info_cache[m] = information.get_machine(m) or {"mold": 0}

    print("Tracking runner started. Press Ctrl+C to stop.")

    try:
        while True:
            loop_start = time.monotonic()
            now = datetime.now()

            for m in TRACKED_MACHINES:
                try:
                    # Reads from subscription cache — zero network calls
                    raw = client.read_machine(m, MACHINES)
                    if raw is None:
                        continue

                    mold_id  = machine_info_cache[m].get("mold")
                    auto     = raw.get("Auto Cycle")
                    prod_qty = raw.get("Production Quantity")
                    ts       = raw.get("timestamp", now)

                    # ── Downtime tracking (safe guard against None) ────────────
                    if auto is not None:
                        downtime_trackers[m].update(auto, mold_id, ts)

                    # ── Production counting using PURE PLC delta ───────────────
                    if prod_qty is not None:
                        current_qty = int(prod_qty)

                        # First read → establish baseline only
                        if prev_prod_qty[m] is None:
                            prev_prod_qty[m] = current_qty

                        else:
                            delta = current_qty - prev_prod_qty[m]

                            if delta > 0:
                                production_counters[m].notify_cycle(
                                    delta, mold_id, ts
                                )

                            # If PLC counter reset (shift change / operator clear)
                            elif delta < 0:
                                prev_prod_qty[m] = current_qty
                                continue

                            prev_prod_qty[m] = current_qty

                    # ── Console output ─────────────────────────────────────────
                    dt   = downtime_trackers[m].live_state()
                    prod = production_counters[m].live_state()
                    status = "DOWN" if dt["is_down"] else "UP  "

                    print(
                        f"[{ts:%H:%M:%S}] M{m} Mold {mold_id} {status} | "
                        f"DT: {dt['total_downtime_min']:6.1f} min | "
                        f"Bottles: {prod['bottles_today']:5d} | "
                        f"Rate: {prod['bottles_per_hour']:5.0f} /hr"
                    )
                except Exception as e:
                    print(f"[{now:%H:%M:%S}] M{m} ERROR: {e}")

            # Smart sleep — only wait if the loop was faster than POLL_INTERVAL
            loop_duration = time.monotonic() - loop_start
            remaining = POLL_INTERVAL - loop_duration
            if remaining > 0:
                time.sleep(remaining)
            else:
                print(f"  ⚠ Loop took {loop_duration:.1f}s (target: {POLL_INTERVAL}s)")

    except KeyboardInterrupt:
        print("\nShutting down – flushing state to DB…")

    finally:
        for m in TRACKED_MACHINES:
            mold_id = machine_info_cache[m].get("mold")
            downtime_trackers[m].flush(mold_id)
            production_counters[m].flush(mold_id)

        client.disconnect()
        print("Done.")


if __name__ == "__main__":
    main()