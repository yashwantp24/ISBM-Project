# db.py

import psycopg2
import json
from datetime import datetime

def get_connection():
    return psycopg2.connect(
        host="localhost",
        dbname="postgres",
        user="postgres",
        password="admin",
        port=54321
    )

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

