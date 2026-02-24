
import joblib
import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any

def extract_parameters_and_golden_data():
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    
    output_dir = "data/cpp_assets"
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Generate Dummy Data for Fitting
    np.random.seed(42)
    n_samples_fit = 300
    
    from trade_bot.ml.data_collector import OrderBookFeatures
    from trade_bot.ml.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    
    fit_data_list = []
    for i in range(n_samples_fit):
        mid_price = 10000.0 + i * 1.0 + np.random.randn() * 10.0
        vwap = mid_price + np.random.randn() * 2.0
        f = OrderBookFeatures(
            timestamp=1700000000 + i * 60,
            symbol="BTC-USD",
            bid_ask_imbalance=np.random.randn(),
            spread_percent=0.001 + np.random.rand() * 0.001,
            mid_price=mid_price,
            bid_volume=1.0 + np.random.rand() * 10,
            ask_volume=1.0 + np.random.rand() * 10,
            order_book_depth=5,
            large_bid_wall=np.random.choice([True, False]),
            large_ask_wall=np.random.choice([True, False]),
            wall_size=10.0 + np.random.rand() * 50,
            volume_weighted_price=vwap,
            price_momentum=np.random.randn() * 0.1,
            volatility=0.02 + np.random.rand() * 0.01,
            volume_24h=1000000.0,
            volume_30d=30000000.0,
            high_24h=mid_price * 1.02,
            low_24h=mid_price * 0.98,
            prev_win_probability=0.5,
            prev_expected_return=0.01,
            prev_confidence=0.8
        )
        fit_data_list.append(f)
        
    # Get base features for all
    X_base_all = np.array([list(fe._extract_features(f).values()) for f in fit_data_list])
    
    # Fit Pipeline components
    imputer = SimpleImputer(strategy='mean')
    X_imp_all = imputer.fit_transform(X_base_all)
    
    # Batch process TS to avoid complex history management during fit
    X_ts_all = fe.create_time_series_features(X_imp_all)
    X_inter_all = fe.create_interaction_features(X_ts_all)
    
    scaler = StandardScaler()
    X_scaled_all = scaler.fit_transform(X_inter_all)
    
    pca = PCA(n_components=10) # Fixed 10 components for testing
    X_pca_all = pca.fit_transform(X_scaled_all)
    
    fe.imputer = imputer
    fe.scaler = scaler
    fe.pca = pca

    # 1. Export Parameters to JSON
    params = {
        "imputer": {
            "statistics": imputer.statistics_.tolist()
        },
        "scaler": {
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist()
        },
        "pca": {
            "components": pca.components_.tolist(),
            "mean": pca.mean_.tolist(),
            "explained_variance": pca.explained_variance_.tolist()
        }
    }
    
    with open(os.path.join(output_dir, "feature_params.json"), "w") as f:
        json.dump(params, f, indent=2)
        
    # 2. Generate Golden Data
    # We need a sequence of raw OrderBookFeatures objects to test rolling stats correctly.
    # I'll create 10 dummy samples.
    np.random.seed(42)
    n_samples = 10
    
    # Create raw features list
    # We'll simulate 26 input features that match what _extract_features expects in the 'features' object
    # OR we can just mock the OrderBookFeatures class/struct
    
    from trade_bot.ml.data_collector import OrderBookFeatures
    
    raw_features_list = []
    for i in range(n_samples):
        # Scale mid_price to be realistic for logs
        mid_price = 10000.0 + i * 10.0 + np.random.randn() * 5.0
        vwap = mid_price + np.random.randn() * 2.0
        
        f = OrderBookFeatures(
            timestamp=1700000000 + i * 60,
            symbol="BTC-USD",
            bid_ask_imbalance=np.random.randn(),
            spread_percent=0.001 + np.random.rand() * 0.001,
            mid_price=mid_price,
            bid_volume=1.0 + np.random.rand() * 10,
            ask_volume=1.0 + np.random.rand() * 10,
            order_book_depth=5,
            large_bid_wall=np.random.choice([True, False]),
            large_ask_wall=np.random.choice([True, False]),
            wall_size=10.0 + np.random.rand() * 50,
            volume_weighted_price=vwap,
            price_momentum=np.random.randn() * 0.1,
            volatility=0.02 + np.random.rand() * 0.01,
            volume_24h=1000000.0,
            volume_30d=30000000.0,
            high_24h=mid_price * 1.02,
            low_24h=mid_price * 0.98,
            prev_win_probability=0.5,
            prev_expected_return=0.01,
            prev_confidence=0.8
        )
        raw_features_list.append(f)
        
    # Process them using Python FeatureEngineer
    from trade_bot.ml.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    fe.imputer = imputer
    fe.scaler = scaler
    fe.pca = pca
    
    # We'll process them one by one to simulate live inference
    # Python FeatureEngineer has been updated (I recall from earlier logs) to handle historical data
    
    golden_data = []
    historical_data = None
    
    for i in range(n_samples):
        current_f = raw_features_list[i]
        
        # Step A: _extract_features (26 base features)
        base_features_dict = fe._extract_features(current_f)
        base_features = list(base_features_dict.values())
        
        # Step B: Preprocess Pipeline (Includes Imputation, TS, Interactions, Scale, PCA)
        # For a single sample, we need to pass historical data for TS to work
        X_in = np.array([base_features])
        
        # We need to manually chain the steps to get intermediate values for verification
        # 1. Impute
        X_imp = fe.imputer.transform(X_in)
        
        # 2. Time Series (needs history)
        X_ts = fe.create_time_series_features(X_imp, historical_data=historical_data)
        
        # 3. Interactions
        X_inter = fe.create_interaction_features(X_ts)
        
        # 4. Scale
        X_scaled = fe.scaler.transform(X_inter)
        
        # 5. PCA
        X_pca = fe.pca.transform(X_scaled)
        
        golden_data.append({
            "raw": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else float(v) if isinstance(v, (float, np.float64, np.float32, np.int64, int)) else v) 
                    for k, v in current_f.__dict__.items() if k not in ["timestamp", "symbol"]},
            "base": [float(x) for x in base_features],
            "imputed": [float(x) for x in X_imp.tolist()[0]],
            "ts": [float(x) for x in X_ts.tolist()[0]],
            "interactions": [float(x) for x in X_inter.tolist()[0]],
            "scaled": [float(x) for x in X_scaled.tolist()[0]],
            "pca": [float(x) for x in X_pca.tolist()[0]]
        })
        
        # Update historical data (keep enough for max window 200)
        if historical_data is None:
            historical_data = X_imp
        else:
            historical_data = np.vstack([historical_data, X_imp])
            # window 200 needs 199 previous points
            if historical_data.shape[0] > 199:
                historical_data = historical_data[-199:]
                
    with open(os.path.join(output_dir, "golden_features.json"), "w") as f:
        json.dump(golden_data, f, indent=2)
        
    print(f"Extracted parameters and golden data to {output_dir}")

if __name__ == "__main__":
    extract_parameters_and_golden_data()
