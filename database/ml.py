
import sys
import os
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import joblib
import json
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path


project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ISBMDefectDetector:

    
    def __init__(self, contamination=0.05):
        """
        Args:
            contamination: Expected defect rate (e.g., 0.05 = 5%)
        """
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=200,
            max_samples='auto',
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
            warm_start=False
        )
        self.feature_names = None
        self.feature_stats = None
        self.contamination = contamination
        
    def get_db_connection(self):
        """Create database connection matching your db.py"""
        return psycopg2.connect(
            host="localhost",
            dbname="postgres",
            user="postgres",
            password="admin",
            port=54321
        )
    
    def extract_features_from_cycle(self, data_json):
        
        if isinstance(data_json, str):
            data = json.loads(data_json)
        else:
            data = data_json
            
        features = {}
        
        # Time features 
        time_features = [
            "Injection Time", "Cooling Time", "Stretch Time", "Blow Time",
            "Cycle Time", "V-P Time PV", "Charge Time",
            "Injection Mold CL FA", "Injection Mold OP FA",
            "Lip Mold CL FA", "Lip Mold OP FA",
            "Blow Mold CL FA", "Blow Mold OP FA",
            "Dry Cycle Time", "Injection Mold CL", "Injection Mold OP",
            "Blow Core DW", "Blow Core UP", "Bottom UP", "Bottom DW",
            "Blow Mold CL", "Blow Mold OP", "Blow Core Hold FW",
            "Stretch Unit DW FA", "Stretch Unit UP FA",
            "Stretch Unit DW", "Stretch Unit UP",
            "Blow Mold M", "Blow Mold C"
        ]
        
        # Pressure features
        pressure_features = ["Main RAM Pressure", "Screw Pressure"]
        
        # Temperature features
        temp_features = [
            "Barrel Nozzle", "Barrel Front", "Barrel Middle",
            "Barrel Rear Front", "Barrel Rear Rear", "Oil Temperature"
        ]
        
        # Position features
        position_features = ["Shot Size PV"]
        

        all_features = time_features + pressure_features + temp_features + position_features
        
        for key in all_features:
            val = data.get(key)
            
            if val is None or (isinstance(val, (int, float)) and (np.isnan(val) or np.isinf(val))):
                features[key] = np.nan
            else:
                features[key] = float(val)
        
        # Derived features
        temp_vals = [features.get(f, np.nan) for f in temp_features]
        temp_vals = [v for v in temp_vals if not pd.isna(v)]
        
        if len(temp_vals) > 0:
            features['Temp_Mean'] = np.mean(temp_vals)
            features['Temp_Std'] = np.std(temp_vals) if len(temp_vals) > 1 else 0
            features['Temp_Range'] = max(temp_vals) - min(temp_vals) if len(temp_vals) > 1 else 0
        else:
            features['Temp_Mean'] = np.nan
            features['Temp_Std'] = np.nan
            features['Temp_Range'] = np.nan
        
        # Pressure ratio (useful for detecting pressure anomalies)
        main_ram = features.get("Main RAM Pressure", 0)
        screw = features.get("Screw Pressure", 1)
        if pd.notna(main_ram) and pd.notna(screw) and screw > 0:
            features['Pressure_Ratio'] = main_ram / screw
        else:
            features['Pressure_Ratio'] = np.nan
        
        # Cycle time ratios (detect timing anomalies)
        cycle_time = features.get("Cycle Time", 0)
        if pd.notna(cycle_time) and cycle_time > 0:
            inj_time = features.get("Injection Time", 0)
            cool_time = features.get("Cooling Time", 0)
            if pd.notna(inj_time):
                features['Injection_Ratio'] = inj_time / cycle_time
            if pd.notna(cool_time):
                features['Cooling_Ratio'] = cool_time / cycle_time
        
        return features
    
    def fetch_training_data(self, machine_id=None, days_back=30, 
                        start_date=None, end_date=None, limit=None, mold_id=None):
        """
        Fetch data from your database for training
        """
        conn = self.get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query
        query = """
        SELECT id, machine_id, timestamp, mold_id, data 
        FROM machine_data 
        WHERE 1=1
        """
        params = []
        
        if machine_id is not None:
            query += " AND machine_id = %s"
            params.append(machine_id)
        
        if mold_id is not None:
            query += " AND mold_id = %s"
            params.append(mold_id)
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        elif days_back:
            query += " AND timestamp >= NOW() - INTERVAL '%s days'"
            params.append(days_back)
            
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        print(f"Fetching training data...")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return pd.DataFrame()
        
        print(f"Processing {len(rows)} cycles...")
        
        # Extract features from each cycle
        data_list = []
        for row in rows:
            try:
                features = self.extract_features_from_cycle(row['data'])
                features['id'] = row['id']
                features['machine_id'] = row['machine_id']
                features['timestamp'] = row['timestamp']
                features['mold_id'] = row['mold_id']
                data_list.append(features)
            except Exception as e:
                print(f"Error processing row {row['id']}: {e}")
                continue
        
        df = pd.DataFrame(data_list)
        return df
    
    def prepare_features(self, df):
        """Prepare features for training/prediction"""
        # Separate metadata from features
        metadata_cols = ['id', 'machine_id', 'timestamp', 'mold_id']
        feature_cols = [col for col in df.columns if col not in metadata_cols]
        
        X = df[feature_cols].copy()
        
        # Handle missing values with median imputation
        X = X.fillna(X.median())
        
        # Fill any remaining NaNs with 0 (for columns that are all NaN)
        X = X.fillna(0)
        
        # Store feature names if first time
        if self.feature_names is None:
            self.feature_names = X.columns.tolist()
            print(f"Using {len(self.feature_names)} features for training")
        
        # Ensure same features as training
        if self.feature_names is not None:
            # Add missing columns with 0
            for col in self.feature_names:
                if col not in X.columns:
                    X[col] = 0
            # Keep only training features
            X = X[self.feature_names]
        
        return X
    
    def train(self, machine_id=None, days_back=30, mold_id=None):
        """
        Train model on historical data
        """
        print("="*80)
        print("TRAINING ISOLATION FOREST MODEL")
        print("="*80)
        
        # Fetch data
        df = self.fetch_training_data(
            machine_id=machine_id,
            days_back=days_back,
            mold_id=mold_id
        )
        
        if df.empty or len(df) < 10:
            raise ValueError(f"Insufficient data for training. Need at least 10 samples, got {len(df)}")
        
        print(f"\nFetched {len(df)} cycles")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        # Prepare features
        X = self.prepare_features(df)
        
        print(f"\nPrepared features: {X.shape}")
        print(f"Feature columns: {len(self.feature_names)}")
        
        # Calculate feature statistics for monitoring
        self.feature_stats = {
            'mean': X.mean().to_dict(),
            'std': X.std().to_dict(),
            'min': X.min().to_dict(),
            'max': X.max().to_dict(),
            'median': X.median().to_dict()
        }
        
        # Scale and train
        print("\nScaling features...")
        X_scaled = self.scaler.fit_transform(X)
        
        print("Training Isolation Forest...")
        self.model.fit(X_scaled)
        
        # Evaluate on training data
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        n_anomalies = (predictions == -1).sum()
        anomaly_pct = (n_anomalies / len(predictions)) * 100
        
        print("\n" + "="*80)
        print("TRAINING COMPLETE")
        print("="*80)
        print(f"Detected {n_anomalies} anomalies ({anomaly_pct:.2f}%)")
        print(f"Expected contamination rate: {self.contamination*100:.1f}%")
        print(f"Anomaly score range: {scores.min():.4f} to {scores.max():.4f}")
        print(f"Mean score: {scores.mean():.4f}")
        
        return df, predictions, scores
    
    def predict_cycle(self, cycle_data):
        """
        Predict on a single cycle (from cycle_logger.aggregate_cycle())
        
        Args:
            cycle_data: dict from cycle_logger.aggregate_cycle()
        
        Returns:
            dict with prediction results
        """
        features = self.extract_features_from_cycle(cycle_data)
        df = pd.DataFrame([features])
        
        X = self.prepare_features(df)
        X_scaled = self.scaler.transform(X)
        
        prediction = self.model.predict(X_scaled)[0]
        score = self.model.score_samples(X_scaled)[0]
        
        # Determine alert level based on score
        if prediction == -1:
            alert = "HIGH"
            is_defect = True
        elif score < -0.15:  # Adjust threshold based on your data
            alert = "MEDIUM"
            is_defect = False
        else:
            alert = "LOW"
            is_defect = False
        
        return {
            'is_defect': is_defect,
            'anomaly_score': float(score),
            'alert_level': alert,
            'prediction': int(prediction),
            'timestamp': datetime.now().isoformat()
        }
    
    def predict_batch(self, df):
        """Predict on batch of data"""
        X = self.prepare_features(df)
        X_scaled = self.scaler.transform(X)
        
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        # Calculate alert levels
        alert_levels = []
        for pred, score in zip(predictions, scores):
            if pred == -1:
                alert_levels.append("HIGH")
            elif score < -0.5:
                alert_levels.append("MEDIUM")
            else:
                alert_levels.append("LOW")
        
        return predictions, scores, alert_levels
    
    def analyze_anomalies(self, df, predictions, scores, top_n=10):
        """Analyze which features contribute most to anomalies"""
        X = self.prepare_features(df)
        
        anomaly_mask = predictions == -1
        normal_mask = predictions == 1
        
        if anomaly_mask.sum() == 0:
            print("No anomalies detected in dataset")
            return None
        
        anomaly_means = X[anomaly_mask].mean()
        normal_means = X[normal_mask].mean()
        
        # Calculate percentage differences
        pct_diff = ((anomaly_means - normal_means) / (normal_means + 1e-10)) * 100
        abs_diff = abs(anomaly_means - normal_means)
        
        # Sort by absolute difference
        top_features = abs_diff.nlargest(top_n)
        
        print("\n" + "="*80)
        print("TOP CONTRIBUTING FEATURES TO ANOMALIES")
        print("="*80)
        print(f"{'Feature':<35} {'Normal':>10} {'Anomaly':>10} {'Diff':>10} {'Diff %':>10}")
        print("-"*80)
        
        for feature in top_features.index:
            norm_val = normal_means[feature]
            anom_val = anomaly_means[feature]
            diff = anom_val - norm_val
            pct = pct_diff[feature]
            print(f"{feature:<35} {norm_val:>10.2f} {anom_val:>10.2f} {diff:>10.2f} {pct:>9.1f}%")
        
        return top_features
    
    def save_model(self, filepath="isbm_defect_model.pkl"):
        """Save trained model"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'feature_stats': self.feature_stats,
            'contamination': self.contamination,
            'trained_at': datetime.now().isoformat()
        }
        joblib.dump(model_data, filepath)
        print(f"\nModel saved to {filepath}")
    
    def load_model(self, filepath="isbm_defect_model.pkl"):
        """Load trained model"""
        model_data = joblib.load(filepath)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.feature_stats = model_data.get('feature_stats')
        self.contamination = model_data.get('contamination', 0.05)
        print(f"Model loaded from {filepath}")
        print(f"Trained at: {model_data.get('trained_at', 'Unknown')}")


# ==============================================================================
# INTEGRATION WITH YOUR EXISTING SYSTEM
# ==============================================================================

def integrate_with_data_collector(detector, machine_id=60):
    """
    Example integration with your data.py cycle logger
    This shows how to add real-time defect detection
    """
    from cycle_logger import CycleLogger
    from opc_client import OPCClient
    from tags import OPC_SERVER_URL, MACHINES
    
    # Initialize
    client = OPCClient(OPC_SERVER_URL)
    client.connect()
    
    logger = CycleLogger(client, machine_id=machine_id, tag_map=MACHINES)
    
    print(f"Starting real-time defect detection for Machine {machine_id}...")
    
    try:
        while True:
            cycle_row = logger.poll()
            
            if cycle_row is None:
                continue  # Cycle still running
            
            # Make prediction
            result = detector.predict_cycle(cycle_row)
            
            # Log result
            if result['is_defect']:
                print(f"\n  DEFECT DETECTED - Machine {machine_id}")
                print(f"   Alert Level: {result['alert_level']}")
                print(f"   Anomaly Score: {result['anomaly_score']:.4f}")
                print(f"   Timestamp: {result['timestamp']}")
            
            # Continue with normal data insertion
            # insert_machine_row(machine_id, mold_id, cycle_row)
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nStopping defect detector...")
    finally:
        client.disconnect()


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == "__main__":
    import time
    
    # Initialize detector with 5% expected defect rate
    detector = ISBMDefectDetector(contamination=0.05)
    
    # OPTION 1: Train on historical data
    print("\n### TRAINING MODEL ###\n")
    try:
        df_train, predictions, scores = detector.train(
            machine_id=60,     # Your machine ID
            days_back=30,      # Last 30 days
            mold_id=None       # All molds
        )
        
        # Analyze anomalies
        detector.analyze_anomalies(df_train, predictions, scores, top_n=15)
        
        # Save model
        detector.save_model("models/machine_60_model.pkl")
        
    except Exception as e:
        print(f"Training failed: {e}")
        print("Make sure you have data in the database!")
    
    # OPTION 2: Load existing model and predict
    print("\n### LOADING MODEL AND TESTING ###\n")
    try:
        detector.load_model("models/machine_60_model.pkl")
        
        # Test on recent data
        df_recent = detector.fetch_training_data(
            machine_id=60,
            limit=100
        )
        
        if not df_recent.empty:
            predictions, scores, alerts = detector.predict_batch(df_recent)
            
            df_recent['prediction'] = predictions
            df_recent['anomaly_score'] = scores
            df_recent['alert_level'] = alerts
            
            defects = df_recent[df_recent['prediction'] == -1]
            print(f"\nFound {len(defects)} potential defects in last 100 cycles")
            
            if len(defects) > 0:
                print("\nDefect examples:")
                print(defects[['id', 'timestamp', 'anomaly_score', 'alert_level']].head())
        
    except FileNotFoundError:
        print("Model file not found. Train a model first!")
    except Exception as e:
        print(f"Prediction failed: {e}")
    
    # OPTION 3: Real-time integration (commented out)
    # detector.load_model("models/machine_60_model.pkl")
    # integrate_with_data_collector(detector, machine_id=60)