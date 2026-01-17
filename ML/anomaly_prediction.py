# realtime_anomaly_predictor.py
"""
Run this script continuously alongside data.py to perform real-time anomaly detection
and store predictions in the database for display in Streamlit
"""

import time
import sys
import os
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.opc_client import OPCClient
from database.tags import OPC_SERVER_URL, MACHINES
from Dashboard import information
from database.cycle_logger import CycleLogger
from database.ml import ISBMDefectDetector
from database.db import get_connection

# Database functions for anomaly predictions
def create_anomaly_table():
    """Create table to store anomaly predictions"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS anomaly_predictions (
            id SERIAL PRIMARY KEY,
            machine_id INT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            anomaly_score FLOAT NOT NULL,
            alert_level VARCHAR(10) NOT NULL,
            is_defect BOOLEAN NOT NULL,
            cycle_data JSONB
        );
        
        CREATE INDEX IF NOT EXISTS idx_anomaly_machine_time 
        ON anomaly_predictions(machine_id, timestamp DESC);
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("Anomaly predictions table created/verified")


def insert_anomaly_prediction(machine_id, timestamp, anomaly_score, alert_level, is_defect, cycle_data):
    """Insert anomaly prediction into database"""
    import json
    from datetime import datetime
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Clean cycle_data to make it JSON serializable
    clean_cycle_data = None
    if cycle_data:
        clean_cycle_data = {}
        for key, value in cycle_data.items():
            # Convert datetime to ISO string
            if isinstance(value, datetime):
                clean_cycle_data[key] = value.isoformat()
            # Convert None, NaN, or other non-serializable to null
            elif value is None or (isinstance(value, float) and (value != value)):  # NaN check
                clean_cycle_data[key] = None
            else:
                clean_cycle_data[key] = value
    
    cur.execute("""
        INSERT INTO anomaly_predictions (
            machine_id,
            timestamp,
            anomaly_score,
            alert_level,
            is_defect,
            cycle_data
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        machine_id,
        timestamp,
        anomaly_score,
        alert_level,
        is_defect,
        json.dumps(clean_cycle_data) if clean_cycle_data else None
    ))
    
    conn.commit()
    cur.close()
    conn.close()


def main():
    """Main prediction loop"""
    
    # Create anomaly table if it doesn't exist
    create_anomaly_table()
    
    # Machine to monitor (change as needed)
    machine_id = 60
    
    # Load the trained model
    print(f"Loading trained model for Machine {machine_id}...")
    try:
        detector = ISBMDefectDetector()
        detector.load_model(f"models/machine_{machine_id}_model.pkl")
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        print("Please ensure the model file exists at models/machine_{machine_id}_model.pkl")
        return
    
    # Initialize OPC client and cycle logger
    print(f"Connecting to OPC server...")
    client = OPCClient(OPC_SERVER_URL)
    client.connect()
    print("✓ Connected to OPC server")
    
    logger = CycleLogger(client, machine_id=machine_id, tag_map=MACHINES)
    print(f"\n{'='*60}")
    print(f"Starting real-time anomaly detection for Machine {machine_id}")
    print(f"{'='*60}\n")
    
    prediction_count = 0
    defect_count = 0
    
    try:
        while True:
            # Poll for completed cycle
            cycle_data = logger.poll()
            
            if cycle_data is None:
                # Cycle still running, wait a bit
                time.sleep(0.5)
                continue
            
            # We have a completed cycle - make prediction
            timestamp = cycle_data.get("timestamp")
            
            # Ensure timestamp is a datetime object
            if isinstance(timestamp, str):
                from dateutil import parser
                timestamp = parser.parse(timestamp)
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.now()
            
            try:
                # Get prediction from model
                result = detector.predict_cycle(cycle_data)
                
                # Get raw anomaly score (negative value from Isolation Forest)
                raw_score = result['anomaly_score']
                anomaly_score = abs(raw_score)
                
                # Determine alert level and defect based on score thresholds
                # Lower (more negative) scores = more anomalous
                # Convert to percentage scale where lower scores = higher defect probability
                if raw_score >= -0.5:  # Less anomalous (0-4% defect chance)
                    alert_level = "LOW"
                    is_defect = False
                elif raw_score >= -0.6:  # Moderately anomalous (4-6% defect chance)
                    alert_level = "MEDIUM"
                    is_defect = False
                else:  # Highly anomalous (6%+ defect chance)
                    alert_level = "HIGH"
                    is_defect = True
                
                prediction_count += 1
                if is_defect:
                    defect_count += 1
                
                # Store prediction in database
                insert_anomaly_prediction(
                    machine_id=machine_id,
                    timestamp=timestamp,
                    anomaly_score=anomaly_score,
                    alert_level=alert_level,
                    is_defect=is_defect,
                    cycle_data=cycle_data
                )
                
                # Print status with percentage
                defect_pct = abs(raw_score) * 100
                status_symbol = "🔴" if is_defect else "🟡" if alert_level == "MEDIUM" else "🟢"
                print(f"{status_symbol} [{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Prediction #{prediction_count}")
                print(f"   Defect Probability: {defect_pct:.2f}% | Alert: {alert_level} | Defect: {is_defect}")
                
                if is_defect:
                    print(f"   ⚠️  DEFECT DETECTED - Total defects: {defect_count}")
                
                print()
                
            except Exception as e:
                print(f"✗ Prediction error: {e}")
                continue
            
            # Small delay before next poll
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\nStopping anomaly predictor...")
        print(f"Total predictions: {prediction_count}")
        print(f"Total defects detected: {defect_count}")
    
    finally:
        client.disconnect()
        print("Disconnected from OPC server")


if __name__ == "__main__":
    main()