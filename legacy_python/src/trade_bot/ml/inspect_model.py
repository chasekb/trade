
import joblib
import os
import json
import numpy as np

def inspect_model():
    with open("data/ml_config.json", "r") as f:
        config = json.load(f)
    active_model_id = config["active_model"]
    name, version = active_model_id.split(":")
    timestamp = version[1:] # strip 'v'
    
    model_path = f"data/models/trading_optimizer/{version}/trading_optimizer_{version}.pkl"
    trans_dir = f"data/transformers/transformers_{timestamp}"
    
    print(f"Loading model: {model_path}")
    model = joblib.load(model_path)
    
    print(f"Loading transformers from: {trans_dir}")
    imputer = joblib.load(os.path.join(trans_dir, "imputer.pkl"))
    scaler = joblib.load(os.path.join(trans_dir, "scaler.pkl"))
    pca = joblib.load(os.path.join(trans_dir, "pca.pkl"))
    # feature_selector = joblib.load(os.path.join(trans_dir, "feature_selector.pkl")) # MIGHT NOT EXIST
    
    print(f"Imputer features in: {imputer.n_features_in_}")
    print(f"Scaler features in: {scaler.n_features_in_}")
    print(f"PCA features in: {pca.n_features_in_}")
    print(f"PCA components: {pca.n_components_}")
    
    if hasattr(model, 'regressor'):
        print(f"Regressor: {type(model.regressor)}")
        print(f"Regressor features in: {model.regressor.coef_.shape[1] if hasattr(model.regressor, 'coef_') else 'N/A'}")
    
    if hasattr(model, 'classifier') and model.classifier:
        print(f"Classifier: {type(model.classifier)}")
        print(f"Classifier features in: {model.classifier.coef_.shape[1] if hasattr(model.classifier, 'coef_') else 'N/A'}")

if __name__ == "__main__":
    inspect_model()
