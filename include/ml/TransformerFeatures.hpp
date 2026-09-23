#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <deque>
#include <vector>

// Live-inference counterpart to the feature representation
// ModelTrainer.cpp's train_transformer trains on: 16 raw order-book fields
// plus rolling mean/std of {bid_ask_imbalance, spread_percent,
// price_momentum, volatility} over 5/20/60-sample sub-windows (40 features
// total). See ModelTrainer.cpp's kTransformerNumFeatures/
// kEngineeredFieldIndices/kEngineeredWindows/rolling_mean_std comment block
// for the training-side implementation and the A/B test that justified this
// representation. The constants and math here are deliberately kept
// value-identical to that implementation (same field indices, same window
// sizes, same mean/std formula) so a live-inference sequence matches what
// the model was trained on; ModelTrainer.cpp's copy was intentionally left
// untouched (already CI-verified, training-only, lower risk) rather than
// refactored to share this header — if either changes, the other must be
// updated to match.
namespace trade {
namespace ml {

inline constexpr int64_t kTransformerRawFeatureCount = 16;
inline constexpr int64_t kTransformerLookback = 60;
// Indices into the 16-field raw_feature_vector() output: bid_ask_imbalance,
// spread_percent, price_momentum, volatility.
inline constexpr std::array<int, 4> kTransformerEngineeredFieldIndices = {0, 1, 10, 11};
inline constexpr std::array<int64_t, 3> kTransformerEngineeredWindows = {5, 20, 60};
inline constexpr int64_t kTransformerEngineeredFeatureCount =
    static_cast<int64_t>(kTransformerEngineeredFieldIndices.size() *
                         kTransformerEngineeredWindows.size() * 2); // 24
inline constexpr int64_t kTransformerTotalFeatureCount =
    kTransformerRawFeatureCount + kTransformerEngineeredFeatureCount; // 40

// Extracts the 16 raw fields, in the exact field order ModelTrainer.cpp's
// transformer_feature_vector() uses, from any type exposing the same named
// members (both trade::ml::OrderBookFeatures in DataCollector.hpp and
// ::ml::OrderBookFeatures in Types.hpp qualify — same field names/shape,
// unrelated C++ types).
template <typename OrderBookFeaturesT>
std::array<double, static_cast<std::size_t>(kTransformerRawFeatureCount)>
raw_feature_vector(const OrderBookFeaturesT &f) {
  return {f.bid_ask_imbalance,
          f.spread_percent,
          f.mid_price,
          f.bid_volume,
          f.ask_volume,
          static_cast<double>(f.order_book_depth),
          f.large_bid_wall ? 1.0 : 0.0,
          f.large_ask_wall ? 1.0 : 0.0,
          f.wall_size,
          f.volume_weighted_price,
          f.price_momentum,
          f.volatility,
          f.volume_24h,
          f.prev_win_probability,
          f.prev_expected_return,
          f.prev_confidence};
}

// Maintains a per-symbol chronological history of raw 16-field vectors and
// builds the (kTransformerLookback, kTransformerTotalFeatureCount) sequence
// a trained transformer expects, updated one live tick at a time.
//
// Retention is 2x kTransformerLookback, not 1x: ModelTrainer.cpp computes
// each row's engineered (rolling-stat) features from THAT row's own up-to-
// 60-sample trailing history, independent of which later sample's 60-token
// window it ends up placed inside — so the earliest token in an emitted
// 60-token sequence still needs up to 60 samples of history *before* it to
// compute its own engineered features correctly. Retaining only
// kTransformerLookback would silently truncate that history for early
// tokens and diverge from what the model was trained on.
class RollingWindowBuffer {
public:
  void push(const std::array<double, static_cast<std::size_t>(kTransformerRawFeatureCount)> &raw) {
    history_.push_back(raw);
    while (static_cast<int64_t>(history_.size()) > kRetain) {
      history_.pop_front();
    }
  }

  // Oldest-first, zero-padded on the left when fewer than kTransformerLookback
  // ticks have been pushed yet — matches ModelTrainer.cpp's zero-pad-when-
  // short behavior for a symbol's early history.
  std::vector<std::vector<double>> build_sequence() const {
    const int64_t hist_size = static_cast<int64_t>(history_.size());
    const int64_t out_len = kTransformerLookback;
    const int64_t hist_start = std::max<int64_t>(0, hist_size - out_len);
    const int64_t emitted = hist_size - hist_start;
    const int64_t pad = out_len - emitted;

    std::vector<std::vector<double>> result(
        static_cast<std::size_t>(out_len),
        std::vector<double>(static_cast<std::size_t>(kTransformerTotalFeatureCount), 0.0));

    for (int64_t k = 0; k < emitted; ++k) {
      const int64_t pos = hist_start + k; // absolute index within history_
      const auto &raw = history_[static_cast<std::size_t>(pos)];
      auto &row_out = result[static_cast<std::size_t>(pad + k)];

      for (int64_t f = 0; f < kTransformerRawFeatureCount; ++f) {
        row_out[static_cast<std::size_t>(f)] = raw[static_cast<std::size_t>(f)];
      }

      int64_t idx = kTransformerRawFeatureCount;
      for (int field_index : kTransformerEngineeredFieldIndices) {
        for (int64_t w : kTransformerEngineeredWindows) {
          const int64_t start = std::max<int64_t>(0, pos - w + 1);
          double sum = 0.0, sum_sq = 0.0;
          int64_t count = 0;
          for (int64_t s = start; s <= pos; ++s) {
            const double v = history_[static_cast<std::size_t>(s)][static_cast<std::size_t>(field_index)];
            sum += v;
            sum_sq += v * v;
            ++count;
          }
          const double mean = count > 0 ? sum / static_cast<double>(count) : 0.0;
          const double variance =
              count > 0 ? std::max(0.0, sum_sq / static_cast<double>(count) - mean * mean) : 0.0;
          row_out[static_cast<std::size_t>(idx++)] = mean;
          row_out[static_cast<std::size_t>(idx++)] = std::sqrt(variance);
        }
      }
    }
    return result;
  }

  std::size_t size() const { return history_.size(); }

  // True once kTransformerLookback real ticks have been pushed. Callers
  // should treat a not-yet-full buffer as "not ready" (return no sequence)
  // rather than serving build_sequence()'s zero-padded output as if it were
  // a real prediction input — matching the deliberate warmup gating the
  // PCA-based get_transformer_sequence path already has via its naturally
  // growing (rather than always-full) sequence length.
  bool has_full_window() const {
    return static_cast<int64_t>(history_.size()) >= kTransformerLookback;
  }

private:
  static constexpr int64_t kRetain = kTransformerLookback * 2;
  std::deque<std::array<double, static_cast<std::size_t>(kTransformerRawFeatureCount)>> history_;
};

} // namespace ml
} // namespace trade
