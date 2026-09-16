#pragma once

#include "ml/DataCollector.hpp"

#include <string>
#include <utility>
#include <vector>

namespace trade {
namespace ml {

struct CalibrationFitResult {
  bool wrote_file = false;
  int win_probability_samples = 0;
  int expected_return_samples = 0;
  // Brier score before/after calibration on the same held-out win/loss
  // labels; after should be <= before for a fit worth shipping. Zero on
  // both sides when no classifier calibration was fit.
  double win_probability_brier_before = 0.0;
  double win_probability_brier_after = 0.0;
  std::string error;
};

// Fits calibration for the ONNX model pack at `model_dir` against held-out
// labeled outcomes and writes calibration.json beside the model's other
// artifacts, where ONNXModelManager::load_models loads it automatically.
//
// Treats the model as a black box: loads it fresh (independent of any
// currently-running service), replays FeatureEngineer + ONNXModelManager
// inference on each sample, and never touches model-training internals.
// `holdout_samples` must be data the model was not trained on — fitting
// calibration against in-sample predictions would calibrate to the model's
// own overfitting rather than to genuine miscalibration against reality.
//
// `feature_params_path` is the same global feature-engineering parameters
// file (imputer/scaler/PCA) the running service loads independent of which
// trained model package is active (main.cpp's FEATURE_PARAMS_PATH,
// default data/cpp_assets/feature_params.json) — it is not inside
// `model_dir`.
CalibrationFitResult fit_and_write_model_calibration(
    const std::string &model_dir, const std::string &feature_params_path,
    const std::vector<std::pair<OrderBookFeatures, TradeOutcome>> &holdout_samples);

} // namespace ml
} // namespace trade
