#include "ml/ModelTrainer.hpp"
#include "ml/Metrics.hpp"
#include "ml/ExecutionCohorts.hpp"
#include "ml/TransformerOnnxExport.hpp"
#include "ml/TransformerModel.hpp"
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cmath>
#include <random>
#include <stdexcept>
#include <spdlog/spdlog.h>
#include <utility>
#include <tuple>

// Note: Requires mlpack, xgboost, and torch headers - assuming they are in the
// include path #include <mlpack/methods/random_forest/random_forest.hpp>
// #include <xgboost/c_api.h>

namespace {
constexpr int64_t kTransformerLookback = 60;
constexpr int64_t kTransformerPatchSize = 5;
constexpr int64_t kTransformerEmbeddingDim = 64;
constexpr int64_t kTransformerHeads = 4;
constexpr int64_t kTransformerLayers = 3;
constexpr double kTransformerDropout = 0.1;
constexpr int kTransformerOpsetVersion = 13;

void write_transformer_config(const std::filesystem::path &config_path,
                              int64_t input_features) {
  nlohmann::json config = {
      {"n_features", input_features},
      {"lookback", kTransformerLookback},
      {"patch_size", kTransformerPatchSize},
      {"embedding_dim", kTransformerEmbeddingDim},
      {"n_heads", kTransformerHeads},
      {"n_layers", kTransformerLayers},
      {"dropout", kTransformerDropout},
      {"opset_version", kTransformerOpsetVersion},
      {"input_layout", "channels_last"}};

  if (!config_path.parent_path().empty()) {
    std::filesystem::create_directories(config_path.parent_path());
  }
  std::ofstream out(config_path);
  if (!out.is_open()) {
    throw std::runtime_error("Failed to open transformer config path: " +
                             config_path.string());
  }
  out << config.dump(2);
}

} // namespace

namespace trade {
namespace ml {

ModelTrainer::ModelTrainer(std::shared_ptr<DataCollector> collector)
    : collector_(collector) {}

ModelMetrics ModelTrainer::train(const TrainingConfig &config) {
  ModelMetrics metrics;

  if (!collector_) {
    spdlog::error("ModelTrainer: data collector is not configured");
    return metrics;
  }

  const int sync_batch_size = std::max(1000, config.batch_size);
  const std::size_t synced =
      collector_->sync_training_inputs(config.days_back, sync_batch_size);
  const std::size_t available = collector_->count_training_inputs(config.days_back);

  spdlog::info(
      "ModelTrainer: training-input sync inserted={} available={} days_back={}"
      " batch_size={}",
      synced, available, config.days_back, sync_batch_size);

  if (available == 0) {
    spdlog::warn("ModelTrainer: no persisted training inputs available");
    return metrics;
  }

  bool use_batch = config.batch_training;
  if (use_batch && available <= 20000) {
    spdlog::info(
        "ModelTrainer: disabling batch mode for {} samples (<= 20000); using"
        " single-load path",
        available);
    use_batch = false;
  }

  if (use_batch) {
    const int batch_rows = std::max(1, config.batch_size);
    spdlog::info(
        "ModelTrainer: batch_training enabled, streaming unlimited rows in batches of {}",
        batch_rows);

    struct PnlStats {
      std::size_t count = 0;
      double sum = 0.0;
      double sum_sq = 0.0;
      double gross_profit = 0.0;
      double gross_loss = 0.0;
    };

    auto update_pnl_stats = [](PnlStats &stats, double pnl) {
      ++stats.count;
      stats.sum += pnl;
      stats.sum_sq += pnl * pnl;
      if (pnl > 0.0) {
        stats.gross_profit += pnl;
      } else if (pnl < 0.0) {
        stats.gross_loss += std::abs(pnl);
      }
    };

    auto finalize_trading_metrics = [&](const PnlStats &stats) {
      if (stats.count == 0) {
        return;
      }

      const double n = static_cast<double>(stats.count);
      const double mean = stats.sum / n;
      const double variance = std::max(0.0, (stats.sum_sq / n) - (mean * mean));
      const double std_dev = std::sqrt(variance);
      metrics.sharpe_ratio =
          std_dev > 0.0 ? (mean / std_dev) * std::sqrt(252.0) : 0.0;

      if (stats.gross_loss == 0.0) {
        metrics.profit_factor = stats.gross_profit > 0.0 ? 999.0 : 0.0;
      } else {
        metrics.profit_factor = stats.gross_profit / stats.gross_loss;
      }
    };

    switch (config.type) {
    case ModelType::RANDOM_FOREST: {
      std::size_t total = 0;
      std::size_t wins = 0;
      PnlStats pnl_stats;
      int batch_index = 0;

      for (int offset = 0;; offset += batch_rows) {
        auto batch =
            collector_->extract_training_pairs_batch(config.days_back, batch_rows,
                                                     offset);
        if (batch.empty()) {
          break;
        }

        ++batch_index;
        spdlog::info(
            "ModelTrainer: [RF batch {}] offset={} rows={} processed_before={}",
            batch_index, offset, batch.size(), total);

        for (const auto &sample : batch) {
          ++total;
          if (sample.second.is_win) {
            ++wins;
          }
          update_pnl_stats(pnl_stats, sample.second.pnl);
          update_execution_cohort(cohort_accumulators, sample.first, sample.second);
        }
      }

      if (total == 0) {
        spdlog::warn("ModelTrainer: no training data found (no matched signals)");
        return metrics;
      }

      const int majority_class = (wins * 2 >= total) ? 1 : 0;
      const double total_d = static_cast<double>(total);
      const double wins_d = static_cast<double>(wins);
      const double losses_d = static_cast<double>(total - wins);

      if (majority_class == 1) {
        metrics.accuracy = wins_d / total_d;
        metrics.precision = wins_d / total_d;
        metrics.recall = wins > 0 ? 1.0 : 0.0;
      } else {
        metrics.accuracy = losses_d / total_d;
        metrics.precision = 0.0;
        metrics.recall = 0.0;
      }

      finalize_trading_metrics(pnl_stats);
      metrics.validation_strategy = "streaming_batch";
      metrics.cohort_metrics = finalize_execution_cohorts(cohort_accumulators);
      return metrics;
    }
    case ModelType::GRADIENT_BOOSTING: {
      std::size_t total = 0;
      std::size_t true_positives = 0;
      std::size_t predicted_positives = 0;
      std::size_t actual_positives = 0;
      std::size_t correct = 0;
      PnlStats pnl_stats;
      int batch_index = 0;

      for (int offset = 0;; offset += batch_rows) {
        auto batch =
            collector_->extract_training_pairs_batch(config.days_back, batch_rows,
                                                     offset);
        if (batch.empty()) {
          break;
        }

        ++batch_index;
        spdlog::info(
            "ModelTrainer: [GB batch {}] offset={} rows={} processed_before={}",
            batch_index, offset, batch.size(), total);

        for (const auto &sample : batch) {
          const bool actual = sample.second.is_win;
          const bool predicted = sample.first.bid_ask_imbalance > 0.0;

          ++total;
          if (actual)
            ++actual_positives;
          if (predicted)
            ++predicted_positives;
          if (actual && predicted)
            ++true_positives;
          if (actual == predicted)
            ++correct;

          update_pnl_stats(pnl_stats, sample.second.pnl);
          update_execution_cohort(cohort_accumulators, sample.first, sample.second);
        }
      }

      if (total == 0) {
        spdlog::warn("ModelTrainer: no training data found (no matched signals)");
        return metrics;
      }

      metrics.accuracy = static_cast<double>(correct) / static_cast<double>(total);
      metrics.precision =
          predicted_positives > 0
              ? static_cast<double>(true_positives) /
                    static_cast<double>(predicted_positives)
              : 0.0;
      metrics.recall =
          actual_positives > 0
              ? static_cast<double>(true_positives) /
                    static_cast<double>(actual_positives)
              : 0.0;

      finalize_trading_metrics(pnl_stats);
      metrics.validation_strategy = "streaming_batch";
      metrics.cohort_metrics = finalize_execution_cohorts(cohort_accumulators);
      return metrics;
    }
    case ModelType::TRANSFORMER: {
      std::size_t count = 0;
      double sum_x = 0.0;
      double sum_y = 0.0;
      double sum_xx = 0.0;
      double sum_xy = 0.0;
      PnlStats pnl_stats;
      int pass1_batch_index = 0;

      for (int offset = 0;; offset += batch_rows) {
        auto batch =
            collector_->extract_training_pairs_batch(config.days_back, batch_rows,
                                                     offset);
        if (batch.empty()) {
          break;
        }

        ++pass1_batch_index;
        spdlog::info(
            "ModelTrainer: [TF pass1 batch {}] offset={} rows={} processed_before={}",
            pass1_batch_index, offset, batch.size(), count);

        for (const auto &sample : batch) {
          const double x = sample.first.bid_ask_imbalance;
          const double y = sample.second.pnl;
          ++count;
          sum_x += x;
          sum_y += y;
          sum_xx += x * x;
          sum_xy += x * y;
          update_pnl_stats(pnl_stats, y);
          update_execution_cohort(cohort_accumulators, sample.first, sample.second);
        }
      }

      if (count == 0) {
        spdlog::warn("ModelTrainer: no training data found (no matched signals)");
        return metrics;
      }

      const double n = static_cast<double>(count);
      double slope = 0.0;
      double intercept = 0.0;
      const double denom = n * sum_xx - sum_x * sum_x;
      if (denom != 0.0) {
        slope = (n * sum_xy - sum_x * sum_y) / denom;
        intercept = (sum_y - slope * sum_x) / n;
      } else {
        intercept = sum_y / n;
      }

      const double mean_y = sum_y / n;
      double ss_res = 0.0;
      double ss_tot = 0.0;
      int pass2_batch_index = 0;

      for (int offset = 0;; offset += batch_rows) {
        auto batch =
            collector_->extract_training_pairs_batch(config.days_back, batch_rows,
                                                     offset);
        if (batch.empty()) {
          break;
        }

        ++pass2_batch_index;
        spdlog::info(
            "ModelTrainer: [TF pass2 batch {}] offset={} rows={}",
            pass2_batch_index, offset, batch.size());

        for (const auto &sample : batch) {
          const double x = sample.first.bid_ask_imbalance;
          const double y = sample.second.pnl;
          const double pred = intercept + slope * x;
          const double diff_res = y - pred;
          const double diff_tot = y - mean_y;
          ss_res += diff_res * diff_res;
          ss_tot += diff_tot * diff_tot;
        }
      }

      metrics.mse = ss_res / n;
      metrics.r2_score = ss_tot == 0.0 ? 0.0 : 1.0 - (ss_res / ss_tot);

      finalize_trading_metrics(pnl_stats);
      metrics.validation_strategy = "streaming_batch";
      metrics.cohort_metrics = finalize_execution_cohorts(cohort_accumulators);
      return metrics;
    }
    default:
      spdlog::warn("ModelTrainer: unsupported model type {}",
                   static_cast<int>(config.type));
      return metrics;
    }
  }

  int extraction_limit = static_cast<int>(available);
  if (config.max_training_rows > 0) {
    extraction_limit = std::min(extraction_limit, config.max_training_rows);
    spdlog::info(
        "ModelTrainer: non-batch training extraction limit set to {} per dataset",
        extraction_limit);
  }

  // 1. Fetch already persisted/matched training inputs from cache table
  auto paired_data =
      collector_->extract_training_pairs_batch(config.days_back, extraction_limit, 0);

  spdlog::info("ModelTrainer: loaded {} persisted training pairs",
               paired_data.size());

  if (paired_data.empty()) {
    spdlog::warn("ModelTrainer: no persisted training pairs found");
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

  std::vector<std::pair<OrderBookFeatures, TradeOutcome>> validation_samples;
  validation_samples.reserve(test_features.size());
  for (size_t i = 0; i < test_features.size(); ++i) {
    validation_samples.emplace_back(test_features[i], test_outcomes[i]);
  }

  std::map<std::string, ExecutionCohortAccumulator> cohort_accumulators;

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

  metrics.validation_strategy = "random_split";
  metrics.cohort_metrics = summarize_execution_cohorts(std::move(validation_samples));
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

void ModelTrainer::export_transformer_artifact(
    const std::filesystem::path &output_path, int64_t input_features) const {
  const auto onnx_path = output_path;
  const auto config_path = onnx_path.parent_path() / "transformer_config.json";

  export_transformer_to_onnx(onnx_path, input_features);
  write_transformer_config(config_path, input_features);

  spdlog::info("Transformer model package prepared at {}",
               onnx_path.parent_path().string());
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
  (void)path;
  spdlog::warn("save_model is not implemented in the lightweight trainer build");
}

void ModelTrainer::load_model(const std::string &path) {
  (void)path;
  spdlog::warn("load_model is not implemented in the lightweight trainer build");
}

} // namespace ml
} // namespace trade
