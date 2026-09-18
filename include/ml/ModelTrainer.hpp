#pragma once

#include "ml/DataCollector.hpp"
#include "ml/ExecutionCohorts.hpp"
#include "ml/TransformerModel.hpp"
#include <filesystem>
#include <map>
#include <memory>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

namespace trade {
namespace ml {

enum class ModelType {
  RANDOM_FOREST,
  GRADIENT_BOOSTING,
  LINEAR_REGRESSION,
  TRANSFORMER,
  NEURAL_NETWORK
};

struct TrainingConfig {
  ModelType type = ModelType::RANDOM_FOREST;
  int epochs = 10;
  double learning_rate = 0.001;
  int batch_size = 32;
  bool batch_training = false;
  double test_split = 0.2;
  // <= 0 means use all available data
  int days_back = 0;
  // Safety guard for non-batch training extraction.
  // batch_training mode streams in batches and ignores this cap.
  // 0 means unlimited.
  int max_training_rows = 0;
  std::string model_name = "default_model";
  // "trade_outcomes" (default): train on ml_training_inputs, labeled from
  // realized PnL on signals that crossed a strategy's threshold and were
  // matched to an executed trade.
  // "opportunity_labels": train on ml_opportunity_labels, self-labeled from
  // every logged order-book state's own forward-looking, fee-adjusted
  // return, independent of signal generation or execution. Intended for the
  // ml_orderbook_opportunity strategy.
  std::string training_source = "trade_outcomes";
  // Forward-return horizon used only when training_source is
  // "opportunity_labels"; ignored otherwise.
  int opportunity_horizon_seconds = 60;
};

struct ModelMetrics {
  double accuracy = 0.0;
  double precision = 0.0;
  double recall = 0.0;
  double mse = 0.0;
  double r2_score = 0.0;
  double sharpe_ratio = 0.0;
  double profit_factor = 0.0;
  std::string validation_strategy = "walk_forward";
  std::string feature_set_version = "order_book_features_v1";
  nlohmann::json walk_forward_folds = nlohmann::json::array();
  nlohmann::json feature_importance = nlohmann::json::array();
  std::vector<ExecutionCohortMetrics> cohort_metrics;
  // Echoes TrainingConfig.training_source so training/report consumers can
  // tell a trade-outcome model apart from an opportunity-labeled one.
  std::string training_source = "trade_outcomes";
};

// JSON Serialization
void to_json(nlohmann::json &j, const ModelMetrics &m);
void from_json(const nlohmann::json &j, ModelMetrics &m);

class ModelTrainer {
public:
  explicit ModelTrainer(std::shared_ptr<DataCollector> collector);

  ModelMetrics train(const TrainingConfig &config);
  void export_transformer_artifact(const std::filesystem::path &output_path,
                                   int64_t input_features) const;
  void save_model(const std::string &path);
  void load_model(const std::string &path);

private:
  ModelMetrics
  train_random_forest(const std::vector<OrderBookFeatures> &features,
                      const std::vector<TradeOutcome> &outcomes);

  ModelMetrics train_xgboost(const std::vector<OrderBookFeatures> &features,
                             const std::vector<TradeOutcome> &outcomes);

  ModelMetrics train_transformer(const std::vector<OrderBookFeatures> &features,
                                 const std::vector<TradeOutcome> &outcomes,
                                 const TrainingConfig &config);

  std::shared_ptr<DataCollector> collector_;

  // Set by train_transformer on a successful run; consumed by
  // export_transformer_artifact to persist the actual gradient-trained
  // weights (transformer_weights.pt) alongside the packaged ONNX artifact.
  // Not populated when the model type isn't TRANSFORMER or training failed,
  // in which case export_transformer_artifact falls back to a shape-correct,
  // weight-free ONNX placeholder as before.
  StockTransformer trained_transformer_{nullptr};
  bool has_trained_transformer_ = false;
  int64_t trained_transformer_n_features_ = 0;
};

} // namespace ml
} // namespace trade
