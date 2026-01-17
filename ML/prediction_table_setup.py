# setup_anomaly_table.py
"""
Run this once to create the anomaly_predictions table in your database
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.db import get_connection

def create_anomaly_table():
    """Create table to store anomaly predictions"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Create the anomaly predictions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_predictions (
                id SERIAL PRIMARY KEY,
                machine_id INT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                anomaly_score FLOAT NOT NULL,
                alert_level VARCHAR(10) NOT NULL,
                is_defect BOOLEAN NOT NULL,
                cycle_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_anomaly_machine_time 
            ON anomaly_predictions(machine_id, timestamp DESC);
            
            CREATE INDEX IF NOT EXISTS idx_anomaly_defect
            ON anomaly_predictions(machine_id, is_defect, timestamp DESC);
        """)
        
        conn.commit()
        print("✓ Anomaly predictions table created successfully")
        print("✓ Indexes created for optimal query performance")
        
        # Show table info
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'anomaly_predictions'
            ORDER BY ordinal_position;
        """)
        
        print("\nTable structure:")
        print("-" * 40)
        for row in cur.fetchall():
            print(f"  {row[0]:<20} {row[1]}")
        print("-" * 40)
        
    except Exception as e:
        print(f"✗ Error creating table: {e}")
        conn.rollback()
    
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print("Setting up anomaly predictions table...\n")
    create_anomaly_table()
    print("\nSetup complete! You can now run realtime_anomaly_predictor.py")