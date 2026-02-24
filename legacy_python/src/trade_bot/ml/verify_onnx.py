
import joblib
import os
import json
import numpy as np
import onnxruntime as ort

def verify_onnx():
    # Load config to find active model
    with open("data/ml_config.json", "r") as f:
        config = json.load(f)
    active_model_id = config["active_model"]
    name, version = active_model_id.split(":")
    timestamp = version[1:] # strip 'v'
    
    model_path = f"data/models/trading_optimizer/{version}/trading_optimizer_{version}.pkl"
    trans_dir = f"data/transformers/transformers_{timestamp}"
    onnx_dir = "data/onnx"
    
    print(f"Loading Pickle model: {model_path}")
    wrapper = joblib.load(model_path)
    
    print(f"Loading transformers from: {trans_dir}")
    imputer = joblib.load(os.path.join(trans_dir, "imputer.pkl"))
    scaler = joblib.load(os.path.join(trans_dir, "scaler.pkl"))
    pca = joblib.load(os.path.join(trans_dir, "pca.pkl"))
    
    # Create dummy input (26 features for imputer)
    np.random.seed(42)
    dummy_input = np.random.randn(1, 26).astype(np.float32)
    
    # 1. Run Pickle Pipeline
    print("\n--- Running Pickle Pipeline ---")
    x_imp = imputer.transform(dummy_input)
    # The current feature_engineer.py adds TS and Interaction features.
    # For this verification, we are testing the exported components (Imputer, Preprocessing, Regressor).
    # Preprocessing (Scaler + PCA) was exported as a unit.
    # We need to make sure we match the expected dimensions.
    
    # We know Scaler expects 93 features (from inspect_model.py output)
    # This means between Imputer (26) and Scaler (93) there is Feature Engineering (TS + Interactions).
    # Our ONNX preprocessing starts AT Scaler.
    
    # So we should run the Python Feature Eng to get the 93 features.
    from trade_bot.ml.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    fe.imputer = imputer
    fe.scaler = scaler
    fe.pca = pca
    
    # Standard preprocess_pipeline in feature_engineer.py:
    # 1. Impute
    # 2. TS (adds rolling mean/std of changes?)
    # 3. Interaction
    # 4. Scale
    # 5. PCA
    # 6. Select
    
    # WAIT, our ONNX export was:
    # 1. Imputer (26 -> 26)
    # 2. Preprocessing (Scaler + PCA) (93 -> 11)
    # 3. Regressor (11 -> 1)
    
    # The gap is between 26 and 93. This is the Feature Engineering logic 
    # (TS and interactions) THAT WE HAVE NOT PORTED TO C++ OR ONNX YET. 
    # That's Phase 4.
    
    # For verification, let's manually generate the 93 features.
    # In feature_engineer.py:
    # ts adds 26*2 = 52 features -> 26 + 52 = 78
    # interaction adds interaction of first 5 -> 5*6/2 = 15 features -> 78 + 15 = 93. Matches!
    
    x_ts = fe.create_time_series_features(x_imp)
    x_inter = fe.create_interaction_features(x_ts)
    x_scaled = scaler.transform(x_inter)
    x_pca = pca.transform(x_scaled)
    py_pred = wrapper.regressor.predict(x_pca)
    print(f"Pickle Prediction: {py_pred}")
    
    # 2. Run ONNX Pipeline
    print("\n--- Running ONNX Pipeline ---")
    # Imputer
    sess_imp = ort.InferenceSession(os.path.join(onnx_dir, "imputer.onnx"))
    onnx_imp = sess_imp.run(None, {'float_input': dummy_input})[0]
    
    # Preprocessing (needs 93 input)
    # We use the Python-generated 93 features for now to verify the Scaler/PCA/Regressor export
    sess_pre = ort.InferenceSession(os.path.join(onnx_dir, "preprocessing.onnx"))
    onnx_pca = sess_pre.run(None, {'float_input': x_inter.astype(np.float32)})[0]
    
    # Regressor
    sess_reg = ort.InferenceSession(os.path.join(onnx_dir, "regressor.onnx"))
    onnx_pred = sess_reg.run(None, {'float_input': onnx_pca})[0]
    print(f"ONNX Prediction: {onnx_pred}")
    
    # Compare
    diff = np.abs(py_pred - onnx_pred.flatten())
    print(f"\nMax difference: {np.max(diff)}")
    
    if np.max(diff) < 1e-5:
        print("SUCCESS: ONNX outputs match Pickle outputs within tolerance!")
    else:
        print("FAILURE: ONNX outputs do not match Pickle outputs!")

if __name__ == "__main__":
    verify_onnx()
