# Transformer Implementation Plan

## Problem Definition
Implement a **Patch-based Temporal Transformer** (PCTT) for stock-price time series prediction as an alternative to the existing LSTM/sklearn models. The model predicts the next interval's log return based on a history of multivariate features.

## Architecture

### Model: Patchwise Causal Temporal Transformer
The model processes a time series of features, patches them into local temporal neighborhoods, and processes them with causal self-attention.

**Components:**
1.  **Input**: Multivariate time series $(B, T, F)$.
2.  **Patch Embedding**: Projects patches of size $P$ into embedding dimension $D$.
3.  **Positional Encoding**: Learned absolute positional encodings.
4.  **Transformer Encoder**: Stack of $L$ causal transformer blocks (Pre-Norm).
5.  **Prediction Head**: Linear layer projecting the final token to the scalar prediction (next log return).

### File Structure
New files will be added to `src/trade_bot/ml/`:
-   `src/trade_bot/ml/transformer.py`: Contains the PyTorch model definitions (`StockTransformer`, `PatchEmbedding`, `TransformerBlock`, `CausalSelfAttention`).
-   `src/trade_bot/ml/transformer_trainer.py`: Handles the training loop, data preparation, and evaluation for the Transformer model.

## Implementation Details

### 1. Model Definition (`src/trade_bot/ml/transformer.py`)
-   **Dependencies**: `torch`, `numpy`.
-   **Classes**:
    -   `PatchEmbedding`: Reshapes $(B, T, F)$ -> $(B, T/P, P \cdot F)$ -> Linear -> $(B, NumPatches, D)$.
    -   `CausalSelfAttention`: Standard multi-head attention with causal masking.
    -   `TransformerBlock`: LayerNorm -> Attention -> LayerNorm -> MLP.
    -   `StockTransformer`: Assembles the components.

### 2. Trainer Implementation (`src/trade_bot/ml/transformer_trainer.py`)
-   **Class**: `TransformerTrainer`.
-   **Data Preparation**:
    -   Input: 2D feature matrix $(N, F)$ from `FeatureEngineer`.
    -   Processing: Create sliding windows of length $T$ (Lookback) to form $(B, T, F)$ batches.
    -   Target: Next step log return.
-   **Training Loop**:
    -   Optimizer: `AdamW` (lr=3e-4, weight_decay=1e-4).
    -   Loss: `SmoothL1Loss`.
    -   Scheduler: Linear warmup + Cosine decay.
    -   Regularization: Dropout, Weight Decay.
-   **Integration**:
    -   Methods to save/load model state dicts (compatible with `ModelManager`'s file management, but using `torch.save`).

### 3. Integration with Existing System
-   **feature_engineer.py**: Ensure it produces the raw features required (Log Returns, Volume, etc.). The current `create_feature_matrix` is sufficient as a starting point, but `TransformerTrainer` will handle the temporal windowing.
-   **Training Manager**: To use this model, instantiate `TransformerTrainer` instead of `ModelTrainer` based on configuration.

## Verification Plan

### Automated Tests
1.  **Unit Tests for Model Components**:
    -   Verify output shapes of `PatchEmbedding`, `CausalSelfAttention`, `StockTransformer`.
    -   Test causal masking (future tokens should not affect current output).
2.  **Integration Test for Trainer**:
    -   Run a short training loop on synthetic data to ensure loss decreases.
    -   Verify save/load functionality.

### Manual Verification
1.  **Training Run**:
    -   Run the trainer on a sample dataset (or valid existing data).
    -   Monitor loss convergence.
    -   Compare RMSE/Profit Factor with baseline models.

## Next Steps
1.  Create `src/trade_bot/ml/transformer.py`.
2.  Create `src/trade_bot/ml/transformer_trainer.py`.
3.  Write a script or test to verify the implementation.
