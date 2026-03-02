
#pragma once
#include "ml/Types.hpp"
#include <deque>
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

  // Get sequence of base features for transformer (Phase 6)
  std::vector<std::vector<double>> get_transformer_sequence();

private:
  // Internal steps
  std::vector<double> extract_base_features(const OrderBookFeatures &f);
  std::vector<double> impute(const std::vector<double> &base);
  std::vector<double>
  add_time_series_features(const std::vector<double> &imputed);
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
  std::deque<std::vector<double>> history_window;
  const std::vector<size_t> windows = {5, 10, 20, 50, 90, 200};
  std::mutex history_mutex;

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

  bool parameters_loaded = false;
};

} // namespace ml
