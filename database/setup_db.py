# setup_db.py

from db import get_connection


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS machine_data (
            id SERIAL PRIMARY KEY,
            machine_id INT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            mold_id INT,
            
            
            -- all other tags stored inside JSON
            data JSONB
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Machine data table created successfully")


if __name__ == "__main__":
    create_tables()
