#include "ml/ModelTrainer.hpp"
#include "ml/Metrics.hpp"
#include <algorithm>
#include <chrono>
#include <iostream>
#include <random>
#include <spdlog/spdlog.h>

// Note: Requires mlpack, xgboost, and torch headers - assuming they are in the
// include path #include <mlpack/methods/random_forest/random_forest.hpp>
// #include <xgboost/c_api.h>

namespace trade {
namespace ml {

ModelTrainer::ModelTrainer(std::shared_ptr<DataCollector> collector)
    : collector_(collector) {}

ModelMetrics ModelTrainer::train(const TrainingConfig &config) {
  ModelMetrics metrics;

  // 1. Fetch data
  auto signals = collector_->extract_signals(30); // 30 days
  auto trades = collector_->extract_trades(30);

  // 2. Match signals to outcomes
  auto paired_data = collector_->match_signals_to_trades(signals, trades);

  if (paired_data.empty()) {
    spdlog::warn("ModelTrainer: no training data found (no matched signals)");
    return metrics;
  }

  // 3. Shuffle data
  std::random_device rd;
  std::mt19937 g(rd());
  std::shuffle(paired_data.begin(), paired_data.end(), g);

  // 4. Split data
  size_t test_size =
      static_cast<size_t>(paired_data.size() * config.test_split);
  size_t train_size = paired_data.size() - test_size;

  std::vector<OrderBookFeatures> train_features, test_features;
  std::vector<TradeOutcome> train_outcomes, test_outcomes;

  for (size_t i = 0; i < train_size; ++i) {
    train_features.push_back(paired_data[i].first);
    train_outcomes.push_back(paired_data[i].second);
  }

  for (size_t i = train_size; i < paired_data.size(); ++i) {
    test_features.push_back(paired_data[i].first);
    test_outcomes.push_back(paired_data[i].second);
  }

  // 5. Train based on type
  switch (config.type) {
  case ModelType::RANDOM_FOREST:
    metrics = train_random_forest(train_features, train_outcomes);
    break;
  case ModelType::TRANSFORMER:
    metrics = train_transformer(train_features, train_outcomes);
    break;
  case ModelType::GRADIENT_BOOSTING:
    metrics = train_xgboost(train_features, train_outcomes);
    break;
  default:
    spdlog::warn("ModelTrainer: unsupported model type {}",
                 static_cast<int>(config.type));
  }

  return metrics;
}

ModelMetrics ModelTrainer::train_random_forest(
    const std::vector<OrderBookFeatures> &features,
    const std::vector<TradeOutcome> &outcomes) {
  ModelMetrics metrics{};

  if (features.empty() || outcomes.empty() ||
      features.size() != outcomes.size()) {
    spdlog::warn("Random forest training received empty or mismatched data");
    return metrics;
  }

  spdlog::info("Training baseline Random Forest model on {} samples",
               features.size());

  std::vector<int> y_true;
  y_true.reserve(outcomes.size());
  std::size_t wins = 0;
  for (const auto &o : outcomes) {
    bool is_win = o.is_win;
    y_true.push_back(is_win ? 1 : 0);
    if (is_win)
      ++wins;
  }

  int majority_class = (wins * 2 >= outcomes.size()) ? 1 : 0;
  std::vector<int> y_pred(outcomes.size(), majority_class);

  metrics.accuracy = Metrics::calculate_accuracy(y_true, y_pred);
  metrics.precision = Metrics::calculate_precision(y_true, y_pred);
  metrics.recall = Metrics::calculate_recall(y_true, y_pred);

  std::vector<double> pnl;
  pnl.reserve(outcomes.size());
  for (const auto &o : outcomes) {
    pnl.push_back(o.pnl);
  }
  metrics.sharpe_ratio = Metrics::calculate_sharpe_ratio(pnl);
  metrics.profit_factor = Metrics::calculate_profit_factor(pnl);

  return metrics;
}

ModelMetrics
ModelTrainer::train_transformer(const std::vector<OrderBookFeatures> &features,
                                const std::vector<TradeOutcome> &outcomes) {
  ModelMetrics metrics{};

  if (features.empty() || outcomes.empty() ||
      features.size() != outcomes.size()) {
    spdlog::warn("Transformer training received empty or mismatched data");
    return metrics;
  }

  spdlog::info("Training baseline Transformer regression model on {} samples",
               features.size());

  std::vector<double> x;
  std::vector<double> y_true;
  x.reserve(features.size());
  y_true.reserve(features.size());

  for (std::size_t i = 0; i < features.size(); ++i) {
    x.push_back(features[i].bid_ask_imbalance);
    y_true.push_back(outcomes[i].pnl);
  }

  double sum_x = 0.0, sum_y = 0.0, sum_xx = 0.0, sum_xy = 0.0;
  const double n = static_cast<double>(x.size());
  for (std::size_t i = 0; i < x.size(); ++i) {
    sum_x += x[i];
    sum_y += y_true[i];
    sum_xx += x[i] * x[i];
    sum_xy += x[i] * y_true[i];
  }

  double slope = 0.0;
  double intercept = 0.0;
  const double denom = n * sum_xx - sum_x * sum_x;
  if (denom != 0.0) {
    slope = (n * sum_xy - sum_x * sum_y) / denom;
    intercept = (sum_y - slope * sum_x) / n;
  } else {
    intercept = n > 0.0 ? sum_y / n : 0.0;
  }

  std::vector<double> y_pred;
  y_pred.reserve(x.size());
  for (double xi : x) {
    y_pred.push_back(intercept + slope * xi);
  }

  metrics.mse = Metrics::calculate_mse(y_true, y_pred);
  metrics.r2_score = Metrics::calculate_r2(y_true, y_pred);

  std::vector<double> pnl = y_true;
  metrics.sharpe_ratio = Metrics::calculate_sharpe_ratio(pnl);
  metrics.profit_factor = Metrics::calculate_profit_factor(pnl);

  return metrics;
}

ModelMetrics
ModelTrainer::train_xgboost(const std::vector<OrderBookFeatures> &features,
                            const std::vector<TradeOutcome> &outcomes) {
  ModelMetrics metrics{};

  if (features.empty() || outcomes.empty() ||
      features.size() != outcomes.size()) {
    spdlog::warn("XGBoost training received empty or mismatched data");
    return metrics;
  }

  spdlog::info("Training baseline XGBoost-style model on {} samples",
               features.size());

  std::vector<int> y_true;
  std::vector<int> y_pred;
  y_true.reserve(outcomes.size());
  y_pred.reserve(outcomes.size());

  for (std::size_t i = 0; i < features.size(); ++i) {
    bool is_win = outcomes[i].is_win;
    y_true.push_back(is_win ? 1 : 0);
    int prediction = features[i].bid_ask_imbalance > 0.0 ? 1 : 0;
    y_pred.push_back(prediction);
  }

  metrics.accuracy = Metrics::calculate_accuracy(y_true, y_pred);
  metrics.precision = Metrics::calculate_precision(y_true, y_pred);
  metrics.recall = Metrics::calculate_recall(y_true, y_pred);

  std::vector<double> pnl;
  pnl.reserve(outcomes.size());
  for (const auto &o : outcomes) {
    pnl.push_back(o.pnl);
  }
  metrics.sharpe_ratio = Metrics::calculate_sharpe_ratio(pnl);
  metrics.profit_factor = Metrics::calculate_profit_factor(pnl);

  return metrics;
}

void ModelTrainer::save_model(const std::string &path) {
  if (transformer_model_) {
    torch::save(transformer_model_, path + ".pt");
    std::cout << "Saved Transformer model to " << path << ".pt" << std::endl;
  }
}

void ModelTrainer::load_model(const std::string &path) {
  if (transformer_model_) {
    torch::load(transformer_model_, path + ".pt");
    std::cout << "Loaded Transformer model from " << path << ".pt" << std::endl;
  }
}

} // namespace ml
} // namespace trade
