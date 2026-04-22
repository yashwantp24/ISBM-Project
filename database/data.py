# data.py

import time
from opc_client import OPCClient
from tags import OPC_SERVER_URL, MACHINES
from db import insert_machine_row
from Dashboard import information
from cycle_logger import CycleLogger


# ── Configuration ─────────────────────────────────────────────
MACHINE_IDS = [1, 22, 23, 24, 25, 26, 59, 60, 61, 62, 68]
SUBSCRIPTION_INTERVAL_MS = 250   # server pushes changes this often
POLL_INTERVAL_SEC = 0.5          # how often we check cache for cycles
WARMUP_SEC = 3                   # time to let subscriptions populate cache


# ── 1. Connect & Subscribe ───────────────────────────────────
client = OPCClient(OPC_SERVER_URL)
client.connect()
client.subscribe_machines(MACHINE_IDS, MACHINES,
                          interval_ms=SUBSCRIPTION_INTERVAL_MS)

# Let subscriptions fill the cache before starting cycle detection
print(f"Warming up cache ({WARMUP_SEC}s)...")
time.sleep(WARMUP_SEC)

# Verify cache population
for mid in MACHINE_IDS:
    with client.lock:
        count = len([k for k in client.cache.get(mid, {})
                     if not k.startswith("_")])
    print(f"  Machine {mid}: {count} tags cached")


# ── 2. Cycle Loggers (unchanged) ─────────────────────────────
cycle_loggers = {mid: CycleLogger(client, mid, MACHINES)
                 for mid in MACHINE_IDS}


# ── 3. Main Loop ─────────────────────────────────────────────
print("\nStarting cycle detection loop...")

try:
    while True:
        for m, logger in cycle_loggers.items():
            machine_info = information.get_machine(m)

            cycle_row = logger.poll()

            if cycle_row is None:
                continue  # cycle still running or machine idle

            insert_machine_row(
                m,
                machine_info["mold"],
                cycle_row
            )

            print(f"[CYCLE SAVED] Machine {m}")

        time.sleep(POLL_INTERVAL_SEC)

except KeyboardInterrupt:
    print("\nStopping collector...")

finally:
    client.disconnect()