#include "ml/TrainingValidation.hpp"
#include "ml/Metrics.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace trade {
namespace ml {
namespace {

double feature_at(const OrderBookFeatures &f, std::size_t index) {
  switch (index) {
  case 0: return f.bid_ask_imbalance;
  case 1: return f.spread_percent;
  case 2: return f.mid_price;
  case 3: return f.bid_volume;
  case 4: return f.ask_volume;
  case 5: return static_cast<double>(f.order_book_depth);
  case 6: return f.large_bid_wall ? 1.0 : 0.0;
  case 7: return f.large_ask_wall ? 1.0 : 0.0;
  case 8: return f.wall_size;
  case 9: return f.volume_weighted_price;
  case 10: return f.price_momentum;
  case 11: return f.volatility;
  case 12: return f.volume_24h;
  case 13: return f.prev_win_probability;
  case 14: return f.prev_expected_return;
  case 15: return f.prev_confidence;
  default: return 0.0;
  }
}

double pearson(const std::vector<double> &x, const std::vector<double> &y) {
  if (x.size() != y.size() || x.size() < 2) {
    return 0.0;
  }
  const double n = static_cast<double>(x.size());
  const double mean_x = std::accumulate(x.begin(), x.end(), 0.0) / n;
  const double mean_y = std::accumulate(y.begin(), y.end(), 0.0) / n;
  double cov = 0.0;
  double var_x = 0.0;
  double var_y = 0.0;
  for (std::size_t i = 0; i < x.size(); ++i) {
    const double dx = x[i] - mean_x;
    const double dy = y[i] - mean_y;
    cov += dx * dy;
    var_x += dx * dx;
    var_y += dy * dy;
  }
  const double denom = std::sqrt(var_x * var_y);
  return denom > 0.0 ? cov / denom : 0.0;
}

} // namespace

std::vector<std::pair<OrderBookFeatures, TradeOutcome>> sort_training_samples_chronologically(
    std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples) {
  std::sort(samples.begin(), samples.end(), [](const auto &lhs, const auto &rhs) {
    if (lhs.first.timestamp != rhs.first.timestamp) {
      return lhs.first.timestamp < rhs.first.timestamp;
    }
    if (lhs.second.entry_timestamp != rhs.second.entry_timestamp) {
      return lhs.second.entry_timestamp < rhs.second.entry_timestamp;
    }
    return lhs.first.symbol < rhs.first.symbol;
  });
  return samples;
}

ModelMetrics summarize_trade_outcomes(const std::vector<TradeOutcome> &outcomes) {
  ModelMetrics metrics{};
  if (outcomes.empty()) {
    return metrics;
  }

  std::vector<int> y_true;
  std::vector<int> y_pred;
  std::vector<double> pnl;
  y_true.reserve(outcomes.size());
  y_pred.reserve(outcomes.size());
  pnl.reserve(outcomes.size());

  std::size_t wins = 0;
  for (const auto &outcome : outcomes) {
    if (outcome.is_win) {
      ++wins;
    }
  }
  const int majority_class = (wins * 2 >= outcomes.size()) ? 1 : 0;
  for (const auto &outcome : outcomes) {
    y_true.push_back(outcome.is_win ? 1 : 0);
    y_pred.push_back(majority_class);
    pnl.push_back(outcome.pnl - outcome.fees);
  }

  metrics.accuracy = Metrics::calculate_accuracy(y_true, y_pred);
  metrics.precision = Metrics::calculate_precision(y_true, y_pred);
  metrics.recall = Metrics::calculate_recall(y_true, y_pred);
  metrics.sharpe_ratio = Metrics::calculate_sharpe_ratio(pnl);
  metrics.profit_factor = Metrics::calculate_profit_factor(pnl);
  return metrics;
}

std::vector<WalkForwardFold> build_walk_forward_folds(
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &chronological_samples,
    double test_split,
    std::size_t max_folds) {
  std::vector<WalkForwardFold> folds;
  const std::size_t total = chronological_samples.size();
  if (total < 3 || max_folds == 0) {
    return folds;
  }

  const double bounded_split = std::clamp(test_split, 0.05, 0.5);
  const std::size_t test_size = std::max<std::size_t>(1, static_cast<std::size_t>(std::round(total * bounded_split)));
  if (test_size >= total) {
    return folds;
  }

  std::size_t first_test = total > test_size * max_folds ? total - test_size * max_folds : test_size;
  first_test = std::max<std::size_t>(1, first_test);

  for (std::size_t test_start = first_test; test_start < total && folds.size() < max_folds; test_start += test_size) {
    const std::size_t test_end = std::min(total, test_start + test_size);
    if (test_start == 0 || test_start >= test_end) {
      continue;
    }

    WalkForwardFold fold;
    fold.fold_index = folds.size() + 1;
    fold.train_start = 0;
    fold.train_end = test_start;
    fold.test_start = test_start;
    fold.test_end = test_end;
    fold.train_start_timestamp = chronological_samples.front().first.timestamp;
    fold.train_end_timestamp = chronological_samples[test_start - 1].first.timestamp;
    fold.test_start_timestamp = chronological_samples[test_start].first.timestamp;
    fold.test_end_timestamp = chronological_samples[test_end - 1].first.timestamp;

    std::vector<TradeOutcome> outcomes;
    outcomes.reserve(test_end - test_start);
    for (std::size_t i = test_start; i < test_end; ++i) {
      outcomes.push_back(chronological_samples[i].second);
    }
    fold.metrics = summarize_trade_outcomes(outcomes);
    fold.metrics.validation_strategy = "walk_forward_fold";
    folds.push_back(fold);
  }

  return folds;
}

std::vector<std::string> order_book_feature_names() {
  return {"bid_ask_imbalance", "spread_percent", "mid_price", "bid_volume",
          "ask_volume", "order_book_depth", "large_bid_wall", "large_ask_wall",
          "wall_size", "volume_weighted_price", "price_momentum", "volatility",
          "volume_24h", "prev_win_probability", "prev_expected_return",
          "prev_confidence"};
}

std::string order_book_feature_set_version() { return "order_book_features_v1"; }

std::vector<FeatureImportance> compute_feature_importance(
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &samples) {
  const auto names = order_book_feature_names();
  std::vector<double> pnl;
  pnl.reserve(samples.size());
  for (const auto &sample : samples) {
    pnl.push_back(sample.second.pnl - sample.second.fees);
  }

  std::vector<FeatureImportance> importances;
  importances.reserve(names.size());
  for (std::size_t index = 0; index < names.size(); ++index) {
    std::vector<double> values;
    values.reserve(samples.size());
    for (const auto &sample : samples) {
      values.push_back(feature_at(sample.first, index));
    }
    const double corr = pearson(values, pnl);
    importances.push_back({names[index], index, std::abs(corr), corr});
  }
  std::sort(importances.begin(), importances.end(), [](const auto &lhs, const auto &rhs) {
    if (std::abs(lhs.importance - rhs.importance) > 1e-12) {
      return lhs.importance > rhs.importance;
    }
    return lhs.index < rhs.index;
  });
  return importances;
}

void to_json(nlohmann::json &j, const WalkForwardFold &f) {
  j = nlohmann::json{{"fold_index", f.fold_index},
                     {"train_start", f.train_start},
                     {"train_end", f.train_end},
                     {"test_start", f.test_start},
                     {"test_end", f.test_end},
                     {"train_start_timestamp", f.train_start_timestamp},
                     {"train_end_timestamp", f.train_end_timestamp},
                     {"test_start_timestamp", f.test_start_timestamp},
                     {"test_end_timestamp", f.test_end_timestamp},
                     {"metrics", f.metrics}};
}

void to_json(nlohmann::json &j, const FeatureImportance &f) {
  j = nlohmann::json{{"name", f.name},
                     {"index", f.index},
                     {"importance", f.importance},
                     {"correlation_to_pnl", f.correlation_to_pnl}};
}

} // namespace ml
} // namespace trade
