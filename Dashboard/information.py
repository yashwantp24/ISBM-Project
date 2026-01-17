import sqlite3
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
DB_NAME = os.path.join(BASE_DIR, "info.db")  
def get_connection():
    return sqlite3.connect(DB_NAME)


def create_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS machine (
        number INTEGER PRIMARY KEY,
        mold INTEGER,
        cyc_limit INTEGER
    )
    """)

    conn.commit()
    conn.close()


def add_machine(number, mold, cyc_limit):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO machine (number, mold, cyc_limit) VALUES (?, ?, ?)",
        (number, mold, cyc_limit)
    )

    conn.commit()
    conn.close()


def get_machine(number):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM machine WHERE number = ?",
        (number,)
    )

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_machines():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM machine")
    machines = cursor.fetchall()

    conn.close()
    return machines

def update_machine(number, mold, cyc_limit):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE machine SET mold = ?, cyc_limit = ? WHERE number = ?",
        (mold, cyc_limit, number)
    )

    conn.commit()
    conn.close()
