# db.py

import json
from datetime import datetime

from database.connection import get_conn


def get_connection():
    """Back-compat alias — prefer `database.connection.get_conn`."""
    return get_conn()

def insert_machine_row(machine_id, mold_id, data_dict):
    conn = get_connection()
    cur = conn.cursor()

    # Extract timestamp from data_dict
    ts = data_dict.pop("timestamp")  # ISO string

    cur.execute("""
        INSERT INTO machine_data (
            machine_id,
            timestamp,
            mold_id,
            data
        )
        VALUES (%s, %s, %s, %s)
    """, (
        machine_id,
        ts,               # ISO timestamp
        mold_id,
        json.dumps(data_dict)
    ))

    conn.commit()
    cur.close()
    conn.close()

