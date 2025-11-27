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


def insert_machine_row(machine_id, mold_id, auto_cycle, blow_time, data_dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO machine_data (
            machine_id, timestamp, mold_id, auto_cycle, blow_time, data
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        machine_id,
        datetime.now(),
        mold_id,
        auto_cycle,
        blow_time,
        json.dumps(data_dict)
    ))

    conn.commit()
    cur.close()
    conn.close()
