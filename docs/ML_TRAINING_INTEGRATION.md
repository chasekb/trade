# ML System C++ Migration Documentation

This document describes the full migration of the Machine Learning (ML) system—including data collection, feature engineering, training, and inference—from Python to a pure C++ architecture.

## Overview

To maximize execution speed and minimize resource overhead, the entire ML lifecycle is being transitioned into the C++ Backend. This eliminates the need for a Python runtime and heavy data science libraries in the production environment.

## Target Architecture

The target architecture is a unified C++ system that handles all ML operations.

```mermaid
graph TD
    UI[Frontend UI] -- "GET /ml/status" --> CPP[C++ Backend (Drogon)]
    UI -- "POST /ml/train" --> CPP
    
    subgraph "C++ ML Engine"
        API[API Controllers]
        Engine[ML Training Engine]
        Inference[ONNX Inference Engine]
        FE[Feature Engineer]
    end
    
    API -- "Trigger/Query" --> Engine
    Engine -- "Fetch Data" --> DB[(Postgres)]
    Engine -- "Compute" --> FE
    Engine -- "Save Model" --> Assets[Assets Directory]
    Inference -- "Load" --> Assets
    CPP -- "Cache/Status" --> Redis[(Redis)]
```

- **Frontend**: Communicates exclusively with the C++ API for status and task triggering.
- **ML Training Engine**: A dedicated C++ component that fetches data from Postgres, processes it, and trains models using high-performance C++ libraries.
- **Inference Engine**: Already implemented in C++ using ONNX Runtime for high-speed predictions.
- **Feature Engineer**: Fully implemented in C++ to ensure consistency between training and inference.

## Implementation Roadmap

The migration is divided into several high-priority phases:

### [Phase 1] Feature Engineering Parity

- **Status**: Completed.
- **Details**: Ported all Python feature transforms (scaling, PCA, rolling statistics) to `src/cpp_backend/ml/FeatureEngineer.cpp` using `xtensor`.

### [Phase 2] C++ Training Engine

- **Objective**: Implement model training logic in C++.
- **Tech Stack**:
  - `mlpack`: For Random Forest, Linear Regression, and Neural Networks.
  - `XGBoost C++ SDK`: For Gradient Boosting models.
  - **`LibTorch` (PyTorch C++ Backend)**: For high-performance Transformer-based temporal models.
- **Tasks**:
  - Implement `ModelTrainer.cpp` to mirror the legacy Python `model_trainer.py` logic.
  - **Port `StockTransformer` architecture** to C++ leveraging `LibTorch` (Patching, Causal Attention, MLP blocks).
  - Integrate `libpqxx` for high-speed training data extraction from Postgres.

### [Phase 3] API & Orchestration

- **Status**: Completed.
- **Objective**: Provide the management interface for ML operations.
- **Tasks**:
  - Implement `/ml/train` and `/ml/status` endpoints in `PredictController.cpp`.
  - Use Redis to track training progress and status for the UI.
  - Implement model versioning and "hot-reloading" in `ONNXModelManager`.

### [Phase 4] Performance & Stats

- **Status**: Completed.
- **Objective**: Port model evaluation and trading-specific metrics.
- **Tasks**:
  - Implement Sharpe Ratio, Profit Factor, and standard ML metrics (R2, MSE, precision/recall) in C++.
  - Provide a `/ml/performance` endpoint for the dashboard.

## File Structure

- `src/cpp_backend/ml/`:
  - `FeatureEngineer.cpp`: Shared feature logic.
  - `ModelTrainer.cpp`: [NEW] Training logic.
  - `ONNXModelManager.cpp`: Model loading and inference.
- `src/cpp_backend/api/`:
  - `PredictController.cpp`: API endpoints for predictions and management.
- `include/api/`: Header definitions.
