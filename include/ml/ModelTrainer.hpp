#pragma once

#include "ml/DataCollector.hpp"
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
  bool batch_training = true;
  double test_split = 0.2;
  // <= 0 means use all available data
  int days_back = 0;
  // Safety guard for non-batch training extraction.
  // batch_training mode streams in batches and ignores this cap.
  // 0 means unlimited.
  int max_training_rows = 0;
  std::string model_name = "default_model";
};

struct ModelMetrics {
  double accuracy = 0.0;
  double precision = 0.0;
  double recall = 0.0;
  double mse = 0.0;
  double r2_score = 0.0;
  double sharpe_ratio = 0.0;
  double profit_factor = 0.0;
};

// JSON Serialization
void to_json(nlohmann::json &j, const ModelMetrics &m);
void from_json(const nlohmann::json &j, ModelMetrics &m);

class ModelTrainer {
public:
  explicit ModelTrainer(std::shared_ptr<DataCollector> collector);

  ModelMetrics train(const TrainingConfig &config);
  void save_model(const std::string &path);
  void load_model(const std::string &path);

private:
  ModelMetrics
  train_random_forest(const std::vector<OrderBookFeatures> &features,
                      const std::vector<TradeOutcome> &outcomes);

  ModelMetrics train_xgboost(const std::vector<OrderBookFeatures> &features,
                             const std::vector<TradeOutcome> &outcomes);

  ModelMetrics train_transformer(const std::vector<OrderBookFeatures> &features,
                                 const std::vector<TradeOutcome> &outcomes);

  std::shared_ptr<DataCollector> collector_;
};

} // namespace ml
} // namespace trade
