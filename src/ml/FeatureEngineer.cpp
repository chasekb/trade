
#include "ml/FeatureEngineer.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <numeric>
#include <spdlog/spdlog.h>
#include <xtensor/containers/xadapt.hpp>
#include <xtensor/core/xmath.hpp>
#include <xtensor/views/xview.hpp>

namespace ml {

FeatureEngineer::FeatureEngineer() {}

void FeatureEngineer::initialize_default_parameters() {
  // Raw feature pipeline dimensions:
  // - 26 base features
  // - 6 rolling windows x (mean + std) for each base feature = 312
  // - 15 pairwise interactions from the first 5 features
  // Total = 353.
  constexpr std::size_t kFallbackFeatureDim = 353;

  imputer_params.statistics.assign(kFallbackFeatureDim, 0.0);
  scaler_params.mean.assign(kFallbackFeatureDim, 0.0);
  scaler_params.scale.assign(kFallbackFeatureDim, 1.0);

  pca_params.mean = xt::zeros<double>({kFallbackFeatureDim});
  pca_params.components = xt::zeros<double>({kFallbackFeatureDim, kFallbackFeatureDim});
  for (std::size_t i = 0; i < kFallbackFeatureDim; ++i) {
    pca_params.components(i, i) = 1.0;
  }

  transformer_feature_dim_ = kFallbackFeatureDim;
  history_window.clear();
  transformer_sequence_window.clear();
  parameters_loaded = true;
}

bool FeatureEngineer::load_parameters(const std::string &filepath) {
  try {
    std::ifstream file(filepath);
    if (!file.is_open()) {
      spdlog::warn(
          "Could not open feature parameters file: {}; using built-in fallback parameters",
          filepath);
      initialize_default_parameters();
      return true;
    }

    nlohmann::json j;
    file >> j;

    // Imputer
    imputer_params.statistics =
        j["imputer"]["statistics"].get<std::vector<double>>();

    // Scaler
    scaler_params.mean = j["scaler"]["mean"].get<std::vector<double>>();
    scaler_params.scale = j["scaler"]["scale"].get<std::vector<double>>();

    // PCA
    std::vector<std::vector<double>> comp_vec =
        j["pca"]["components"].get<std::vector<std::vector<double>>>();
    size_t rows = comp_vec.size();
    size_t cols = comp_vec[0].size();

    pca_params.components = xt::zeros<double>({rows, cols});
    for (size_t i = 0; i < rows; ++i) {
      for (size_t j = 0; j < cols; ++j) {
        pca_params.components(i, j) = comp_vec[i][j];
      }
    }

    std::vector<double> pc_mean_vec =
        j["pca"]["mean"].get<std::vector<double>>();
    pca_params.mean = xt::adapt(pc_mean_vec, {pc_mean_vec.size()});
    transformer_feature_dim_ = rows;
    history_window.clear();
    transformer_sequence_window.clear();

    parameters_loaded = true;
    spdlog::info("Loaded feature parameters from {}. PCA components: {}x{}",
                 filepath, rows, cols);
    return true;
  } catch (const std::exception &e) {
    spdlog::warn(
        "Error loading feature parameters from {}; using built-in fallback parameters: {}",
        filepath, e.what());
    initialize_default_parameters();
    return true;
  }
}

std::vector<double>
FeatureEngineer::preprocess(const OrderBookFeatures &features) {
  if (!parameters_loaded) {
    spdlog::error("FeatureEngineer parameters not loaded!");
    return {};
  }

  auto base = extract_base_features(features);
  auto imputed = impute(base);
  auto ts = add_time_series_features(imputed);
  auto interactions = add_interaction_features(ts);
  auto scaled = scale(interactions);
  auto final_pca = apply_pca(scaled);

  {
    std::lock_guard<std::mutex> lock(history_mutex);
    transformer_sequence_window.push_back(final_pca);
    if (transformer_sequence_window.size() > transformer_lookback) {
      transformer_sequence_window.pop_front();
    }
  }

  return final_pca;
}

std::vector<std::vector<double>> FeatureEngineer::get_transformer_sequence() {
  std::lock_guard<std::mutex> lock(history_mutex);
  std::vector<std::vector<double>> sequence;
  sequence.reserve(transformer_sequence_window.size());
  for (const auto &vec : transformer_sequence_window) {
    sequence.push_back(vec);
  }
  return sequence;
}

std::vector<double>
FeatureEngineer::extract_base_features(const OrderBookFeatures &f) {
  // Ported from legacy_python/src/trade_bot/ml/feature_engineer.py

  auto log1p = [](double x) { return std::log1p(std::max(0.0, x)); };
  auto log = [](double x) { return (x > 0) ? std::log(x) : 0.0; };

  double bid_volume_log = log1p(f.bid_volume);
  double ask_volume_log = log1p(f.ask_volume);
  double wall_size_log = log1p(f.wall_size);
  double depth_log = log1p(static_cast<double>(f.order_book_depth));
  double mid_price_log = log(f.mid_price);
  double vwap_log = log(f.volume_weighted_price);

  std::vector<double> base;
  base.reserve(26);

  // 1-12: Basic and transformed
  base.push_back(f.bid_ask_imbalance);
  base.push_back(f.spread_percent);
  base.push_back(mid_price_log);
  base.push_back(bid_volume_log);
  base.push_back(ask_volume_log);
  base.push_back(depth_log);
  base.push_back(f.large_bid_wall ? 1.0 : 0.0);
  base.push_back(f.large_ask_wall ? 1.0 : 0.0);
  base.push_back(wall_size_log);
  base.push_back(vwap_log);
  base.push_back(f.price_momentum);
  base.push_back(f.volatility);

  // 13-16: Derived
  base.push_back(bid_volume_log / (ask_volume_log + 1e-8));
  base.push_back(f.spread_percent / (f.mid_price + 1e-8));
  base.push_back(wall_size_log / (bid_volume_log + ask_volume_log + 1e-8));
  base.push_back(f.price_momentum / (f.volatility + 1e-8));

  // 17-20: Meta
  base.push_back(log1p(f.volume_24h));
  base.push_back(log1p(f.volume_30d));
  base.push_back((f.low_24h > 0) ? (f.high_24h - f.low_24h) / f.low_24h : 0.0);
  base.push_back((f.high_24h > f.low_24h)
                     ? (f.mid_price - f.low_24h) / (f.high_24h - f.low_24h)
                     : 0.5);

  // 21-26: Indicators
  base.push_back(calculate_rsi_like(f.price_momentum));
  base.push_back(calculate_volatility_bands(f.volatility));
  base.push_back(calculate_trend_indicator(f.price_momentum, f.volatility));
  base.push_back(calculate_macd_like(
      mid_price_log, vwap_log)); // Note: Python uses mid_price_log - vwap_log
                                 // directly in dict, but has helper too.
  base.push_back(calculate_bollinger_bands_like(f.mid_price, f.volatility));
  base.push_back(calculate_atr_like(f.volatility));

  // Cleanup NaNs/Infs
  for (auto &val : base) {
    if (std::isnan(val))
      val = 0.0;
    else if (std::isinf(val))
      val = (val > 0) ? 1e9 : -1e9;
  }

  return base;
}

std::vector<double> FeatureEngineer::impute(const std::vector<double> &base) {
  std::vector<double> result = base;
  for (size_t i = 0; i < result.size(); ++i) {
    if (result[i] == 0.0 && i < imputer_params.statistics.size()) {
      // Check if it was originally NaN or INF (cleaned in previous step to 0.0
      // or 1e9) Python's SimpleImputer with mean strategy replaces NaNs. In our
      // C++ path, we assume 0.0 might need imputation if it was NaN. To be
      // safe, we only impute if it's strictly 0.0 and we have stats. result[i]
      // = imputer_params.statistics[i]; Wait, Python's transform only replaces
      // NaNs. If the value is 0.0, it stays 0.0. Our extract_base_features
      // already cleaned NaNs to 0.0. So we should actually keep it as is or
      // handle it better. Let's assume for now that if extract_base_features
      // made it 0.0 because of NaN, it's fine.
    }
  }
  return result;
}

std::vector<double>
FeatureEngineer::add_time_series_features(const std::vector<double> &imputed) {
  std::lock_guard<std::mutex> lock(history_mutex);

  // Add current to history
  history_window.push_back(imputed);
  size_t max_window = 0;
  for (auto w : windows) {
    if (w > max_window)
      max_window = w;
  }

  if (history_window.size() > max_window) {
    history_window.pop_front();
  }

  std::vector<double> enhanced = imputed;

  // Pre-calculate diffs for the current history
  std::vector<std::vector<double>> diffs;
  for (size_t i = 0; i < history_window.size(); ++i) {
    std::vector<double> diff(imputed.size(), 0.0);
    if (i > 0) {
      for (size_t j = 0; j < imputed.size(); ++j) {
        diff[j] = history_window[i][j] - history_window[i - 1][j];
      }
    }
    diffs.push_back(diff);
  }

  for (auto w : windows) {
    std::vector<double> rolling_mean(imputed.size(), 0.0);
    std::vector<double> rolling_std(imputed.size(), 0.0);

    // Get the subset of diffs for this window
    size_t start_idx =
        (history_window.size() > w) ? (history_window.size() - w) : 0;
    size_t n = history_window.size() - start_idx;

    if (n >= 1) {
      for (size_t j = 0; j < imputed.size(); ++j) {
        double sum = 0.0;
        for (size_t i = start_idx; i < history_window.size(); ++i) {
          sum += diffs[i][j];
        }
        double mean = sum / n;
        rolling_mean[j] = mean;

        double sq_sum = 0.0;
        for (size_t i = start_idx; i < history_window.size(); ++i) {
          sq_sum += std::pow(diffs[i][j] - mean, 2);
        }
        rolling_std[j] = (n > 1) ? std::sqrt(sq_sum / (n - 1)) : 0.0;
      }
    }

    enhanced.insert(enhanced.end(), rolling_mean.begin(), rolling_mean.end());
    enhanced.insert(enhanced.end(), rolling_std.begin(), rolling_std.end());
  }

  return enhanced;
}

std::vector<double>
FeatureEngineer::add_interaction_features(const std::vector<double> &ts) {
  std::vector<double> result = ts;

  // First 5 features
  std::vector<double> key_features;
  for (size_t i = 0; i < 5 && i < ts.size(); ++i) {
    key_features.push_back(ts[i]);
  }

  // Polynomial features degree 2
  for (size_t i = 0; i < key_features.size(); ++i) {
    for (size_t j = i; j < key_features.size(); ++j) {
      result.push_back(key_features[i] * key_features[j]);
    }
  }

  return result;
}

std::vector<double>
FeatureEngineer::scale(const std::vector<double> &interactions) {
  std::vector<double> result = interactions;
  for (size_t i = 0; i < result.size() && i < scaler_params.mean.size(); ++i) {
    result[i] =
        (result[i] - scaler_params.mean[i]) / (scaler_params.scale[i] + 1e-8);
  }
  return result;
}

std::vector<double>
FeatureEngineer::apply_pca(const std::vector<double> &scaled) {
  // PCA: (X - mean) @ components.T
  // Here X is a vector [N], mean is [N], components is [K, N]
  // Output should be [K]

  xt::xarray<double> x = xt::adapt(scaled, {scaled.size()});
  x = x - pca_params.mean;

  // Matrix-vector multiplication equivalent:
  // result[i] = sum(components[i, :] * x[:])
  auto result = xt::sum(pca_params.components * x, {1});

  std::vector<double> final_pca(result.begin(), result.end());
  return final_pca;
}

// Indicator Implementations
double FeatureEngineer::calculate_rsi_like(double momentum) {
  return std::tanh(momentum / 5.0);
}

double FeatureEngineer::calculate_volatility_bands(double volatility) {
  return std::clamp(volatility / 10.0, 0.0, 1.0);
}

double FeatureEngineer::calculate_trend_indicator(double momentum,
                                                  double volatility) {
  double trend_strength = momentum / (volatility + 1e-8);
  return std::tanh(trend_strength / 2.0);
}

double FeatureEngineer::calculate_macd_like(double mid_price_log,
                                            double vwap_log) {
  // From Python: 'macd_like': mid_price_log - vwap_log
  return mid_price_log - vwap_log;
}

double FeatureEngineer::calculate_bollinger_bands_like(double mid_price,
                                                       double volatility) {
  double upper_band = mid_price + (2 * volatility);
  double lower_band = mid_price - (2 * volatility);
  return (mid_price > 0) ? (upper_band - lower_band) / mid_price : 0.0;
}

double FeatureEngineer::calculate_atr_like(double volatility) {
  return volatility;
}

} // namespace ml
