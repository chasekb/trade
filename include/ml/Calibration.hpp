#pragma once

#include <nlohmann/json.hpp>
#include <utility>
#include <vector>

namespace trade {
namespace ml {

// A monotonic calibration curve fit by isotonic regression (pool-adjacent-
// violators). Maps a raw model output (e.g. classifier win_probability, or
// any bounded score) to the empirical outcome rate observed at that score,
// interpolated between fitted breakpoints. An empty map means "no fit is
// available" and every caller must treat that as a pass-through, not as
// "already calibrated" or "known good."
struct CalibrationMap {
  std::vector<double> x; // ascending fitted breakpoints
  std::vector<double> y; // calibrated value at each breakpoint, non-decreasing
  int sample_count = 0;

  bool empty() const { return x.empty(); }
};

// samples: (raw predicted value, realized outcome — 0.0/1.0 for a binary
// win/loss label, or any bounded realized value being calibrated against).
// Requires at least 2 finite samples; returns an empty CalibrationMap
// otherwise so callers fail closed to the raw, uncalibrated value.
CalibrationMap fit_isotonic_calibration(const std::vector<std::pair<double, double>> &samples);

// Piecewise-linear lookup into a fitted CalibrationMap. Passes `raw` through
// unchanged if the map is empty or `raw` is non-finite. Clamps to the map's
// calibrated range outside the fitted domain — isotonic regression does not
// extrapolate beyond observed evidence.
double apply_calibration(const CalibrationMap &map, double raw);

// Mean squared error between predicted probability and realized binary
// outcome (0.0/1.0). Lower is better calibrated; a model that always predicts
// the base rate p scores p*(1-p), the ceiling a real model must beat.
double brier_score(const std::vector<std::pair<double, double>> &samples);

struct ReliabilityBucket {
  double predicted_lo = 0.0;
  double predicted_hi = 0.0;
  int sample_count = 0;
  double avg_predicted = 0.0;
  double avg_actual = 0.0;
};

// Buckets samples by predicted value into `bucket_count` equal-width bins
// over [0, 1] and reports average predicted vs. average realized outcome in
// each — the standard reliability-diagram view of calibration quality.
std::vector<ReliabilityBucket> reliability_buckets(
    const std::vector<std::pair<double, double>> &samples, int bucket_count = 10);

void to_json(nlohmann::json &j, const CalibrationMap &m);
void from_json(const nlohmann::json &j, CalibrationMap &m);

} // namespace ml
} // namespace trade
