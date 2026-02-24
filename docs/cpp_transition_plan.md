# C++ Transition Plan: Backend & ML Server

This document outlines the strategy for migrating the existing Python FastAPI backend and Machine Learning components to a high-performance C++ architecture.

## 1. Executive Summary

The goal is to replace the current Python/FastAPI/Uvicorn stack with a C++ microservice system while integrating the new **Patch-based Temporal Transformer** plan. The transition prioritizes performance, type safety, and efficient inference.

**Key Architectural Decisions:**

* **Web Framework**: `Drogon` or `Crow` (Drogon recommended for full-featured C++ web framework).
* **ML Inference (Unified)**: `ONNX Runtime` (C++ API). This provides a single runtime for both:
  * Existing Scikit-Learn models (RF, GB, etc.) converted to ONNX.
  * New PyTorch Transformer models exportable to ONNX.
* **Deep Learning Alternative**: `LibTorch` (C++ Interface for PyTorch) could be used specifically for the Transformer if ONNX export proves difficult or lacks operator support.
* **Database**: `libpqxx` for PostgreSQL.
* **JSON**: `nlohmann/json`.

## 2. Architecture Overview

### Current (Python)

* **App**: FastAPI (ASGI)
* **ML**: Scikit-Learn (Pickle) + PyTorch (Planned Transformer)
* **Data**: Pandas/Numpy for feature engineering

### Target (C++)

* **App**: Drogon (HTTP/WebSocket)
* **ML**: ONNX Runtime (loads `.onnx` models)
* **Data**: `Xtensor` or native `std::vector` optimizations for feature engineering

## 3. Implementation Phases

### Phase 1: Foundation & Dependencies

* [x] Refactor Python codebase to `legacy_python/` directory
  * [x] Move `src/` and `app.py` into `legacy_python/` directory
  * [x] Move Python test directories and environments: `tests/`, `.pytest_cache/`, and `.venv/` to `legacy_python/`
  * [x] Move obsolete structures: `archive/` to `legacy_python/`
  * [x] Move Python-specific documentation files from `docs/` to `legacy_python/docs/`
  * [x] Move Python-specific configuration files from `config/` to `legacy_python/config/`
  * [x] Update `.gitignore` to reflect the new `legacy_python/` paths for ignored files (like `__pycache__`, `.venv`, etc.)
  * [x] Update imports or Dockerfile context paths so the existing `docker-compose.yml` can still run correctly using the relocated Python code
* [x] Create base C++ source directory `src/cpp_backend/`
* [x] Set up `CMakeLists.txt` with required C++ standards (C++17/20)
* [x] Configure `vcpkg` for dependency management by creating a `vcpkg.json` manifest file
* [x] Add dependencies to build system:
  * [x] Web Framework: `drogon` (or `crow`)
  * [x] JSON: `nlohmann_json`
  * [x] PostgreSQL: `libpqxx`
  * [x] Redis: `redis-plus-plus`
  * [x] Logging: `spdlog`
  * [x] ML/Math: `onnxruntime`, `xtensor`
* [x] Create initial `main.cpp` with a simple HTTP "Hello World" endpoint
* [x] Create `Dockerfile` tailored for the C++ build and runtime stages
* [x] Update `docker-compose.yml` to include the new C++ backend service (initially on a different port for testing)
* [x] **Deliverable**: Containerized C++ server successfully responding to `GET /health` requests

### Phase 2: Core Infrastructure

* [x] Configuration Management
  * [x] Implement `Config` class parsing `.env` files and environment variables
  * [x] Map all existing Python environment variables to C++ configurations
* [x] Logging System
  * [x] Integrate `spdlog` to match Python's formatting and output destinations (stdout/file)
* [x] Database Connections
  * [x] Implement `DatabaseManager` wrapper around `libpqxx` connection pooling
  * [x] Port schema queries or integrate with existing database
* [x] Redis Cache
  * [x] Implement `CacheManager` wrapper around `redis-plus-plus`
  * [x] Emulate current standard cache read/write formats

### Phase 3: ML Model Export (Python Side)

* [x] Update `requirements.txt` / `uv.lock` to include `skl2onnx`, `onnx`, and `onnxruntime`
* [x] Create standalone Python script `legacy_python/src/trade_bot/ml/export_to_onnx.py`
  * [x] Add conversion logic for existing SGD regressors and classifiers using `skl2onnx`
  * [x] Define precise input/output tensor shapes and types for the ONNX graphs
  * [x] Ensure custom `TradingModelWrapper` components are individually exported
* [x] Create Validation Script `legacy_python/src/trade_bot/ml/verify_onnx.py`
  * [x] Load same input into both `.pkl` models and their ONNX counterparts
  * [x] Assert predictions (floating-point values) match within a strict tolerance (`1e-9`)
* [x] **Deliverable**: Set of verified `.onnx` models in `data/onnx/` ready for C++ inference.

### Phase 4: Feature Engineering (The Critical Path)

* [x] Analyze `legacy_python/src/trade_bot/ml/feature_engineer.py` and isolate all pure math/pandas functionality
* [x] Create "Golden Data" test set: Python script `generate_golden_data.py` to dump raw inputs and final processed outputs to JSON
* [x] Implement C++ `FeatureEngineer` class
  * [x] Setup `Xtensor` arrays for time-series memory structures
  * [x] Implement Imputation logic (mean filling)
  * [x] Implement Sliding Window / Rolling Statistics (moving average, momentum, volatility) on Log Returns
  * [x] **New**: Implement multi-horizon analysis (5, 10, 20, 50, 90, 200) for all rolling statistics
  * [x] Implement Interaction features (polynomials) equivalent to python
  * [x] Implement Standard Scaling and PCA parameter loading from JSON
* [x] Unit test C++ `FeatureEngineer` against the Python "Golden Data" using `test_feature_engineer.cpp`
* [x] **Deliverable**: High-performance C++ `FeatureEngineer` class verified against Python implementation within `1e-7` tolerance.

### Phase 5: Inference Engine & API

* [x] Implement `ONNXModelManager` class wrapping the C++ `onnxruntime` library
  * [x] Implement model loading and session creation
  * [x] Implement tensor memory allocation mapping `Xtensor` structures to ONNX input arrays
  * [x] Handle asynchronous/threaded inference properly
* [x] Implement Web Endpoints (Drogon/Crow)
  * [x] `POST /predict`: Read JSON request, map to C++ structs -> run `FeatureEngineer` -> run `ONNXModelManager` -> return JSON
  * [x] `POST /set_active`: Update the current in-memory ONNX session (hot-swapping models) - *Note: Handled by session reload*
  * [x] `GET /status` and `/performance`: Read model metadata gracefully - *Note: Handled by health check and logs*
* [x] Performance profile API endpoint latency

### Phase 6: Transformer Integration

* [x] Ensure Python `TransformerTrainer` outputs compatible ONNX models (Batch, Seq, Features)
* [x] Implement multi-dimensional tensor construction in `ONNXModelManager` for 3D transformer tokens vs 2D standard ML features
* [x] Ensure C++ `FeatureEngineer` properly maintains the temporal sequence buffer required for the Transformer Lookback period
* [x] Integration test: Execute end-to-end predicting sequence logic in C++ and confirm it functionally matches Python `TransformerTrainer` evaluation output

## 4. Detailed Component Mapping

| Python Component | C++ Replacement | Notes |
| :--- | :--- | :--- |
| `FastAPI` | `Drogon` | High-throughput, async IO. |
| `pydantic` | `struct` + `nlohmann/json` | Manual validation or reflection based serializers. |
| `pandas` | `Xtensor` / Custom | Custom logic for sliding windows is often faster in C++. |
| `scikit-learn` | `ONNX Runtime` | Export via `skl2onnx`. |
| `PyTorch` | `ONNX Runtime` | Export via `torch.onnx` or `LibTorch` (C++ native). |
| `sqlalchemy` | `libpqxx` | Raw SQL or simple ORM mapper. |

## 5. Risk Mitigation

* **Feature Drift**: Small differences in floating-point math between Python/Pandas and C++ can accumulate. *Mitigation*: Strict unit testing with high-precision comparisons.
* **Training Compatibility**: Training complex models (like RF/GB) in C++ is non-trivial. *Strategy*: **Keep training in Python**. The C++ server should focus purely on *inference*. Triggers to `/train` should spawn a Python job or container.

## 6. Next Steps

1. Set up the C++ project skeleton with CMake.
2. Write the `skl2onnx` conversion script for existing models.
3. Implement the C++ `FeatureEngineer` and verify against Python outputs.
