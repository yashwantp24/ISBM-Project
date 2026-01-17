# train_model.py
"""
Train the Isolation Forest model on historical data
Run this FIRST before testing
"""

import os
from ml import ISBMDefectDetector
from datetime import datetime

# Create models directory
os.makedirs("models", exist_ok=True)

print("="*80)
print("ISBM DEFECT DETECTION - MODEL TRAINING")
print("="*80)
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
MACHINE_ID = 60          # Change this to your machine ID
DAYS_BACK = 30           # How many days of historical data to use
CONTAMINATION = 0.05     # Expected defect rate (5%)
MODEL_PATH = f"models/machine_{MACHINE_ID}_model.pkl"

print("Configuration:")
print(f"  Machine ID: {MACHINE_ID}")
print(f"  Training period: Last {DAYS_BACK} days")
print(f"  Expected defect rate: {CONTAMINATION*100}%")
print(f"  Model will be saved to: {MODEL_PATH}")
print()

# Step 1: Initialize detector
print("Step 1: Initializing detector...")
detector = ISBMDefectDetector(contamination=CONTAMINATION)
print("✓ Detector initialized")
print()

# Step 2: Check database connection
print("Step 2: Testing database connection...")
try:
    conn = detector.get_db_connection()
    cursor = conn.cursor()
    
    # Check if we have data
    cursor.execute("""
        SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
        FROM machine_data 
        WHERE machine_id = %s
    """, (MACHINE_ID,))
    
    count, min_date, max_date = cursor.fetchone()
    cursor.close()
    conn.close()
    
    print(f"✓ Database connected successfully")
    print(f"  Total records for Machine {MACHINE_ID}: {count}")
    print(f"  Date range: {min_date} to {max_date}")
    print()
    
    if count < 10:
        print("⚠️  ERROR: Not enough data!")
        print(f"   Found: {count} records")
        print(f"   Need: At least 10 records (preferably 100+)")
        print()
        print("Solutions:")
        print("  1. Let data.py run longer to collect more data")
        print("  2. Check if machine_id=60 is correct")
        print("  3. Verify data.py is actually saving to database")
        exit(1)
    
    if count < 100:
        print(f"⚠️  WARNING: Only {count} records found")
        print("   Model will work better with 100+ records")
        print("   Consider collecting more data for better accuracy")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Training cancelled")
            exit(0)

except Exception as e:
    print(f"✗ Database connection failed: {e}")
    print()
    print("Check:")
    print("  1. Is PostgreSQL running?")
    print("  2. Database credentials correct in isbm_defect_detector.py?")
    print("  3. Does machine_data table exist?")
    exit(1)

# Step 3: Train the model
print("Step 3: Training model...")
print("-" * 80)

try:
    df_train, predictions, scores = detector.train(
        machine_id=MACHINE_ID,
        days_back=DAYS_BACK,
        mold_id=None  # Use data from all molds
    )
    
    print()
    print("✓ Training completed successfully!")
    
except Exception as e:
    print(f"\n✗ Training failed: {e}")
    print()
    import traceback
    traceback.print_exc()
    exit(1)

# Step 4: Analyze anomalies
print()
print("Step 4: Analyzing anomalies...")
print("-" * 80)

top_features = detector.analyze_anomalies(df_train, predictions, scores, top_n=15)

# Step 5: Save the model
print()
print("Step 5: Saving model...")
detector.save_model(MODEL_PATH)

# Step 6: Verify model can be loaded
print()
print("Step 6: Verifying saved model...")
try:
    test_detector = ISBMDefectDetector()
    test_detector.load_model(MODEL_PATH)
    print("✓ Model verified successfully!")
except Exception as e:
    print(f"✗ Model verification failed: {e}")
    exit(1)

# Summary
print()
print("="*80)
print("TRAINING COMPLETE!")
print("="*80)
print(f"Model saved to: {MODEL_PATH}")
print(f"Training samples: {len(df_train)}")
print(f"Features used: {len(detector.feature_names)}")
print(f"Anomalies detected: {(predictions == -1).sum()} ({(predictions == -1).sum()/len(predictions)*100:.1f}%)")
print()
print("Next steps:")
print("  1. Run 'python test_model.py' to test predictions")
print("  2. Integrate with data.py for real-time detection")
print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)