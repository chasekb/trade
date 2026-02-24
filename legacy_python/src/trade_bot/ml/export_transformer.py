
import torch
import os
import json
import numpy as np
from trade_bot.ml.transformer import StockTransformer

def export_dummy_transformer():
    # Model parameters
    n_features = 26 # Raw features before TS/Interactions? 
    # OR should it take the 353 features? 
    # Usually Transformers take the raw features and learn temporal patterns themselves.
    # Let's assume it takes the 26 base features.
    
    lookback = 60 # 1 hour of minute data
    patch_size = 5
    embedding_dim = 64
    n_heads = 4
    n_layers = 3
    
    model = StockTransformer(n_features, lookback, patch_size, embedding_dim, n_heads, n_layers)
    model.eval()
    
    # Create dummy input: (Batch, SeqLen, Features)
    dummy_input = torch.randn(1, lookback, n_features)
    
    output_dir = "data/onnx"
    os.makedirs(output_dir, exist_ok=True)
    onnx_path = os.path.join(output_dir, "transformer.onnx")
    
    print(f"Exporting Transformer to {onnx_path}...")
    
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=['sequence_input'],
        output_names=['pnl_output'],
        dynamic_axes={
            'sequence_input': {0: 'batch_size'},
            'pnl_output': {0: 'batch_size'}
        }
    )
    
    # Save model config for C++ reference
    config = {
        "n_features": n_features,
        "lookback": lookback,
        "patch_size": patch_size,
        "embedding_dim": embedding_dim,
        "n_heads": n_heads,
        "n_layers": n_layers
    }
    with open(os.path.join(output_dir, "transformer_config.json"), "w") as f:
        json.dump(config, f, indent=2)
        
    print("Transformer export complete.")

if __name__ == "__main__":
    export_dummy_transformer()
