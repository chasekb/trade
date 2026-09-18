
#pragma once
#include "ml/Types.hpp"
#include "ml/TransformerFeatures.hpp"
#include <deque>
#include <map>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include <xtensor/containers/xarray.hpp>

namespace ml {

class FeatureEngineer {
public:
  FeatureEngineer();

  // Load parameters from JSON (exported from Python)
  bool load_parameters(const std::string &filepath);

  // Core preprocessing: Raw -> Final PCA features
  std::vector<double> preprocess(const OrderBookFeatures &features);

  // Get sequence of model-ready PCA features for transformer, most-recent
  // rows last. `max_length` trims to the caller's active model contract
  // (e.g. ONNXModelManager::transformer_lookback()); 0 returns everything
  // currently retained. Retention itself is a generous fixed upper bound
  // (see kMaxTransformerHistoryRetained), not tied to any one model's
  // lookback, so a retrained model with a different lookback is never
  // capped below what it needs.
  std::vector<std::vector<double>> get_transformer_sequence(const std::string &sequence_key = "",
                                                             std::size_t max_length = 0);
  size_t transformer_feature_dim() const { return transformer_feature_dim_; }

  // Raw (non-PCA) counterpart to preprocess()/get_transformer_sequence(),
  // feeding a LibTorch-backed transformer trained by
  // ModelTrainer::train_transformer directly on
  // trade::ml::OrderBookFeatures-derived raw+engineered features (see
  // include/ml/TransformerFeatures.hpp) rather than this class's PCA
  // pipeline. Call record_raw_transformer_features once per live tick, then
  // get_raw_transformer_sequence to build the model's input sequence.
  // Maintains its own per-symbol state, independent of
  // transformer_sequence_windows_/history_windows_ below.
  template <typename OrderBookFeaturesT>
  void record_raw_transformer_features(const std::string &symbol,
                                       const OrderBookFeaturesT &features) {
    std::lock_guard<std::mutex> lock(raw_transformer_mutex_);
    raw_transformer_windows_[symbol].push(trade::ml::raw_feature_vector(features));
  }

  // Returns an empty sequence (matching the PCA path's natural "not enough
  // history yet" warmup behavior) until kTransformerLookback real ticks have
  // been recorded for this symbol — never a zero-padded full-length
  // sequence passed off as a ready prediction input.
  std::vector<std::vector<double>> get_raw_transformer_sequence(const std::string &symbol) {
    std::lock_guard<std::mutex> lock(raw_transformer_mutex_);
    auto it = raw_transformer_windows_.find(symbol);
    if (it == raw_transformer_windows_.end() || !it->second.has_full_window()) {
      return {};
    }
    return it->second.build_sequence();
  }

private:
  void initialize_default_parameters();

  // Internal steps
  std::vector<double> extract_base_features(const OrderBookFeatures &f);
  std::vector<double> impute(const std::vector<double> &base);
  std::vector<double>
  add_time_series_features(const std::vector<double> &imputed,
                           const std::string &sequence_key);
  std::vector<double> add_interaction_features(const std::vector<double> &ts);
  std::vector<double> scale(const std::vector<double> &interactions);
  std::vector<double> apply_pca(const std::vector<double> &scaled);

  // Helpers
  double calculate_rsi_like(double momentum);
  double calculate_volatility_bands(double volatility);
  double calculate_trend_indicator(double momentum, double volatility);
  double calculate_macd_like(double mid_price, double vwap);
  double calculate_bollinger_bands_like(double mid_price, double volatility);
  double calculate_atr_like(double volatility);

  // State for rolling stats
  std::map<std::string, std::deque<std::vector<double>>> history_windows_;
  std::map<std::string, std::deque<std::vector<double>>> transformer_sequence_windows_;
  const std::vector<size_t> windows = {5, 10, 20, 50, 90, 200};
  // Memory-bound retention cap only, not a model contract: must stay >= the
  // largest lookback any active transformer could request. The exact
  // per-model length is enforced by get_transformer_sequence's max_length
  // argument and by ONNXModelManager::transformer_input_ready, not here.
  static constexpr size_t kMaxTransformerHistoryRetained = 512;
  std::mutex history_mutex;

  // Per-symbol raw-feature rolling buffers backing
  // record_raw_transformer_features/get_raw_transformer_sequence, entirely
  // separate from the PCA-based state above.
  std::map<std::string, trade::ml::RollingWindowBuffer> raw_transformer_windows_;
  std::mutex raw_transformer_mutex_;

  // Parameters
  struct {
    std::vector<double> statistics;
  } imputer_params;

  struct {
    std::vector<double> mean;
    std::vector<double> scale;
  } scaler_params;

  struct {
    xt::xarray<double> components;
    xt::xarray<double> mean;
  } pca_params;

  size_t transformer_feature_dim_ = 0;

  bool parameters_loaded = false;
};

} // namespace ml
