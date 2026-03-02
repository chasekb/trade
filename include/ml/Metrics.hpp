#pragma once

#include "ml/ModelTrainer.hpp"
#include <cmath>
#include <stdexcept>
#include <vector>

namespace trade {
namespace ml {

class Metrics {
public:
  // Regression Metrics
  static double calculate_mse(const std::vector<double> &y_true,
                              const std::vector<double> &y_pred);
  static double calculate_r2(const std::vector<double> &y_true,
                             const std::vector<double> &y_pred);

  // Classification Metrics (assumes 1/0 for true/false)
  static double calculate_accuracy(const std::vector<int> &y_true,
                                   const std::vector<int> &y_pred);
  static double calculate_precision(const std::vector<int> &y_true,
                                    const std::vector<int> &y_pred);
  static double calculate_recall(const std::vector<int> &y_true,
                                 const std::vector<int> &y_pred);

  // Trading Metrics
  // Assumes returns are percentage returns per trade/period based on model
  // signals
  static double calculate_sharpe_ratio(const std::vector<double> &returns,
                                       double risk_free_rate = 0.0);

  // Profit factor = Gross Profit / Gross Loss
  // Gross profit is sum of all positive trades, gross loss is absolute sum of
  // all negative trades
  static double calculate_profit_factor(const std::vector<double> &pnl);
};

} // namespace ml
} // namespace trade
