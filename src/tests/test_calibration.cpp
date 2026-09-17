#include "ml/Calibration.hpp"

#include <cmath>
#include <iostream>
#include <vector>

namespace {
int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

void expect_near(double actual, double expected, double tolerance, const std::string &label) {
  if (std::abs(actual - expected) > tolerance) {
    std::cerr << "FAIL: " << label << " expected=" << expected << " actual=" << actual
              << std::endl;
    ++failures;
  }
}

} // namespace

int main() {
  using trade::ml::apply_calibration;
  using trade::ml::brier_score;
  using trade::ml::CalibrationMap;
  using trade::ml::fit_isotonic_calibration;
  using trade::ml::reliability_buckets;

  // Too few samples: fail closed to an empty (pass-through) map.
  {
    const auto map = fit_isotonic_calibration({{0.5, 1.0}});
    expect(map.empty(), "single-sample fit stays empty");
    expect_near(apply_calibration(map, 0.7), 0.7, 1e-9, "empty map is a pass-through");
  }

  // A model that systematically overstates win probability by a fixed
  // amount: raw predictions cluster around 0.8 but the realized win rate is
  // only ~0.5. The calibration map should pull 0.8 down toward 0.5, not
  // leave it untouched.
  {
    std::vector<std::pair<double, double>> samples;
    for (int i = 0; i < 40; ++i) {
      const double raw = 0.75 + 0.001 * (i % 10);
      const double outcome = (i % 2 == 0) ? 1.0 : 0.0; // ~50% realized win rate
      samples.emplace_back(raw, outcome);
    }
    const auto map = fit_isotonic_calibration(samples);
    expect(!map.empty(), "overstated-confidence fit produces a map");
    const double calibrated = apply_calibration(map, 0.75);
    expect(calibrated < 0.7, "overconfident raw prediction is pulled down toward the realized rate");
    expect(calibrated > 0.3, "calibrated value stays a plausible probability");
  }

  // Monotonic input/output stays monotonic and roughly identity when the
  // model is already well-calibrated.
  {
    std::vector<std::pair<double, double>> samples;
    for (int i = 0; i <= 100; ++i) {
      const double raw = static_cast<double>(i) / 100.0;
      // Bernoulli-ish outcome whose expectation equals raw; alternate above
      // and below to average out to raw at each point without needing RNG.
      const double outcome = (i % 2 == 0) ? std::min(1.0, raw + 0.05) : std::max(0.0, raw - 0.05);
      samples.emplace_back(raw, outcome);
    }
    const auto map = fit_isotonic_calibration(samples);
    expect(!map.empty(), "well-calibrated fit produces a map");
    for (std::size_t i = 1; i < map.y.size(); ++i) {
      expect(map.y[i] >= map.y[i - 1] - 1e-9, "fitted curve is non-decreasing");
    }
    expect_near(apply_calibration(map, 0.5), 0.5, 0.1, "near-identity fit stays close to raw at 0.5");
  }

  // Clamping outside the fitted domain: isotonic regression never
  // extrapolates past the evidence it was fit on.
  {
    const auto map = fit_isotonic_calibration({{0.3, 0.2}, {0.6, 0.5}, {0.9, 0.8}});
    expect_near(apply_calibration(map, 0.0), apply_calibration(map, 0.3), 1e-9,
               "below-domain input clamps to the lowest breakpoint");
    expect_near(apply_calibration(map, 1.0), apply_calibration(map, 0.9), 1e-9,
               "above-domain input clamps to the highest breakpoint");
  }

  // Brier score: a model that always predicts the realized outcome exactly
  // scores 0; a model that is maximally wrong on every sample scores 1.
  {
    const std::vector<std::pair<double, double>> perfect = {{1.0, 1.0}, {0.0, 0.0}, {1.0, 1.0}};
    const std::vector<std::pair<double, double>> worst = {{1.0, 0.0}, {0.0, 1.0}};
    expect_near(brier_score(perfect), 0.0, 1e-9, "perfect predictions score zero Brier loss");
    expect_near(brier_score(worst), 1.0, 1e-9, "maximally wrong predictions score Brier loss of 1");
  }

  // Reliability buckets: predictions concentrated in one bucket should all
  // land there with the correct average, and untouched buckets stay empty.
  {
    // Values chosen away from exact bucket-boundary multiples of 0.1 (e.g.
    // 0.9) to avoid floating-point division landing in the neighboring
    // bucket.
    std::vector<std::pair<double, double>> samples = {
        {0.15, 1.0}, {0.18, 0.0}, {0.12, 1.0}, {0.83, 1.0}, {0.86, 1.0}};
    const auto buckets = reliability_buckets(samples, 10);
    expect(buckets.size() == 10, "reliability_buckets returns the requested bucket count");
    expect(buckets[1].sample_count == 3, "predictions near 0.15 land in the [0.1, 0.2) bucket");
    expect_near(buckets[1].avg_actual, 2.0 / 3.0, 1e-9, "bucket average actual matches realized rate");
    expect(buckets[8].sample_count == 2, "predictions near 0.83-0.86 land in the [0.8, 0.9) bucket");
    expect(buckets[5].sample_count == 0, "an untouched bucket stays empty rather than inventing data");
  }

  // JSON round trip.
  {
    const auto map = fit_isotonic_calibration({{0.2, 0.1}, {0.5, 0.4}, {0.8, 0.9}});
    nlohmann::json j;
    trade::ml::to_json(j, map);
    CalibrationMap round_tripped;
    trade::ml::from_json(j, round_tripped);
    expect(round_tripped.x == map.x, "JSON round trip preserves breakpoints");
    expect(round_tripped.y == map.y, "JSON round trip preserves calibrated values");
    expect(round_tripped.sample_count == map.sample_count, "JSON round trip preserves sample count");
  }

  if (failures == 0) {
    std::cout << "All calibration tests passed." << std::endl;
    return 0;
  }
  std::cerr << failures << " calibration test(s) failed." << std::endl;
  return 1;
}
