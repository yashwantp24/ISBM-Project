import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL
from Notifications.notifs import check_notifications
import time

client = OPCClient(OPC_SERVER_URL)

# Cycle limits as Python dictionary
cycle_limits = {
    "1": 1,
    "60": 1
}

MACHINE_LIST = [60]

while True:
    print("----New Alert----")
    for m in MACHINE_LIST:
        
        values = client.read_machine(m, MACHINES)
        
        
        if not values:
            continue


            
        # check alarms
        alerts = check_notifications(m, values, cycle_limits)

        for a in alerts:
            
            print("ALERT:", a)

    time.sleep(20)