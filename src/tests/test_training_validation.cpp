#include "ml/TrainingValidation.hpp"

#include <cmath>
#include <iostream>
#include <string>

using trade::ml::OrderBookFeatures;
using trade::ml::TradeOutcome;

namespace {

OrderBookFeatures features(long long timestamp, double imbalance, double spread) {
  OrderBookFeatures f{};
  f.timestamp = timestamp;
  f.symbol = "BTC-USD";
  f.bid_ask_imbalance = imbalance;
  f.spread_percent = spread;
  f.mid_price = 100.0;
  f.bid_volume = 1000.0 + imbalance * 100.0;
  f.ask_volume = 900.0;
  f.order_book_depth = 10;
  f.large_bid_wall = imbalance > 0.0;
  f.large_ask_wall = imbalance < 0.0;
  f.wall_size = std::abs(imbalance) * 1000.0;
  f.volume_weighted_price = 100.0 + imbalance;
  f.price_momentum = imbalance;
  f.volatility = 0.2;
  f.volume_24h = 2e9;
  f.prev_win_probability = 0.5 + imbalance * 0.1;
  f.prev_expected_return = imbalance * 0.01;
  f.prev_confidence = std::abs(imbalance);
  return f;
}

TradeOutcome outcome(const std::string &id, long long timestamp, double pnl) {
  TradeOutcome t{};
  t.trade_id = id;
  t.symbol = "BTC-USD";
  t.side = "buy";
  t.entry_price = 100.0;
  t.exit_price = 100.0 + pnl;
  t.quantity = 1.0;
  t.pnl = pnl;
  t.fees = 0.1;
  t.entry_timestamp = timestamp;
  t.exit_timestamp = timestamp + 60;
  t.is_win = pnl > 0.0;
  return t;
}

} // namespace

int main() {
  std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples = {
      {features(300, -0.3, 0.001), outcome("t3", 300, -3.0)},
      {features(100, 0.1, 0.0005), outcome("t1", 100, 1.0)},
      {features(200, 0.2, 0.0007), outcome("t2", 200, 2.0)},
      {features(400, 0.4, 0.0004), outcome("t4", 400, 4.0)},
      {features(500, 0.5, 0.0003), outcome("t5", 500, 5.0)},
  };

  const auto chronological = trade::ml::sort_training_samples_chronologically(samples);
  for (std::size_t i = 1; i < chronological.size(); ++i) {
    if (chronological[i - 1].first.timestamp > chronological[i].first.timestamp) {
      std::cerr << "samples not sorted chronologically" << std::endl;
      return 1;
    }
  }

  const auto folds = trade::ml::build_walk_forward_folds(chronological, 0.2, 3);
  if (folds.empty()) {
    std::cerr << "expected walk-forward folds" << std::endl;
    return 1;
  }
  for (const auto &fold : folds) {
    if (!(fold.train_end <= fold.test_start)) {
      std::cerr << "fold leaks future samples into training" << std::endl;
      return 1;
    }
    if (!(fold.train_end_timestamp < fold.test_start_timestamp)) {
      std::cerr << "fold timestamp order is not chronological" << std::endl;
      return 1;
    }
    if (fold.metrics.validation_strategy != "walk_forward_fold") {
      std::cerr << "fold metrics missing validation strategy" << std::endl;
      return 1;
    }
  }

  const auto names = trade::ml::order_book_feature_names();
  const auto importances = trade::ml::compute_feature_importance(chronological);
  if (importances.size() != names.size()) {
    std::cerr << "feature importance/name count mismatch" << std::endl;
    return 1;
  }
  bool found_imbalance = false;
  for (const auto &importance : importances) {
    if (importance.name == "bid_ask_imbalance" && importance.index == 0) {
      found_imbalance = true;
    }
  }
  if (!found_imbalance) {
    std::cerr << "stable feature name/index mapping missing bid_ask_imbalance" << std::endl;
    return 1;
  }

  nlohmann::json artifact = importances;
  if (!artifact.is_array() || artifact.empty() || !artifact.front().contains("importance")) {
    std::cerr << "feature importance artifact is not JSON serializable" << std::endl;
    return 1;
  }

  return 0;
}
