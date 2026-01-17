# collector.py
import csv
from datetime import datetime
import os
from pathlib import Path
import sys
import streamlit as st

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import MACHINES, OPC_SERVER_URL

CSV_FOLDER = "Streamlit Dashboard"
CSV_FILE = os.path.join(CSV_FOLDER, "production_data.csv")

os.makedirs(CSV_FOLDER, exist_ok=True)

client = OPCClient(OPC_SERVER_URL)

MACHINES_TO_LOG = [60]

@st.cache_data(ttl=60)
def get_total_production_for_all_machines():
    totals = {}

    for machine_id in MACHINES_TO_LOG:
        machine_data = client.read_machine(machine_id, MACHINES).get("Production Quantity")
        totals[machine_id] = (
            machine_data
            if machine_data else None
        )

    return totals

@st.cache_data(ttl=60)
def save_hourly_totals():
    totals = get_total_production_for_all_machines()
    timestamp = datetime.now().replace(minute=0, second=0, microsecond=0)

    write_header = not os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)

        if write_header:
            writer.writerow(["timestamp", "machine_id", "production"])

        for machine_id, production in totals.items():
            writer.writerow([
                timestamp.isoformat(),
                machine_id,
                production
            ])

    print("Saved totals at", timestamp)


if __name__ == "__main__":
    save_hourly_totals()


