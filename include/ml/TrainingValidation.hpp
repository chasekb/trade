#pragma once

#include "ml/DataCollector.hpp"
#include "ml/ModelTrainer.hpp"

#include <cstddef>
#include <nlohmann/json.hpp>
#include <string>
#include <utility>
#include <vector>

namespace trade {
namespace ml {

struct WalkForwardFold {
  std::size_t fold_index = 0;
  std::size_t train_start = 0;
  std::size_t train_end = 0;
  std::size_t test_start = 0;
  std::size_t test_end = 0;
  long long train_start_timestamp = 0;
  long long train_end_timestamp = 0;
  long long test_start_timestamp = 0;
  long long test_end_timestamp = 0;
  ModelMetrics metrics;
};

struct FeatureImportance {
  std::string name;
  std::size_t index = 0;
  double importance = 0.0;
  double correlation_to_pnl = 0.0;
};

std::vector<std::pair<OrderBookFeatures, TradeOutcome>> sort_training_samples_chronologically(
    std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples);

std::vector<WalkForwardFold> build_walk_forward_folds(
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &chronological_samples,
    double test_split,
    std::size_t max_folds = 5);

ModelMetrics summarize_trade_outcomes(const std::vector<TradeOutcome> &outcomes);

std::vector<FeatureImportance> compute_feature_importance(
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &samples);

std::vector<std::string> order_book_feature_names();
std::string order_book_feature_set_version();

void to_json(nlohmann::json &j, const WalkForwardFold &f);
void to_json(nlohmann::json &j, const FeatureImportance &f);

} // namespace ml
} // namespace trade
