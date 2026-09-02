#include "ml/ExecutionCohorts.hpp"

#include <algorithm>
#include <cmath>
#include <ctime>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace trade {
namespace ml {
namespace {

double clamp_double(double value, double low, double high) {
  return std::max(low, std::min(high, value));
}

std::string bucket_spread(double spread_percent) {
  if (spread_percent < 0.0005) {
    return "low";
  }
  if (spread_percent < 0.0015) {
    return "medium";
  }
  return "high";
}

std::string bucket_imbalance(double imbalance) {
  if (imbalance <= -0.15) {
    return "bearish";
  }
  if (imbalance >= 0.15) {
    return "bullish";
  }
  return "balanced";
}

std::string bucket_volatility(double volatility) {
  if (volatility < 0.5) {
    return "low";
  }
  if (volatility < 1.5) {
    return "medium";
  }
  return "high";
}

std::string bucket_liquidity(const OrderBookFeatures &features) {
  const std::string symbol = features.symbol;
  if (features.volume_24h >= 1e9 || symbol.find("BTC") != std::string::npos ||
      symbol.find("ETH") != std::string::npos) {
    return "high";
  }
  if (features.volume_24h >= 1e7) {
    return "medium";
  }
  return "low";
}

std::string bucket_session(long long timestamp) {
  std::time_t raw = static_cast<std::time_t>(timestamp);
  std::tm utc_tm{};
#ifdef _WIN32
  gmtime_s(&utc_tm, &raw);
#else
  gmtime_r(&raw, &utc_tm);
#endif
  const int hour = utc_tm.tm_hour;
  if (hour < 6) {
    return "asia";
  }
  if (hour < 13) {
    return "europe";
  }
  if (hour < 20) {
    return "us";
  }
  return "overnight";
}

std::string build_regime_label(const OrderBookFeatures &features) {
  std::ostringstream oss;
  oss << "liquidity=" << bucket_liquidity(features)
      << "|spread=" << bucket_spread(features.spread_percent)
      << "|imbalance=" << bucket_imbalance(features.bid_ask_imbalance)
      << "|volatility=" << bucket_volatility(features.volatility)
      << "|session=" << bucket_session(features.timestamp);
  return oss.str();
}

} // namespace

void ExecutionCohortAccumulator::update(const OrderBookFeatures &features,
                                        const TradeOutcome &outcome) {
  if (regime.empty()) {
    regime = build_regime_label(features);
  }

  ++sample_count;
  if (outcome.pnl > 0.0) {
    ++winning_trades;
    gross_profit += outcome.pnl;
  } else if (outcome.pnl < 0.0) {
    ++losing_trades;
    gross_loss += std::abs(outcome.pnl);
  }

  pnl_sum += outcome.pnl;
  pnl_sum_sq += outcome.pnl * outcome.pnl;
  cumulative_pnl += outcome.pnl;
  peak_pnl = std::max(peak_pnl, cumulative_pnl);
  max_drawdown = std::max(max_drawdown, peak_pnl - cumulative_pnl);
  spread_sum += features.spread_percent;
  volatility_sum += features.volatility;
}

ExecutionCohortMetrics ExecutionCohortAccumulator::finalize() const {
  ExecutionCohortMetrics metrics;
  metrics.regime = regime;
  metrics.sample_count = sample_count;
  metrics.winning_trades = winning_trades;
  metrics.losing_trades = losing_trades;
  metrics.win_rate = sample_count > 0
                         ? static_cast<double>(winning_trades) /
                               static_cast<double>(sample_count) * 100.0
                         : 0.0;
  metrics.avg_pnl = sample_count > 0 ? pnl_sum / static_cast<double>(sample_count) : 0.0;
  metrics.avg_spread_percent =
      sample_count > 0 ? spread_sum / static_cast<double>(sample_count) : 0.0;
  metrics.avg_volatility =
      sample_count > 0 ? volatility_sum / static_cast<double>(sample_count) : 0.0;
  metrics.max_drawdown = max_drawdown;

  if (gross_loss == 0.0) {
    metrics.profit_factor = gross_profit > 0.0 ? 999.0 : 0.0;
  } else {
    metrics.profit_factor = gross_profit / gross_loss;
  }

  if (sample_count > 1) {
    const double n = static_cast<double>(sample_count);
    const double mean = pnl_sum / n;
    const double variance = std::max(0.0, (pnl_sum_sq / n) - (mean * mean));
    const double std_dev = std::sqrt(variance);
    metrics.sharpe_ratio = std_dev > 0.0 ? (mean / std_dev) * std::sqrt(252.0) : 0.0;
  }

  return metrics;
}

std::string classify_execution_regime(const OrderBookFeatures &features) {
  return build_regime_label(features);
}

void update_execution_cohort(std::map<std::string, ExecutionCohortAccumulator> &cohorts,
                             const OrderBookFeatures &features,
                             const TradeOutcome &outcome) {
  const std::string regime = classify_execution_regime(features);
  auto &cohort = cohorts[regime];
  if (cohort.regime.empty()) {
    cohort.regime = regime;
  }
  cohort.update(features, outcome);
}

std::vector<ExecutionCohortMetrics>
finalize_execution_cohorts(const std::map<std::string, ExecutionCohortAccumulator> &cohorts) {
  std::vector<ExecutionCohortMetrics> metrics;
  metrics.reserve(cohorts.size());
  for (const auto &entry : cohorts) {
    metrics.push_back(entry.second.finalize());
  }
  std::sort(metrics.begin(), metrics.end(), [](const auto &lhs, const auto &rhs) {
    if (lhs.sample_count != rhs.sample_count) {
      return lhs.sample_count > rhs.sample_count;
    }
    return lhs.regime < rhs.regime;
  });
  return metrics;
}

std::vector<ExecutionCohortMetrics> summarize_execution_cohorts(
    std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples) {
  std::sort(samples.begin(), samples.end(), [](const auto &lhs, const auto &rhs) {
    if (lhs.first.timestamp != rhs.first.timestamp) {
      return lhs.first.timestamp < rhs.first.timestamp;
    }
    return lhs.first.symbol < rhs.first.symbol;
  });

  std::map<std::string, ExecutionCohortAccumulator> cohorts;
  for (const auto &sample : samples) {
    update_execution_cohort(cohorts, sample.first, sample.second);
  }
  return finalize_execution_cohorts(cohorts);
}

void to_json(nlohmann::json &j, const ExecutionCohortMetrics &m) {
  j = nlohmann::json{{"regime", m.regime},
                     {"sample_count", m.sample_count},
                     {"winning_trades", m.winning_trades},
                     {"losing_trades", m.losing_trades},
                     {"win_rate", m.win_rate},
                     {"avg_pnl", m.avg_pnl},
                     {"profit_factor", m.profit_factor},
                     {"sharpe_ratio", m.sharpe_ratio},
                     {"max_drawdown", m.max_drawdown},
                     {"avg_spread_percent", m.avg_spread_percent},
                     {"avg_volatility", m.avg_volatility}};
}

void from_json(const nlohmann::json &j, ExecutionCohortMetrics &m) {
  m.regime = j.value("regime", "");
  m.sample_count = j.value("sample_count", 0);
  m.winning_trades = j.value("winning_trades", 0);
  m.losing_trades = j.value("losing_trades", 0);
  m.win_rate = j.value("win_rate", 0.0);
  m.avg_pnl = j.value("avg_pnl", 0.0);
  m.profit_factor = j.value("profit_factor", 0.0);
  m.sharpe_ratio = j.value("sharpe_ratio", 0.0);
  m.max_drawdown = j.value("max_drawdown", 0.0);
  m.avg_spread_percent = j.value("avg_spread_percent", 0.0);
  m.avg_volatility = j.value("avg_volatility", 0.0);
}

} // namespace ml
} // namespace trade
