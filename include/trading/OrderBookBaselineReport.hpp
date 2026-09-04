#pragma once

#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace trade {
namespace trading {

enum class OrderBookRowPopulation {
  live,
  live_parity_paper,
  simulated,
};

// A captured order-book intent. Producers should populate this from their
// already-recorded signal/intent and outcome fields; report generation never
// re-runs or changes an execution gate.
struct OrderBookBaselineRow {
  std::string source_row_id;
  std::string snapshot_timestamp;
  OrderBookRowPopulation population = OrderBookRowPopulation::simulated;
  std::string symbol;
  std::string strategy;
  std::string model_branch;
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double fee_fraction = 0.0;
  double spread_fraction = 0.0;
  double slippage_fraction = 0.0;
  std::string gate_decision = "insufficient"; // accepted|rejected|blocked|insufficient
  std::string gate_reason;
  std::optional<double> requested_notional;
  std::optional<double> requested_quantity;
  std::optional<double> sizing_fraction;
  std::optional<double> realized_outcome;
  std::optional<double> pnl;
};

struct OrderBookBaselineIntent {
  OrderBookBaselineRow source;
  std::string status; // accepted|rejected|blocked|insufficient
  double directional_expected_edge_fraction = 0.0;
  double required_edge_fraction = 0.0;
  double fee_adjusted_expected_return_fraction = 0.0;
};

struct OrderBookBaselineMetrics {
  std::size_t intents = 0;
  std::size_t accepted = 0;
  std::size_t rejected = 0;
  std::size_t blocked = 0;
  std::size_t insufficient = 0;
  std::size_t realized_outcomes = 0;
  std::size_t wins = 0;
  std::size_t losses = 0;
  double total_pnl = 0.0;
  double average_win = 0.0;
  double average_loss = 0.0; // positive magnitude
  double expectancy = 0.0;
  double profit_factor = 0.0;
  double max_drawdown = 0.0;
  double total_required_edge_fraction = 0.0;
  double total_fee_fraction = 0.0;
  double total_spread_fraction = 0.0;
  double total_slippage_fraction = 0.0;
};

struct OrderBookBaselineGroupKey {
  OrderBookRowPopulation population = OrderBookRowPopulation::simulated;
  std::string symbol;
  std::string strategy;
  std::string model_branch;

  bool operator<(const OrderBookBaselineGroupKey &other) const;
};

struct OrderBookBaselineReport {
  std::string report_version = "order_book_baseline_v1";
  std::string configuration_version;
  std::string source_snapshot_id;
  std::vector<OrderBookBaselineIntent> intents;
  std::map<OrderBookBaselineGroupKey, OrderBookBaselineMetrics> grouped;
  std::map<OrderBookRowPopulation, OrderBookBaselineMetrics> by_population;
  OrderBookBaselineMetrics overall;
};

// Deterministic for a fixed row snapshot. Rows are sorted by population,
// source identifier, timestamp, symbol, strategy, and model branch. Empty or
// incomplete rows remain visible as insufficient rather than throwing or
// being silently discarded.
OrderBookBaselineReport generateOrderBookBaselineReport(
    std::vector<OrderBookBaselineRow> rows,
    std::string configuration_version = "unknown",
    std::string source_snapshot_id = "unknown");

const char *toString(OrderBookRowPopulation population);

} // namespace trading
} // namespace trade
