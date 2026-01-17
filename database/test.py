from opc_client import OPCClient
from tags import OPC_SERVER_URL, MACHINES
from cycle_logger import CycleLogger
import time

client = OPCClient(OPC_SERVER_URL)
client.connect()

logger = CycleLogger(client, machine_id=60, tag_map=MACHINES)

try:
    while True:
        cycle_data = logger.poll()

        if cycle_data:
            print("CYCLE COMPLETE")
            for k, v in cycle_data.items():
                print(f"{k}: {v}")
            print("-" * 50)

        time.sleep(0.5)  # polling interval

except KeyboardInterrupt:
    print("Stopping...")

finally:
    client.disconnect()

