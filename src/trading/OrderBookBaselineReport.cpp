#include "trading/OrderBookBaselineReport.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <tuple>
#include <utility>

namespace trade {
namespace trading {
namespace {

int populationRank(OrderBookRowPopulation population) {
  switch (population) {
  case OrderBookRowPopulation::live:
    return 0;
  case OrderBookRowPopulation::live_parity_paper:
    return 1;
  case OrderBookRowPopulation::simulated:
    return 2;
  }
  return 3;
}

bool finiteOrZero(double value) { return std::isfinite(value) ? value : 0.0; }

std::string normalizedStatus(const std::string &decision) {
  if (decision == "accepted" || decision == "rejected" || decision == "blocked") {
    return decision;
  }
  return "insufficient";
}

void addMetrics(OrderBookBaselineMetrics &metrics,
                const OrderBookBaselineIntent &intent) {
  ++metrics.intents;
  if (intent.status == "accepted") {
    ++metrics.accepted;
  } else if (intent.status == "rejected") {
    ++metrics.rejected;
  } else if (intent.status == "blocked") {
    ++metrics.blocked;
  } else {
    ++metrics.insufficient;
  }

  metrics.total_required_edge_fraction += intent.required_edge_fraction;
  metrics.total_fee_fraction += finiteOrZero(intent.source.fee_fraction);
  metrics.total_spread_fraction += finiteOrZero(intent.source.spread_fraction);
  metrics.total_slippage_fraction += finiteOrZero(intent.source.slippage_fraction);
  if (!intent.source.pnl.has_value() || !std::isfinite(*intent.source.pnl)) {
    return;
  }

  ++metrics.realized_outcomes;
  const double pnl = *intent.source.pnl;
  metrics.total_pnl += pnl;
  if (pnl > 0.0) {
    ++metrics.wins;
    metrics.average_win += pnl;
  } else if (pnl < 0.0) {
    ++metrics.losses;
    metrics.average_loss += -pnl;
  }
}

void finalizeMetrics(OrderBookBaselineMetrics &metrics,
                     const std::vector<const OrderBookBaselineIntent *> &rows) {
  if (metrics.wins > 0) {
    metrics.average_win /= static_cast<double>(metrics.wins);
  }
  if (metrics.losses > 0) {
    metrics.average_loss /= static_cast<double>(metrics.losses);
  }
  if (metrics.realized_outcomes > 0) {
    metrics.expectancy = metrics.total_pnl /
                         static_cast<double>(metrics.realized_outcomes);
  }

  double gross_wins = 0.0;
  double gross_losses = 0.0;
  double equity = 0.0;
  double peak_equity = 0.0;
  for (const auto *row : rows) {
    if (!row->source.pnl.has_value() || !std::isfinite(*row->source.pnl)) {
      continue;
    }
    const double pnl = *row->source.pnl;
    if (pnl > 0.0) {
      gross_wins += pnl;
    } else if (pnl < 0.0) {
      gross_losses -= pnl;
    }
    equity += pnl;
    peak_equity = std::max(peak_equity, equity);
    metrics.max_drawdown = std::max(metrics.max_drawdown, peak_equity - equity);
  }
  if (gross_losses > 0.0) {
    metrics.profit_factor = gross_wins / gross_losses;
  } else if (gross_wins > 0.0) {
    metrics.profit_factor = std::numeric_limits<double>::infinity();
  }
}

} // namespace

const char *toString(OrderBookRowPopulation population) {
  switch (population) {
  case OrderBookRowPopulation::live:
    return "live";
  case OrderBookRowPopulation::live_parity_paper:
    return "live_parity_paper";
  case OrderBookRowPopulation::simulated:
    return "simulated";
  }
  return "simulated";
}

bool OrderBookBaselineGroupKey::operator<(
    const OrderBookBaselineGroupKey &other) const {
  return std::tie(population, symbol, strategy, model_branch) <
         std::tie(other.population, other.symbol, other.strategy,
                  other.model_branch);
}

OrderBookBaselineReport generateOrderBookBaselineReport(
    std::vector<OrderBookBaselineRow> rows,
    std::string configuration_version,
    std::string source_snapshot_id) {
  std::sort(rows.begin(), rows.end(), [](const auto &lhs, const auto &rhs) {
    const int lhs_population = populationRank(lhs.population);
    const int rhs_population = populationRank(rhs.population);
    return std::tie(lhs_population, lhs.source_row_id,
                    lhs.snapshot_timestamp, lhs.symbol, lhs.strategy,
                    lhs.model_branch, lhs.signal_type, lhs.signal_strength,
                    lhs.expected_return_available, lhs.expected_return_fraction,
                    lhs.fee_fraction, lhs.spread_fraction, lhs.slippage_fraction,
                    lhs.gate_decision, lhs.gate_reason, lhs.requested_notional,
                    lhs.requested_quantity, lhs.sizing_fraction,
                    lhs.realized_outcome, lhs.pnl) <
           std::tie(rhs_population, rhs.source_row_id,
                    rhs.snapshot_timestamp, rhs.symbol, rhs.strategy,
                    rhs.model_branch, rhs.signal_type, rhs.signal_strength,
                    rhs.expected_return_available, rhs.expected_return_fraction,
                    rhs.fee_fraction, rhs.spread_fraction, rhs.slippage_fraction,
                    rhs.gate_decision, rhs.gate_reason, rhs.requested_notional,
                    rhs.requested_quantity, rhs.sizing_fraction,
                    rhs.realized_outcome, rhs.pnl);
  });

  OrderBookBaselineReport report;
  report.configuration_version = std::move(configuration_version);
  report.source_snapshot_id = std::move(source_snapshot_id);
  report.intents.reserve(rows.size());

  for (const auto &row : rows) {
    OrderBookBaselineIntent intent;
    intent.source = row;
    intent.status = normalizedStatus(row.gate_decision);

    const double expected = finiteOrZero(row.expected_return_fraction);
    if (row.signal_type == "buy") {
      intent.directional_expected_edge_fraction = expected;
    } else if (row.signal_type == "sell") {
      intent.directional_expected_edge_fraction = -expected;
    }
    intent.required_edge_fraction = std::max(0.0, finiteOrZero(row.fee_fraction)) +
                                    std::max(0.0, finiteOrZero(row.spread_fraction)) +
                                    std::max(0.0, finiteOrZero(row.slippage_fraction));
    intent.fee_adjusted_expected_return_fraction =
        intent.directional_expected_edge_fraction - intent.required_edge_fraction;

    // A row without the minimum identity fields or a recognized decision is
    // retained but cannot be treated as an executable population.
    if (row.source_row_id.empty() || row.symbol.empty() || row.strategy.empty() ||
        row.gate_decision.empty() || !row.expected_return_available ||
        !std::isfinite(row.expected_return_fraction) ||
        !std::isfinite(row.fee_fraction) || !std::isfinite(row.spread_fraction) ||
        !std::isfinite(row.slippage_fraction)) {
      intent.status = "insufficient";
    }

    report.intents.push_back(std::move(intent));
  }

  std::map<OrderBookRowPopulation, std::vector<const OrderBookBaselineIntent *>>
      populationRows;
  std::map<OrderBookBaselineGroupKey,
           std::vector<const OrderBookBaselineIntent *>> groupedRows;
  for (const auto &intent : report.intents) {
    populationRows[intent.source.population].push_back(&intent);
    groupedRows[{intent.source.population, intent.source.symbol,
                 intent.source.strategy, intent.source.model_branch}]
        .push_back(&intent);
  }

  auto summarize = [](const auto &intentRows) {
    OrderBookBaselineMetrics metrics;
    for (const auto *intent : intentRows) {
      addMetrics(metrics, *intent);
    }
    finalizeMetrics(metrics, intentRows);
    return metrics;
  };

  std::vector<const OrderBookBaselineIntent *> allRows;
  allRows.reserve(report.intents.size());
  for (const auto &intent : report.intents) {
    allRows.push_back(&intent);
  }
  report.overall = summarize(allRows);
  for (const auto &[population, intentRows] : populationRows) {
    report.by_population[population] = summarize(intentRows);
  }
  for (const auto &[key, intentRows] : groupedRows) {
    report.grouped[key] = summarize(intentRows);
  }
  return report;
}

} // namespace trading
} // namespace trade
