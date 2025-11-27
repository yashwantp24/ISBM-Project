# data.py

import time
from database.opc_client import OPCClient
from database.tags import OPC_SERVER_URL, MACHINES
from database.db import insert_machine_row

MOLD_ID = "M1"   # manually for now


client = OPCClient(OPC_SERVER_URL)
client.connect()

try:
    while True:
        machines_to_read = [1, 60]

        for m in machines_to_read:
            values = client.read_machine(m, MACHINES)

            if values is None:
                continue

            auto_cycle = values.get("Auto Cycle")
            blow_time = values.get("Blow Time")

            # Remove metadata from dict copy
            temp = values.copy()
            del temp["machine_id"]
            del temp["timestamp"]

            # write row into DB
            insert_machine_row(
                m,
                MOLD_ID,
                auto_cycle,
                blow_time,
                temp
            )

            print(f"[SAVED] Machine {m}")

        time.sleep(20)

except KeyboardInterrupt:
    print("Stopping collector...")

finally:
    client.disconnect()
