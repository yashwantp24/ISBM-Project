import os
import certifi
import pip_system_certs

os.environ["SSL_CERT_FILE"] = certifi.where()

import os
from twilio.rest import Client
import sys
from pathlib import Path

# root path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL
from Notifications.notifs import check_notifications
import time

client = OPCClient(OPC_SERVER_URL)

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = 
auth_token =
client_w = Client(account_sid, auth_token)


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

        alerts,alerts_tag = check_notifications(m, values, cycle_limits)

        if alerts:
            message = client_w.messages.create(
                body=str(alerts),
                from_='whatsapp:+14155238886',
                to='whatsapp:+12176932291'
            )
            print("Sent:", message.sid)

    time.sleep(20)