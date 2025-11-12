# Hot-Swappable ML-Based Feature Generation

This document provides a detailed overview of the hot-swappable machine learning-based feature generation system. This system is designed to enhance the predictive power of the trading bot by moving from hand-crafted statistical features to learned representations of market microstructures.

## 1. Introduction

The objective of this system is to develop and integrate a hot-swappable machine learning model that processes raw order book data to generate insightful features. These generated features are then used as input for the existing downstream machine learning models that predict trading signals.

## 2. Architecture

The new architecture introduces a dedicated, hot-swappable feature generation layer.

-   **New Component: Feature Generation Model**: A new class of ML models has been introduced, specifically designed to process raw order book snapshots (e.g., a 2D array of price/volume for bids and asks) and output a dense feature vector. Suitable model architectures include Convolutional Neural Networks (CNNs) for capturing spatial patterns or Autoencoders for unsupervised feature learning.

-   **New Manager: `FeatureModelManager`**: A new manager, similar to the existing `ModelManager`, has been created to handle the lifecycle of these feature generation models. Its responsibilities include:
    -   Registering, loading, and versioning feature generation models.
    -   Setting a specific model version as "active" for feature extraction.
    -   Providing an interface for hot-swapping models at runtime without service interruption.

-   **Integration with `MLDataCollector`**: The `create_feature_vectors` method has been modified to incorporate this new layer. The new workflow is:
    1.  Retrieve the raw order book snapshot for a given signal.
    2.  Fetch the active feature generation model from the `FeatureModelManager`.
    3.  Pass the raw snapshot through the model to get a learned feature vector.
    4.  Combine the learned features with a curated subset of the original statistical features.
    5.  The `OrderBookFeatures` dataclass has been updated to include these new learned features.

-   **API for Hot-Swapping**: New API endpoints have been created to manage the feature generation models, allowing operators to list available models, switch the active model, and monitor their performance.

## 3. API Endpoints

The following API endpoints are available for managing the feature generation models:

-   `GET /feature_models`: Get a list of available feature generation models.
-   `POST /feature_models/set_active`: Set the active feature generation model.

## 4. Rollback Plan

A feature flag has been implemented in the configuration (`data/ml_config.json`). This flag controls whether the `MLDataCollector` uses the ML-based feature generator or falls back to the original statistical feature calculation method. This allows for instantaneous rollback without requiring a code deployment.
