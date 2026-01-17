# data.py

import time
import sys
import os
from opc_client import OPCClient
from tags import OPC_SERVER_URL, MACHINES
from db import insert_machine_row
from Dashboard import information
from cycle_logger import CycleLogger



client = OPCClient(OPC_SERVER_URL)
client.connect()

cycle_loggers = {
    60: CycleLogger(client, machine_id=60, tag_map=MACHINES)
}

try:
    while True:
        for m, logger in cycle_loggers.items():
            machine_info = information.get_machine(m)

            cycle_row = logger.poll()

            if cycle_row is None:
                continue  # cycle still running

            insert_machine_row(
                m,
                machine_info["mold"],
                cycle_row
            )

            print(f"[CYCLE SAVED] Machine {m}")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("Stopping collector...")

finally:
    client.disconnect()

