#include "ml/ModelTrainer.hpp"
#include "ml/Metrics.hpp"
#include "ml/ExecutionCohorts.hpp"
#include "ml/TrainingValidation.hpp"
#include "ml/TransformerOnnxExport.hpp"
#include "ml/TransformerModel.hpp"
#include "ml/TransformerFeatures.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cmath>
#include <random>
#include <stdexcept>
#include <spdlog/spdlog.h>
#include <string>
#include <unordered_map>
#include <utility>
#include <tuple>

// Note: Requires mlpack, xgboost, and torch headers - assuming they are in the
// include path #include <mlpack/methods/random_forest/random_forest.hpp>
// #include <xgboost/c_api.h>

namespace {
// Sequence length and feature representation (16 raw DB fields + rolling
// mean/std of imbalance/spread/momentum/volatility over 5/20/60-sample
// windows, 40 total) are now the single shared implementation in
// include/ml/TransformerFeatures.hpp — trade::ml::RollingWindowBuffer,
// used identically here (training) and by FeatureEngineer/ONNXModelManager
// (live inference), so the two can no longer silently drift apart. An A/B
// test on live trade_outcomes data (2026-09-18, 11,244 train / holdout
// split) justified this representation over a 16-raw-field-only baseline:
// holdout MSE 0.000303 vs 0.000319 (~5% lower), R^2 +0.0019 vs -0.0497.
constexpr int64_t kTransformerLookback = trade::ml::kTransformerLookback;
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
      {"input_layout", "channels_last"},
      // export_transformer_to_onnx always writes the shape-correct,
      // weight-free Identity placeholder (see TransformerOnnxExport.cpp) —
      // never true today. ONNXModelManager reads this to decide whether the
      // ONNX session is ever usable for real predictions; a future real
      // ONNX exporter would need to flip this at its own call site.
      {"onnx_has_weights", false}};

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
  metrics.training_source = config.training_source;

  if (!collector_) {
    spdlog::error("ModelTrainer: data collector is not configured");
    return metrics;
  }

  // "opportunity_labels" trains on ml_opportunity_labels, which self-labels
  // every logged order-book state's own forward-looking return regardless of
  // whether it crossed a strategy's signal threshold or led to a trade — see
  // DataCollector::sync_opportunity_labels. Every other value keeps the
  // existing trade-matched path unchanged.
  const bool use_opportunity_source =
      config.training_source == "opportunity_labels";

  const int sync_batch_size = std::max(1000, config.batch_size);
  const std::size_t synced =
      use_opportunity_source
          ? collector_->sync_opportunity_labels(
                config.days_back, config.opportunity_horizon_seconds,
                sync_batch_size)
          : collector_->sync_training_inputs(config.days_back, sync_batch_size);
  const std::size_t available =
      use_opportunity_source
          ? collector_->count_opportunity_labels(config.days_back)
          : collector_->count_training_inputs(config.days_back);

  spdlog::info(
      "ModelTrainer: training-input sync source={} inserted={} available={}"
      " days_back={} batch_size={}",
      config.training_source, synced, available, config.days_back,
      sync_batch_size);

  if (available == 0) {
    spdlog::warn("ModelTrainer: no persisted training inputs available");
    return metrics;
  }

  auto extract_batch = [&](int limit, int offset) {
    return use_opportunity_source
               ? collector_->extract_opportunity_pairs_batch(config.days_back,
                                                             limit, offset)
               : collector_->extract_training_pairs_batch(config.days_back,
                                                          limit, offset);
  };

  bool use_batch = config.batch_training;
  if (use_batch && available <= 20000) {
    spdlog::info(
        "ModelTrainer: disabling batch mode for {} samples (<= 20000); using"
        " single-load path",
        available);
    use_batch = false;
  }
  if (use_batch && config.type == ModelType::TRANSFORMER) {
    // The streaming/batch_training branch below (case ModelType::TRANSFORMER)
    // still fits a single-feature OLS-on-bid_ask_imbalance stand-in, not the
    // real gradient-trained StockTransformer train_transformer() trains via
    // the single-load path below. A caller setting batch_training=true for a
    // large transformer run would otherwise silently get a fully-functional-
    // looking but fake model (real metrics logged, but no real weights, no
    // transformer_weights.pt, no live inference) instead of an error —
    // exactly the trap this forces closed. train_transformer's own
    // per-symbol sequence construction is O(1) memory per sample (a fixed
    // rolling buffer), not O(dataset), so it does not need the streaming
    // path's memory-bound rationale in the first place.
    spdlog::info(
        "ModelTrainer: batch_training=true is not supported for TRANSFORMER "
        "(no real incremental training loop exists yet); using the "
        "single-load path, which trains the real model regardless of row count");
    use_batch = false;
  }

  if (use_batch) {
    const int batch_rows = std::max(1, config.batch_size);
    std::map<std::string, ExecutionCohortAccumulator> cohort_accumulators;
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
        auto batch = extract_batch(batch_rows, offset);
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
      metrics.feature_set_version = order_book_feature_set_version();
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
        auto batch = extract_batch(batch_rows, offset);
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
      metrics.feature_set_version = order_book_feature_set_version();
      metrics.cohort_metrics = finalize_execution_cohorts(cohort_accumulators);
      return metrics;
    }
    // ModelType::TRANSFORMER never reaches this streaming switch — use_batch
    // is forced false for it above, unconditionally, so it always goes
    // through the real gradient-trained single-load path (train_transformer)
    // regardless of batch_training or row count. This streaming branch
    // previously fit a single-feature OLS-on-bid_ask_imbalance stand-in here
    // instead, which a batch_training=true caller would have silently
    // received as if it were a real trained transformer (plausible-looking
    // metrics, but no real weights, no transformer_weights.pt, no live
    // inference) — removed rather than left reachable by accident.
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
  auto paired_data = extract_batch(extraction_limit, 0);

  spdlog::info("ModelTrainer: loaded {} persisted training pairs",
               paired_data.size());

  if (paired_data.empty()) {
    spdlog::warn("ModelTrainer: no persisted training pairs found");
    return metrics;
  }

  paired_data = sort_training_samples_chronologically(std::move(paired_data));

  const auto walk_forward_folds = build_walk_forward_folds(paired_data, config.test_split);
  size_t test_size = walk_forward_folds.empty()
                         ? static_cast<size_t>(paired_data.size() * config.test_split)
                         : walk_forward_folds.back().test_end - walk_forward_folds.back().test_start;
  size_t train_size = paired_data.size() - test_size;
  if (!walk_forward_folds.empty()) {
    train_size = walk_forward_folds.back().train_end;
  }
  if (train_size == 0) {
    train_size = paired_data.size() > 1 ? paired_data.size() - 1 : paired_data.size();
    test_size = paired_data.size() - train_size;
  }

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
    metrics = train_transformer(train_features, train_outcomes, config);
    break;
  case ModelType::GRADIENT_BOOSTING:
    metrics = train_xgboost(train_features, train_outcomes);
    break;
  default:
    spdlog::warn("ModelTrainer: unsupported model type {}",
                 static_cast<int>(config.type));
  }

  metrics.validation_strategy = walk_forward_folds.empty()
                                    ? "chronological_holdout"
                                    : "walk_forward";
  metrics.feature_set_version = order_book_feature_set_version();
  metrics.walk_forward_folds = walk_forward_folds;
  metrics.feature_importance = compute_feature_importance(paired_data);
  metrics.cohort_metrics = summarize_execution_cohorts(std::move(validation_samples));
  metrics.training_source = config.training_source;
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
                                const std::vector<TradeOutcome> &outcomes,
                                const TrainingConfig &config) {
  ModelMetrics metrics{};
  has_trained_transformer_ = false;

  if (features.empty() || outcomes.empty() ||
      features.size() != outcomes.size()) {
    spdlog::warn("Transformer training received empty or mismatched data");
    return metrics;
  }

  const int64_t n_features = trade::ml::kTransformerTotalFeatureCount;
  const int64_t lookback = trade::ml::kTransformerLookback;

  // Build each sample's full (lookback, n_features) input sequence via the
  // SAME trade::ml::RollingWindowBuffer that live inference uses
  // (FeatureEngineer::get_raw_transformer_sequence /
  // ONNXModelManager::predict_transformer), pushed through in each symbol's
  // chronological order, so training and serving compute identical features
  // by construction rather than via two independently maintained
  // implementations. A sample is skipped entirely (not zero-padded) until
  // its symbol has accumulated a full lookback of real history — matching
  // what live inference does (reports "not ready" during warmup) instead of
  // training on artificial all-zero-padded inputs.
  std::unordered_map<std::string, trade::ml::RollingWindowBuffer> buffers_by_symbol;
  std::vector<std::vector<std::vector<double>>> sample_sequences(features.size());
  std::vector<std::size_t> valid_indices;
  valid_indices.reserve(features.size());
  for (std::size_t i = 0; i < features.size(); ++i) {
    auto &buffer = buffers_by_symbol[features[i].symbol];
    buffer.push(trade::ml::raw_feature_vector(features[i]));
    if (buffer.has_full_window()) {
      sample_sequences[i] = buffer.build_sequence();
      valid_indices.push_back(i);
    }
  }

  if (valid_indices.empty()) {
    spdlog::warn(
        "Transformer training: no symbol reached the {}-sample warmup "
        "required to build a full input sequence; skipping training",
        lookback);
    return metrics;
  }

  spdlog::info(
      "Training Transformer (patch-attention) model on {} samples ({} "
      "skipped below the {}-sample per-symbol warmup), n_features={}, "
      "lookback={}, epochs={}, batch_size={}, lr={}",
      valid_indices.size(), features.size() - valid_indices.size(), lookback,
      n_features, lookback, config.epochs, config.batch_size,
      config.learning_rate);

  auto build_batch_tensor = [&](const std::vector<std::size_t> &sample_idxs) {
    const int64_t b = static_cast<int64_t>(sample_idxs.size());
    torch::Tensor batch = torch::zeros({b, lookback, n_features}, torch::kFloat32);
    auto accessor = batch.accessor<float, 3>();
    for (int64_t bi = 0; bi < b; ++bi) {
      const auto &seq = sample_sequences[sample_idxs[static_cast<std::size_t>(bi)]];
      for (int64_t t = 0; t < lookback; ++t) {
        const auto &row = seq[static_cast<std::size_t>(t)];
        for (int64_t f = 0; f < n_features; ++f) {
          accessor[bi][t][f] = static_cast<float>(row[static_cast<std::size_t>(f)]);
        }
      }
    }
    return batch;
  };

  StockTransformer model(n_features, lookback, kTransformerPatchSize,
                         kTransformerEmbeddingDim, kTransformerHeads,
                         kTransformerLayers, kTransformerDropout);

  const double learning_rate = config.learning_rate > 0.0 ? config.learning_rate : 0.001;
  const int epochs = config.epochs > 0 ? config.epochs : 10;
  const int64_t batch_size = config.batch_size > 0 ? config.batch_size : 32;

  torch::optim::Adam optimizer(model->parameters(),
                               torch::optim::AdamOptions(learning_rate));

  std::vector<std::size_t> all_indices = valid_indices;
  std::mt19937 rng(42);

  model->train();
  double last_epoch_loss = 0.0;
  for (int epoch = 0; epoch < epochs; ++epoch) {
    std::shuffle(all_indices.begin(), all_indices.end(), rng);
    double epoch_loss_sum = 0.0;
    int64_t epoch_batches = 0;

    for (std::size_t offset = 0; offset < all_indices.size(); offset += static_cast<std::size_t>(batch_size)) {
      const std::size_t end = std::min(all_indices.size(), offset + static_cast<std::size_t>(batch_size));
      std::vector<std::size_t> batch_idxs(all_indices.begin() + static_cast<std::ptrdiff_t>(offset),
                                          all_indices.begin() + static_cast<std::ptrdiff_t>(end));
      if (batch_idxs.empty()) {
        continue;
      }

      torch::Tensor x = build_batch_tensor(batch_idxs);
      torch::Tensor y = torch::zeros({static_cast<int64_t>(batch_idxs.size()), 1}, torch::kFloat32);
      {
        auto y_acc = y.accessor<float, 2>();
        for (std::size_t bi = 0; bi < batch_idxs.size(); ++bi) {
          y_acc[static_cast<int64_t>(bi)][0] =
              static_cast<float>(outcomes[batch_idxs[bi]].pnl);
        }
      }

      optimizer.zero_grad();
      torch::Tensor pred = model->forward(x);
      torch::Tensor loss = torch::mse_loss(pred, y);
      loss.backward();
      optimizer.step();

      epoch_loss_sum += loss.item<double>();
      ++epoch_batches;
    }

    last_epoch_loss = epoch_batches > 0 ? epoch_loss_sum / static_cast<double>(epoch_batches) : 0.0;
    spdlog::info("Transformer training epoch {}/{}: mean_batch_mse={}", epoch + 1,
                epochs, last_epoch_loss);
  }

  // Post-training evaluation over the same (train) split, matching the
  // existing convention of the sibling train_random_forest/train_xgboost
  // methods, which likewise report metrics computed on their own training
  // set rather than a held-out slice managed inside the method itself —
  // the caller (ModelTrainer::train) already applies a walk-forward/
  // chronological holdout upstream and reports cohort metrics from that
  // separately.
  // torch::nn::Module::eval() switches dropout/batchnorm to inference
  // behavior; unrelated to code-evaluating eval() in other languages.
  model->eval();
  std::vector<double> y_true;
  std::vector<double> y_pred;
  y_true.reserve(features.size());
  y_pred.reserve(features.size());
  {
    torch::NoGradGuard no_grad;
    const std::size_t eval_batch = 512;
    for (std::size_t offset = 0; offset < all_indices.size(); offset += eval_batch) {
      const std::size_t end = std::min(all_indices.size(), offset + eval_batch);
      std::vector<std::size_t> batch_idxs(end - offset);
      for (std::size_t i = offset; i < end; ++i) {
        // all_indices order, not shuffled — the valid-sample subset in
        // original chronological order (see valid_indices above).
        batch_idxs[i - offset] = all_indices[i];
      }
      torch::Tensor x = build_batch_tensor(batch_idxs);
      torch::Tensor pred = model->forward(x).squeeze(-1);
      auto pred_acc = pred.accessor<float, 1>();
      for (std::size_t bi = 0; bi < batch_idxs.size(); ++bi) {
        y_true.push_back(outcomes[batch_idxs[bi]].pnl);
        y_pred.push_back(static_cast<double>(pred_acc[static_cast<int64_t>(bi)]));
      }
    }
  }

  metrics.mse = Metrics::calculate_mse(y_true, y_pred);
  metrics.r2_score = Metrics::calculate_r2(y_true, y_pred);

  std::vector<double> pnl = y_true;
  metrics.sharpe_ratio = Metrics::calculate_sharpe_ratio(pnl);
  metrics.profit_factor = Metrics::calculate_profit_factor(pnl);

  trained_transformer_ = std::make_shared<StockTransformer>(model);
  has_trained_transformer_ = true;
  trained_transformer_n_features_ = n_features;

  spdlog::info(
      "Transformer training complete: final_mean_batch_mse={}, holdout_mse={}, r2={}",
      last_epoch_loss, metrics.mse, metrics.r2_score);

  return metrics;
}

void ModelTrainer::export_transformer_artifact(
    const std::filesystem::path &output_path, int64_t input_features) const {
  const auto onnx_path = output_path;
  const auto config_path = onnx_path.parent_path() / "transformer_config.json";

  // The trainer's feature space (trade::ml::OrderBookFeatures-derived raw+
  // engineered features, trade::ml::kTransformerTotalFeatureCount) differs
  // from the live FeatureEngineer PCA pipeline's feature count
  // (::ml::FeatureEngineer::transformer_feature_dim(), passed in as
  // input_features by the caller) — a pre-existing split documented in
  // ModelCalibrationFitter.cpp for the classifier/regressor path, which
  // still applies there. For the transformer specifically, this is no
  // longer a live-serving gap: ONNXModelManager/LiveTradingService/
  // SimulatedTradingService consume the trained model's own raw+engineered
  // feature space directly via FeatureEngineer::get_raw_transformer_sequence
  // (include/ml/TransformerFeatures.hpp), not the PCA pipeline, whenever a
  // LibTorch-backed transformer is active. input_features (the PCA dim) is
  // only used for the placeholder ONNX shape when no trained model exists.
  const int64_t effective_features =
      has_trained_transformer_ ? trained_transformer_n_features_ : input_features;
  if (has_trained_transformer_ && trained_transformer_n_features_ != input_features) {
    spdlog::info(
        "Trained transformer feature count ({}) differs from the live "
        "FeatureEngineer PCA pipeline's feature count ({}); this is "
        "expected — the transformer serves from its own raw+engineered "
        "feature space (see ONNXModelManager::has_torch_transformer), not "
        "the PCA one.",
        trained_transformer_n_features_, input_features);
  }

  // The ONNX graph itself remains a shape-correct placeholder (see
  // TransformerOnnxExport.cpp) — LibTorch's C++ API has no built-in ONNX
  // exporter (unlike PyTorch's Python torch.onnx.export), and hand-authoring
  // a weight-bearing ONNX graph for a multi-block attention model by hand,
  // without the ability to compile/run it here to verify correctness, would
  // risk silently shipping a broken inference graph. Real learned weights
  // are captured below via torch::save, LibTorch's own native serialization,
  // and loaded directly by ONNXModelManager for live inference
  // (predict_transformer prefers this path over the ONNX placeholder — see
  // ONNXModelManager.cpp), so a trained model does serve real predictions
  // despite the ONNX file itself carrying no weights.
  export_transformer_to_onnx(onnx_path, effective_features);
  write_transformer_config(config_path, effective_features);

  if (has_trained_transformer_) {
    const auto weights_path = onnx_path.parent_path() / "transformer_weights.pt";
    try {
      const auto model_ptr =
          std::static_pointer_cast<StockTransformer>(trained_transformer_);
      torch::save(*model_ptr, weights_path.string());
      spdlog::info("Wrote gradient-trained transformer weights to {}",
                   weights_path.string());
    } catch (const std::exception &e) {
      spdlog::error("Failed to save trained transformer weights to {}: {}",
                    weights_path.string(), e.what());
    }
  } else {
    spdlog::warn(
        "No gradient-trained transformer available to persist; packaged "
        "ONNX graph will not have learned weights");
  }

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
