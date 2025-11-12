# Plan for Hot-Swappable ML-Based Feature Generation from Order Book Data

## 1. Introduction

The objective is to develop and integrate a hot-swappable machine learning model that processes raw order book data to generate insightful features. These generated features will then be used as input for the existing downstream machine learning models that predict trading signals. This will enhance the predictive power of the system by moving from hand-crafted statistical features to learned representations of market microstructures.

## 2. Analysis of Current System

-   **Data Collection**: The `MLDataCollector` class in `src/trade_bot/ml/data_collector.py` is responsible for data handling. The `extract_order_book_snapshots` method can retrieve raw order book data, which is stored in a JSON format.
-   **Feature Engineering**: The `create_feature_vectors` method currently computes a set of pre-defined statistical features from the order book data (e.g., `bid_ask_imbalance`, `spread_percent`, `vwap`). These features are defined in the `OrderBookFeatures` dataclass.
-   **Modeling**: The existing ML models (`ModelTrainer`, `MLTradingOptimizer`) are trained using these hand-crafted features.

The current system lacks the ability to learn features directly from raw order book data, potentially missing complex, non-linear patterns.

## 3. Proposed Architecture

The new architecture will introduce a dedicated, hot-swappable feature generation layer.

-   **New Component: Feature Generation Model**: A new class of ML models will be introduced, specifically designed to process raw order book snapshots (e.g., a 2D array of price/volume for bids and asks) and output a dense feature vector. Suitable model architectures include Convolutional Neural Networks (CNNs) for capturing spatial patterns or Autoencoders for unsupervised feature learning.

-   **New Manager: `FeatureModelManager`**: A new manager, similar to the existing `ModelManager`, will be created to handle the lifecycle of these feature generation models. Its responsibilities will include:
    -   Registering, loading, and versioning feature generation models.
    -   Setting a specific model version as "active" for feature extraction.
    -   Providing an interface for hot-swapping models at runtime without service interruption.

-   **Integration with `MLDataCollector`**: The `create_feature_vectors` method will be modified to incorporate this new layer. The new workflow will be:
    1.  Retrieve the raw order book snapshot for a given signal.
    2.  Fetch the active feature generation model from the `FeatureModelManager`.
    3.  Pass the raw snapshot through the model to get a learned feature vector.
    4.  Combine the learned features with a curated subset of the original statistical features.
    5.  The `OrderBookFeatures` dataclass will be updated to include these new learned features.

-   **API for Hot-Swapping**: New API endpoints will be created to manage the feature generation models, allowing operators to list available models, switch the active model, and monitor their performance.

## 4. Implementation Plan

### Step 1: Build the Feature Generation Infrastructure
1.  **Create `FeatureModelManager`**: In a new file `src/trade_bot/ml/feature_model_manager.py`, implement the `FeatureModelManager` class. It should mirror the design of `ModelManager` with methods like `register_model`, `set_active_model`, `get_current_model`, and `list_models`.
2.  **Define a Base Model Interface**: Create a base class or interface for all feature generation models to ensure they have a consistent `predict(snapshot_data)` method.

### Step 2: Develop the First Feature Generation Model
1.  **Data Representation**: Define a standardized format for the raw order book snapshot (e.g., a fixed-size NumPy array).
2.  **Model Implementation**: Implement an initial feature generation model (e.g., a simple CNN or Autoencoder using PyTorch or TensorFlow).
3.  **Training Script**: Create a separate script to train this model. The training can be unsupervised (learning to reconstruct the order book) or supervised if intermediate labels can be engineered (e.g., predicting short-term price movement).

### Step 3: Integrate into the Data Pipeline
1.  **Update `OrderBookFeatures`**: Add new fields to the `OrderBookFeatures` dataclass in `data_collector.py` to hold the vector from the new model.
2.  **Modify `MLDataCollector`**:
    -   Inject an instance of `FeatureModelManager` into `MLDataCollector`.
    -   In `create_feature_vectors`, for each signal, fetch the corresponding raw snapshot using `extract_order_book_snapshots`.
    -   Use the active model from `FeatureModelManager` to process the snapshot.
    -   Populate the `OrderBookFeatures` object with both the newly generated features and the existing statistical ones.

### Step 4: Adapt Downstream Processes
1.  **Update `FeatureEngineer`**: The `preprocess_pipeline` in `feature_engineer.py` may need to be adjusted to handle the new, learned features (e.g., applying scaling).
2.  **Retrain Signal Models**: The main signal prediction models in `ModelTrainer` will need to be retrained with this new, enriched feature set to leverage their predictive power.

### Step 5: Expose via API
1.  **Add New Routes**: In `src/trade_bot/web/web_routes/ml_routes.py`, add new endpoints for managing the feature models (e.g., `POST /ml/feature_models/set_active`).
2.  **Implement Handlers**: In `src/trade_bot/web/web_handlers/ml_handler.py`, implement the logic to interact with the `FeatureModelManager`.

## 5. Testing Strategy

1.  **Unit Tests**: Add tests for the `FeatureModelManager` and the updated logic in `MLDataCollector`.
2.  **Integration Tests**: Create tests to verify the end-to-end pipeline: from a raw snapshot being processed by the feature model to the final signal model making a prediction.
3.  **A/B Performance Testing**: Design an experiment to compare the performance of the signal prediction models trained with and without the ML-generated features to quantify the improvement.

## 6. Rollback Plan

A feature flag will be implemented in the configuration (`data/ml_config.json`). This flag will control whether the `MLDataCollector` uses the ML-based feature generator or falls back to the original statistical feature calculation method. This allows for instantaneous rollback without requiring a code deployment.
