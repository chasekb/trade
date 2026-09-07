#pragma once

#include "ml/DataCollector.hpp"

#include <map>
#include <nlohmann/json.hpp>
#include <string>
#include <utility>
#include <vector>

namespace trade {
namespace ml {

struct ExecutionCohortMetrics {
  std::string regime;
  int sample_count = 0;
  int winning_trades = 0;
  int losing_trades = 0;
  double win_rate = 0.0;
  double avg_pnl = 0.0;
  double profit_factor = 0.0;
  double sharpe_ratio = 0.0;
  double max_drawdown = 0.0;
  double avg_spread_percent = 0.0;
  double avg_volatility = 0.0;
};

struct ExecutionCohortAccumulator {
  std::string regime;
  int sample_count = 0;
  int winning_trades = 0;
  int losing_trades = 0;
  double pnl_sum = 0.0;
  double pnl_sum_sq = 0.0;
  double gross_profit = 0.0;
  double gross_loss = 0.0;
  double cumulative_pnl = 0.0;
  double peak_pnl = 0.0;
  double max_drawdown = 0.0;
  double spread_sum = 0.0;
  double volatility_sum = 0.0;

  void update(const OrderBookFeatures &features, const TradeOutcome &outcome);
  ExecutionCohortMetrics finalize() const;
};

std::string classify_execution_regime(const OrderBookFeatures &features);
void update_execution_cohort(std::map<std::string, ExecutionCohortAccumulator> &cohorts,
                             const OrderBookFeatures &features,
                             const TradeOutcome &outcome);
std::vector<ExecutionCohortMetrics>
finalize_execution_cohorts(const std::map<std::string, ExecutionCohortAccumulator> &cohorts);
std::vector<ExecutionCohortMetrics> summarize_execution_cohorts(
    std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples);

void to_json(nlohmann::json &j, const ExecutionCohortMetrics &m);
void from_json(const nlohmann::json &j, ExecutionCohortMetrics &m);

} // namespace ml
} // namespace trade
