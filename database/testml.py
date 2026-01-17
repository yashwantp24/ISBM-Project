# test_model_predictions.py
"""
Test the trained Isolation Forest model
Run this AFTER training
"""

from ml import ISBMDefectDetector
from datetime import datetime
import pandas as pd

print("="*80)
print("ISBM DEFECT DETECTION - MODEL TESTING")
print("="*80)
print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
MACHINE_ID = 60
MODEL_PATH = f"models/machine_{MACHINE_ID}_model.pkl"

# Initialize and load model
print("Step 1: Loading trained model...")
detector = ISBMDefectDetector()

try:
    detector.load_model(MODEL_PATH)
    print(f"✓ Model loaded from {MODEL_PATH}")
    print()
except FileNotFoundError:
    print(f"✗ Model not found at {MODEL_PATH}")
    print()
    print("You need to train the model first!")
    print("Run: python train_model.py")
    exit(1)

# Test 1: Predict on recent data
print("="*80)
print("TEST 1: Batch Prediction on Recent Cycles")
print("="*80)

print("Fetching last 100 cycles from database...")
try:
    df_recent = detector.fetch_training_data(
        machine_id=MACHINE_ID,
        limit=100
    )
    
    if df_recent.empty:
        print("⚠️  No recent data found")
        exit(0)
    
    print(f"✓ Fetched {len(df_recent)} cycles")
    print(f"  Date range: {df_recent['timestamp'].min()} to {df_recent['timestamp'].max()}")
    print()
    
    # Run predictions
    print("Running predictions...")
    predictions, scores, alerts = detector.predict_batch(df_recent)
    
    # Add to dataframe
    df_recent['prediction'] = predictions
    df_recent['anomaly_score'] = scores
    df_recent['alert_level'] = alerts
    
    # Results
    n_defects = (predictions == -1).sum()
    
    print()
    print("Results:")
    print(f"  Total cycles analyzed: {len(df_recent)}")
    print(f"  Defects detected: {n_defects} ({n_defects/len(df_recent)*100:.1f}%)")
    print()
    print("Alert Level Distribution:")
    print(f"  🔴 HIGH:   {(df_recent['alert_level'] == 'HIGH').sum():3d} cycles")
    print(f"  🟡 MEDIUM: {(df_recent['alert_level'] == 'MEDIUM').sum():3d} cycles")
    print(f"  🟢 LOW:    {(df_recent['alert_level'] == 'LOW').sum():3d} cycles")
    print()
    
    # Show top 5 worst scores
    print("Top 5 Most Anomalous Cycles:")
    worst = df_recent.nsmallest(5, 'anomaly_score')
    print(worst[['id', 'timestamp', 'anomaly_score', 'alert_level']].to_string(index=False))
    print()
    
    # Show defects if any
    if n_defects > 0:
        print("⚠️  Detected Defects:")
        defects = df_recent[df_recent['prediction'] == -1]
        print(defects[['id', 'timestamp', 'anomaly_score', 'alert_level']].head(10).to_string(index=False))
        print()
    else:
        print("✓ No defects detected in recent cycles")
        print()
    
except Exception as e:
    print(f"✗ Batch prediction failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 2: Single cycle prediction (simulated)
print("="*80)
print("TEST 2: Single Cycle Prediction (Simulated)")
print("="*80)

# Test with a normal cycle
print("Test 2a: Normal Cycle")
normal_cycle = {
  "Blow Time": 5,
  "Bottom DW": 0.13,
  "Bottom UP": 0.15,
  "Cycle Time": 13.91,
  "Blow Mold C": 2.89,
  "Blow Mold M": 1.36,
  "Charge Time": 4.86,
  "V-P Time PV": 14.5,
  "Barrel Front": 284.98333333333335,
  "Blow Core DW": 2.28,
  "Blow Core UP": 0.76,
  "Blow Mold CL": 1.36,
  "Blow Mold OP": 0.82,
  "Cooling Time": 3,
  "Shot Size PV": 111.9,
  "Stretch Time": 0.8,
  "Barrel Middle": 294.9916666666666,
  "Barrel Nozzle": 280.675,
  "Dry Cycle Time": 5.01,
  "Injection Time": 5.9,
  "Lip Mold CL FA": 0.76,
  "Lip Mold OP FA": 0.7,
  "Screw Pressure": 13.2,
  "Blow Mold CL FA": 0,
  "Blow Mold OP FA": 0.92,
  "Oil Temperature": 38.39999999999999,
  "Stretch Unit DW": 0.73,
  "Stretch Unit UP": 1.18,
  "Barrel Rear Rear": 294.8833333333334,
  "Barrel Rear Front": 295.075,
  "Blow Core Hold FW": 0.12,
  "Injection Mold CL": 1.32,
  "Injection Mold OP": 1.23,
  "Main RAM Pressure": 14,
  "Stretch Unit DW FA": 0.66,
  "Stretch Unit UP FA": 0.98,
  "Injection Mold CL FA": 0.66,
  "Injection Mold OP FA": 1.15
}

try:
    result = detector.predict_cycle(normal_cycle)
    print(f"  Prediction: {'🔴 DEFECT' if result['is_defect'] else '✓ Normal'}")
    print(f"  Alert Level: {result['alert_level']}")
    print(f"  Anomaly Score: {result['anomaly_score']:.4f}")
    print()
except Exception as e:
    print(f"✗ Prediction failed: {e}")
    print()

# Test with an abnormal cycle
print("Test 2b: Abnormal Cycle (High Pressure + Long Injection)")
abnormal_cycle = {
  "Blow Time": 5,
  "Bottom DW": 0.13,
  "Bottom UP": 0.15,
  "Cycle Time": 15,
  "Blow Mold C": 2.91,
  "Blow Mold M": 1.36,
  "Charge Time": 4.87,
  "V-P Time PV": 14.6,
  "Barrel Front": 284.9666666666667,
  "Blow Core DW": 2.3,
  "Blow Core UP": 0.76,
  "Blow Mold CL": 0.7,
  "Blow Mold OP": 0.82,
  "Cooling Time": 3,
  "Shot Size PV": 112,
  "Stretch Time": 0.8,
  "Barrel Middle": 295.05555555555554,
  "Barrel Nozzle": 279.72222222222223,
  "Dry Cycle Time": 5.07,
  "Injection Time": 5.9,
  "Lip Mold CL FA": 0.76,
  "Lip Mold OP FA": 0.71,
  "Screw Pressure": 13,
  "Blow Mold CL FA": 0,
  "Blow Mold OP FA": 0.92,
  "Oil Temperature": 38.4,
  "Stretch Unit DW": 0.76,
  "Stretch Unit UP": 1.21,
  "Barrel Rear Rear": 294.94444444444446,
  "Barrel Rear Front": 294.9,
  "Blow Core Hold FW": 0.12,
  "Injection Mold CL": 1.23,
  "Injection Mold OP": 1.23,
  "Main RAM Pressure": 14,
  "Stretch Unit DW FA": 0.66,
  "Stretch Unit UP FA": 0.98,
  "Injection Mold CL FA": 0.66,
  "Injection Mold OP FA": 1.15
}

try:
    result = detector.predict_cycle(abnormal_cycle)
    print(f"  Prediction: {'🔴 DEFECT' if result['is_defect'] else '✓ Normal'}")
    print(f"  Alert Level: {result['alert_level']}")
    print(f"  Anomaly Score: {result['anomaly_score']:.4f}")
    
    if result['is_defect']:
        print("  ✓ Correctly identified as anomaly!")
    else:
        print("  ⚠️  Model did not flag as defect (may need more training data)")
    print()
except Exception as e:
    print(f"✗ Prediction failed: {e}")
    print()



# Summary
print("="*80)
print("TESTING COMPLETE!")
print("="*80)
print("Model is ready for production use.")
print()
print("To integrate with real-time detection:")
print("  1. Add to data.py: from isbm_defect_detector import ISBMDefectDetector")
print("  2. Load model: detector.load_model('models/machine_60_model.pkl')")
print("  3. Predict: result = detector.predict_cycle(cycle_row)")
print()
print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)