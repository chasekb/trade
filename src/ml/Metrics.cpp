#include "ml/Metrics.hpp"
#include "ml/ModelTrainer.hpp"
#include "ml/ExecutionCohorts.hpp"
#include <algorithm>
#include <nlohmann/json.hpp>
#include <numeric>

namespace trade {
namespace ml {

double Metrics::calculate_mse(const std::vector<double> &y_true,
                              const std::vector<double> &y_pred) {
  if (y_true.size() != y_pred.size() || y_true.empty()) {
    return 0.0;
  }
  double sum_sq_error = 0.0;
  for (size_t i = 0; i < y_true.size(); ++i) {
    double diff = y_true[i] - y_pred[i];
    sum_sq_error += diff * diff;
  }
  return sum_sq_error / static_cast<double>(y_true.size());
}

double Metrics::calculate_r2(const std::vector<double> &y_true,
                             const std::vector<double> &y_pred) {
  if (y_true.size() != y_pred.size() || y_true.empty()) {
    return 0.0;
  }

  double mean_y = std::accumulate(y_true.begin(), y_true.end(), 0.0) /
                  static_cast<double>(y_true.size());

  double ss_tot = 0.0;
  double ss_res = 0.0;

  for (size_t i = 0; i < y_true.size(); ++i) {
    double diff_tot = y_true[i] - mean_y;
    ss_tot += diff_tot * diff_tot;

    double diff_res = y_true[i] - y_pred[i];
    ss_res += diff_res * diff_res;
  }

  if (ss_tot == 0.0)
    return 0.0; // Avoid division by zero

  return 1.0 - (ss_res / ss_tot);
}

double Metrics::calculate_accuracy(const std::vector<int> &y_true,
                                   const std::vector<int> &y_pred) {
  if (y_true.size() != y_pred.size() || y_true.empty()) {
    return 0.0;
  }
  int correct = 0;
  for (size_t i = 0; i < y_true.size(); ++i) {
    if (y_true[i] == y_pred[i]) {
      correct++;
    }
  }
  return static_cast<double>(correct) / static_cast<double>(y_true.size());
}

double Metrics::calculate_precision(const std::vector<int> &y_true,
                                    const std::vector<int> &y_pred) {
  if (y_true.size() != y_pred.size() || y_true.empty()) {
    return 0.0;
  }
  int true_positives = 0;
  int predicted_positives = 0;

  for (size_t i = 0; i < y_true.size(); ++i) {
    if (y_pred[i] == 1) {
      predicted_positives++;
      if (y_true[i] == 1) {
        true_positives++;
      }
    }
  }

  if (predicted_positives == 0)
    return 0.0;
  return static_cast<double>(true_positives) /
         static_cast<double>(predicted_positives);
}

double Metrics::calculate_recall(const std::vector<int> &y_true,
                                 const std::vector<int> &y_pred) {
  if (y_true.size() != y_pred.size() || y_true.empty()) {
    return 0.0;
  }
  int true_positives = 0;
  int actual_positives = 0;

  for (size_t i = 0; i < y_true.size(); ++i) {
    if (y_true[i] == 1) {
      actual_positives++;
      if (y_pred[i] == 1) {
        true_positives++;
      }
    }
  }

  if (actual_positives == 0)
    return 0.0;
  return static_cast<double>(true_positives) /
         static_cast<double>(actual_positives);
}

double Metrics::calculate_sharpe_ratio(const std::vector<double> &returns,
                                       double risk_free_rate) {
  if (returns.empty())
    return 0.0;

  double mean_return = std::accumulate(returns.begin(), returns.end(), 0.0) /
                       static_cast<double>(returns.size());

  double variance = 0.0;
  for (double r : returns) {
    double diff = r - mean_return;
    variance += diff * diff;
  }
  variance /= static_cast<double>(returns.size());

  double std_dev = std::sqrt(variance);

  if (std_dev == 0.0)
    return 0.0;

  // Assuming returns are daily, annualize the sharpe ratio (sqrt(252)).
  // If not daily, this constant should be parameterized.
  // We will assume 252 for generic trading days per year.
  return (mean_return - risk_free_rate) / std_dev * std::sqrt(252.0);
}

double Metrics::calculate_profit_factor(const std::vector<double> &pnl) {
  if (pnl.empty())
    return 0.0;

  double gross_profit = 0.0;
  double gross_loss = 0.0;

  for (double trade_pnl : pnl) {
    if (trade_pnl > 0) {
      gross_profit += trade_pnl;
    } else if (trade_pnl < 0) {
      gross_loss += std::abs(trade_pnl);
    }
  }

  if (gross_loss == 0.0) {
    // If there are no losses, profit factor is infinite. Return a large number.
    return gross_profit > 0 ? 999.0 : 0.0;
  }

  return gross_profit / gross_loss;
}

// JSON Serialization for ModelMetrics
void to_json(nlohmann::json &j, const ml::ModelMetrics &m) {
  j = nlohmann::json{{"accuracy", m.accuracy},
                     {"precision", m.precision},
                     {"recall", m.recall},
                     {"mse", m.mse},
                     {"r2_score", m.r2_score},
                     {"sharpe_ratio", m.sharpe_ratio},
                     {"profit_factor", m.profit_factor},
                     {"validation_strategy", m.validation_strategy},
                     {"cohort_metrics", m.cohort_metrics}};
}

void from_json(const nlohmann::json &j, ml::ModelMetrics &m) {
  m.accuracy = j.value("accuracy", 0.0);
  m.precision = j.value("precision", 0.0);
  m.recall = j.value("recall", 0.0);
  m.mse = j.value("mse", 0.0);
  m.r2_score = j.value("r2_score", 0.0);
  m.sharpe_ratio = j.value("sharpe_ratio", 0.0);
  m.profit_factor = j.value("profit_factor", 0.0);
  m.validation_strategy = j.value("validation_strategy", std::string{"random_split"});
  if (j.contains("cohort_metrics") && j["cohort_metrics"].is_array()) {
    m.cohort_metrics = j["cohort_metrics"].get<std::vector<ml::ExecutionCohortMetrics>>();
  } else {
    m.cohort_metrics.clear();
  }
}

} // namespace ml
} // namespace trade
