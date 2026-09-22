#include "ml/ModelCalibrationFitter.hpp"

#include "ml/Calibration.hpp"
#include "ml/FeatureEngineer.hpp"
#include "ml/ONNXModelManager.hpp"
#include "ml/Types.hpp"

#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

namespace trade {
namespace ml {
namespace {

// FeatureEngineer/ONNXModelManager consume ::ml::OrderBookFeatures
// (include/ml/Types.hpp); DataCollector/ExecutionCohorts/training use the
// distinct trade::ml::OrderBookFeatures (include/ml/DataCollector.hpp) —
// same name, different namespace, different (mostly overlapping) fields.
// This maps the inference-relevant subset across.
::ml::OrderBookFeatures to_inference_features(const OrderBookFeatures &features) {
  ::ml::OrderBookFeatures out;
  out.timestamp = features.timestamp;
  out.symbol = features.symbol;
  out.bid_ask_imbalance = features.bid_ask_imbalance;
  out.spread_percent = features.spread_percent;
  out.mid_price = features.mid_price;
  out.bid_volume = features.bid_volume;
  out.ask_volume = features.ask_volume;
  out.order_book_depth = features.order_book_depth;
  out.large_bid_wall = features.large_bid_wall;
  out.large_ask_wall = features.large_ask_wall;
  out.wall_size = features.wall_size;
  out.volume_weighted_price = features.volume_weighted_price;
  out.price_momentum = features.price_momentum;
  out.volatility = features.volatility;
  out.volume_24h = features.volume_24h;
  out.prev_win_probability = features.prev_win_probability;
  out.prev_expected_return = features.prev_expected_return;
  out.prev_confidence = features.prev_confidence;
  return out;
}

bool write_calibration_file(const std::filesystem::path &final_path, const nlohmann::json &payload,
                            std::string &error) {
  const std::filesystem::path tmp_path = final_path.string() + ".tmp";
  {
    std::ofstream out(tmp_path);
    if (!out.is_open()) {
      error = "failed to open temp calibration file for writing: " + tmp_path.string();
      return false;
    }
    out << payload.dump(2);
    out.flush();
    if (!out.good()) {
      std::error_code rm_ec;
      std::filesystem::remove(tmp_path, rm_ec);
      error = "failed to flush calibration file: " + tmp_path.string();
      return false;
    }
  }
  std::error_code rename_ec;
  std::filesystem::rename(tmp_path, final_path, rename_ec);
  if (rename_ec) {
    std::error_code rm_ec;
    std::filesystem::remove(tmp_path, rm_ec);
    error = "failed to finalize calibration file: " + rename_ec.message();
    return false;
  }
  return true;
}

} // namespace

CalibrationFitResult fit_and_write_model_calibration(
    const std::string &model_dir, const std::string &feature_params_path,
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &holdout_samples) {
  CalibrationFitResult result;
  if (holdout_samples.empty()) {
    result.error = "no held-out samples provided";
    return result;
  }

  // A fresh, independent manager/engineer pair — never touches whatever
  // model a live PredictController singleton currently has loaded.
  ::ml::ONNXModelManager models;
  if (!models.load_models(model_dir)) {
    result.error = "failed to load model pack at " + model_dir;
    return result;
  }
  ::ml::FeatureEngineer engineer;
  if (!engineer.load_parameters(feature_params_path)) {
    result.error = "failed to load feature-engineering parameters at " + feature_params_path;
    return result;
  }

  std::vector<std::pair<double, double>> win_probability_samples;
  std::vector<std::pair<double, double>> expected_return_samples;
  win_probability_samples.reserve(holdout_samples.size());
  expected_return_samples.reserve(holdout_samples.size());

  for (const auto &[features, outcome] : holdout_samples) {
    const auto inference_features = to_inference_features(features);
    const auto pca_features = engineer.preprocess(inference_features);
    if (pca_features.empty()) {
      continue;
    }
    if (models.has_classifier()) {
      const double raw_win_prob = models.predict_win_prob(pca_features);
      win_probability_samples.emplace_back(raw_win_prob, outcome.is_win ? 1.0 : 0.0);
    }
    if (models.has_regressor()) {
      const double raw_expected = models.predict_pnl(pca_features);
      const double notional = outcome.entry_price * outcome.quantity;
      const double realized_return = notional > 0.0 ? outcome.pnl / notional : 0.0;
      expected_return_samples.emplace_back(raw_expected, realized_return);
    }
  }

  nlohmann::json calibration_json = nlohmann::json::object();

  if (win_probability_samples.size() >= 2) {
    const auto map = fit_isotonic_calibration(win_probability_samples);
    if (!map.empty()) {
      nlohmann::json map_json;
      to_json(map_json, map);
      calibration_json["win_probability"] = map_json;
      result.win_probability_samples = map.sample_count;
      result.win_probability_brier_before = brier_score(win_probability_samples);
      std::vector<std::pair<double, double>> calibrated_samples;
      calibrated_samples.reserve(win_probability_samples.size());
      for (const auto &[raw, actual] : win_probability_samples) {
        calibrated_samples.emplace_back(apply_calibration(map, raw), actual);
      }
      result.win_probability_brier_after = brier_score(calibrated_samples);
    }
  }

  if (expected_return_samples.size() >= 2) {
    const auto map = fit_isotonic_calibration(expected_return_samples);
    if (!map.empty()) {
      nlohmann::json map_json;
      to_json(map_json, map);
      calibration_json["expected_return"] = map_json;
      result.expected_return_samples = map.sample_count;
    }
  }

  if (calibration_json.empty()) {
    result.error = "not enough labeled held-out samples to fit any calibration "
                   "(need >= 2 per target, plus a loaded classifier/regressor)";
    return result;
  }

  const std::filesystem::path final_path = std::filesystem::path(model_dir) / "calibration.json";
  std::string write_error;
  if (!write_calibration_file(final_path, calibration_json, write_error)) {
    result.error = write_error;
    return result;
  }

  spdlog::info(
      "Wrote model calibration to {} (win_probability samples={}, brier {} -> {}; "
      "expected_return samples={})",
      final_path.string(), result.win_probability_samples, result.win_probability_brier_before,
      result.win_probability_brier_after, result.expected_return_samples);
  result.wrote_file = true;
  return result;
}

} // namespace ml
} // namespace trade
