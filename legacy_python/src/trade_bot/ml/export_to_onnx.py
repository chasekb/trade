
import joblib
import os
import json
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx

def export_to_onnx():
    # Load config to find active model
    with open("data/ml_config.json", "r") as f:
        config = json.load(f)
    active_model_id = config["active_model"]
    name, version = active_model_id.split(":")
    timestamp = version[1:] # strip 'v'
    
    model_path = f"data/models/trading_optimizer/{version}/trading_optimizer_{version}.pkl"
    trans_dir = f"data/transformers/transformers_{timestamp}"
    output_dir = "data/onnx"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading model: {model_path}")
    wrapper = joblib.load(model_path)
    
    print(f"Loading transformers from: {trans_dir}")
    imputer = joblib.load(os.path.join(trans_dir, "imputer.pkl"))
    scaler = joblib.load(os.path.join(trans_dir, "scaler.pkl"))
    pca = joblib.load(os.path.join(trans_dir, "pca.pkl"))
    
    # 1. Export Imputer
    print("Exporting Imputer...")
    initial_type = [('float_input', FloatTensorType([None, imputer.n_features_in_]))]
    onx_imputer = convert_sklearn(imputer, initial_types=initial_type)
    with open(os.path.join(output_dir, "imputer.onnx"), "wb") as f:
        f.write(onx_imputer.SerializeToString())
        
    # 2. Export Preprocessing (Scaler + PCA)
    print("Exporting Preprocessing (Scaler + PCA)...")
    from sklearn.pipeline import Pipeline
    pre_pipeline = Pipeline([
        ('scaler', scaler),
        ('pca', pca)
    ])
    initial_type_pre = [('float_input', FloatTensorType([None, scaler.n_features_in_]))]
    onx_pre = convert_sklearn(pre_pipeline, initial_types=initial_type_pre)
    with open(os.path.join(output_dir, "preprocessing.onnx"), "wb") as f:
        f.write(onx_pre.SerializeToString())
        
    # 3. Export Regressor
    print("Exporting Regressor...")
    regressor = wrapper.regressor
    # Determine input size for regressor (should match PCA output)
    n_features_reg = regressor.coef_.shape[0] if hasattr(regressor, 'coef_') else pca.n_components_
    initial_type_reg = [('float_input', FloatTensorType([None, n_features_reg]))]
    onx_reg = convert_sklearn(regressor, initial_types=initial_type_reg)
    with open(os.path.join(output_dir, "regressor.onnx"), "wb") as f:
        f.write(onx_reg.SerializeToString())
        
    # 4. Export Classifier (if exists)
    if hasattr(wrapper, 'classifier') and wrapper.classifier:
        print("Exporting Classifier...")
        classifier = wrapper.classifier
        n_features_cls = classifier.coef_.shape[1] if hasattr(classifier, 'coef_') else pca.n_components_
        initial_type_cls = [('float_input', FloatTensorType([None, n_features_cls]))]
        # For classifier, we want probabilities if possible
        # SGDClassifier with log loss supports predict_proba
        onx_cls = convert_sklearn(classifier, initial_types=initial_type_cls, 
                                 options={type(classifier): {'zipmap': False}})
        with open(os.path.join(output_dir, "classifier.onnx"), "wb") as f:
            f.write(onx_cls.SerializeToString())
            
    print(f"ONNX models exported to {output_dir}")

if __name__ == "__main__":
    export_to_onnx()
