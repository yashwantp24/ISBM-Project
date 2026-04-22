import os
import sys
import time
from pathlib import Path

import certifi
import pip_system_certs

os.environ["SSL_CERT_FILE"] = certifi.where()

from twilio.rest import Client

# root path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL
from Notifications.notifs import check_notifications

client = OPCClient(OPC_SERVER_URL)

# Credentials must be supplied via environment variables.
# Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM, TWILIO_TO before running.
# See http://twil.io/secure for rotation guidance.
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_from = os.environ.get("TWILIO_FROM", "whatsapp:+14155238886")
twilio_to   = os.environ.get("TWILIO_TO")

if not (account_sid and auth_token and twilio_to):
    sys.exit(
        "Missing Twilio configuration. Set TWILIO_ACCOUNT_SID, "
        "TWILIO_AUTH_TOKEN, and TWILIO_TO environment variables before running."
    )

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
                from_=twilio_from,
                to=twilio_to,
            )
            print("Sent:", message.sid)

    time.sleep(20)