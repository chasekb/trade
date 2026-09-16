#include "ml/Calibration.hpp"

#include <algorithm>
#include <cmath>

namespace trade {
namespace ml {
namespace {

// One pooled block in the pool-adjacent-violators algorithm: a contiguous
// run of samples (sorted by x) whose y-values are averaged together because
// their individual means would otherwise violate monotonicity.
struct Block {
  double x_sum = 0.0;
  double y_sum = 0.0;
  double weight = 0.0;

  double value() const { return weight > 0.0 ? y_sum / weight : 0.0; }
  double mean_x() const { return weight > 0.0 ? x_sum / weight : 0.0; }
};

} // namespace

CalibrationMap fit_isotonic_calibration(const std::vector<std::pair<double, double>> &samples) {
  CalibrationMap result;

  std::vector<std::pair<double, double>> sorted;
  sorted.reserve(samples.size());
  for (const auto &sample : samples) {
    if (std::isfinite(sample.first) && std::isfinite(sample.second)) {
      sorted.push_back(sample);
    }
  }
  if (sorted.size() < 2) {
    return result;
  }
  std::sort(sorted.begin(), sorted.end(),
           [](const auto &a, const auto &b) { return a.first < b.first; });

  // Pool-adjacent-violators: each sample starts as its own block. Whenever
  // appending a block would make the block-value sequence decrease, merge it
  // into its predecessor (and keep merging backward) until non-decreasing.
  std::vector<Block> blocks;
  blocks.reserve(sorted.size());
  for (const auto &[x, y] : sorted) {
    blocks.push_back(Block{x, y, 1.0});
    while (blocks.size() > 1) {
      Block &last = blocks[blocks.size() - 1];
      Block &prev = blocks[blocks.size() - 2];
      if (prev.value() <= last.value()) {
        break;
      }
      prev.x_sum += last.x_sum;
      prev.y_sum += last.y_sum;
      prev.weight += last.weight;
      blocks.pop_back();
    }
  }

  result.x.reserve(blocks.size());
  result.y.reserve(blocks.size());
  int total = 0;
  for (const auto &block : blocks) {
    result.x.push_back(block.mean_x());
    result.y.push_back(block.value());
    total += static_cast<int>(block.weight);
  }
  result.sample_count = total;
  return result;
}

double apply_calibration(const CalibrationMap &map, double raw) {
  if (map.empty() || !std::isfinite(raw)) {
    return raw;
  }
  if (map.x.size() == 1 || raw <= map.x.front()) {
    return map.y.front();
  }
  if (raw >= map.x.back()) {
    return map.y.back();
  }
  const auto it = std::lower_bound(map.x.begin(), map.x.end(), raw);
  const std::size_t hi = static_cast<std::size_t>(it - map.x.begin());
  const std::size_t lo = hi - 1;
  const double x0 = map.x[lo];
  const double x1 = map.x[hi];
  const double y0 = map.y[lo];
  const double y1 = map.y[hi];
  if (x1 <= x0) {
    return y1;
  }
  const double t = (raw - x0) / (x1 - x0);
  return y0 + t * (y1 - y0);
}

double brier_score(const std::vector<std::pair<double, double>> &samples) {
  double sum_sq = 0.0;
  std::size_t count = 0;
  for (const auto &[predicted, actual] : samples) {
    if (!std::isfinite(predicted) || !std::isfinite(actual)) {
      continue;
    }
    const double diff = predicted - actual;
    sum_sq += diff * diff;
    ++count;
  }
  return count > 0 ? sum_sq / static_cast<double>(count) : 0.0;
}

std::vector<ReliabilityBucket> reliability_buckets(
    const std::vector<std::pair<double, double>> &samples, int bucket_count) {
  std::vector<ReliabilityBucket> buckets;
  if (bucket_count <= 0) {
    return buckets;
  }
  const auto count = static_cast<std::size_t>(bucket_count);
  buckets.resize(count);
  std::vector<double> predicted_sum(count, 0.0);
  std::vector<double> actual_sum(count, 0.0);
  std::vector<int> sample_counts(count, 0);
  const double width = 1.0 / static_cast<double>(bucket_count);

  for (const auto &[predicted, actual] : samples) {
    if (!std::isfinite(predicted) || !std::isfinite(actual)) {
      continue;
    }
    int index = static_cast<int>(std::clamp(predicted, 0.0, 0.999999) / width);
    index = std::clamp(index, 0, bucket_count - 1);
    const auto idx = static_cast<std::size_t>(index);
    predicted_sum[idx] += predicted;
    actual_sum[idx] += actual;
    ++sample_counts[idx];
  }

  for (std::size_t i = 0; i < count; ++i) {
    ReliabilityBucket &bucket = buckets[i];
    bucket.predicted_lo = width * static_cast<double>(i);
    bucket.predicted_hi = width * static_cast<double>(i + 1);
    bucket.sample_count = sample_counts[i];
    if (bucket.sample_count > 0) {
      bucket.avg_predicted = predicted_sum[i] / bucket.sample_count;
      bucket.avg_actual = actual_sum[i] / bucket.sample_count;
    }
  }
  return buckets;
}

void to_json(nlohmann::json &j, const CalibrationMap &m) {
  j = nlohmann::json{{"x", m.x}, {"y", m.y}, {"sample_count", m.sample_count}};
}

void from_json(const nlohmann::json &j, CalibrationMap &m) {
  m.x = j.value("x", std::vector<double>{});
  m.y = j.value("y", std::vector<double>{});
  m.sample_count = j.value("sample_count", 0);
}

} // namespace ml
} // namespace trade
