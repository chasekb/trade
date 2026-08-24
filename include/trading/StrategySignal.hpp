#pragma once

#include "trading/DiagnosticsContract.hpp"

#include <cstdint>
#include <deque>
#include <optional>
#include <string>
#include <vector>

namespace trade {
namespace trading {

// Per-strategy tuning knobs, populated from the session's parameters object.
// Only the fields for the active strategy are consulted.
struct StrategyParams {
  // moving-average strategies (sma, ema)
  double short_window = 10.0;
  double long_window = 20.0;
  // rsi
  double rsi_window = 14.0;
  double rsi_overbought = 70.0;
  double rsi_oversold = 30.0;
  // bollinger
  double bb_window = 20.0;
  double bb_std_dev = 2.0;
  // macd
  double macd_fast = 12.0;
  double macd_slow = 26.0;
  double macd_signal = 9.0;
  // stochastic
  double stoch_k = 14.0;
  double stoch_d = 3.0;
  double stoch_overbought = 80.0;
  double stoch_oversold = 20.0;
  // fibonacci
  double fib_lookback = 20.0;
  std::vector<double> fib_levels = {0.236, 0.382, 0.5, 0.618, 0.786};
  // dca: ticks between purchases (the 1s-per-tick simulator compresses one
  // configured hour to one minute of ticks)
  long long dca_interval_ticks = 60LL * 24LL;
};

struct StrategySignalOutcome {
  std::string signal_type = "hold"; // "buy" | "sell" | "hold"
  double strength = 0.0;            // 0..1
  std::string reason;
};

struct OrderBookProfitabilityInput {
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.22;
};

struct OrderBookProfitabilityGate {
  bool passes = false;
  DiagnosticsAvailability availability = DiagnosticsAvailability::Unavailable;
  DiagnosticsReasonCode reason_code = DiagnosticsReasonCode::MissingExpectedReturn;
  bool report_only = false;
  double net_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  std::string reason;
};

struct StrategyProfitabilityInput {
  std::string strategy = "orderbook";
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.0;
  std::optional<DiagnosticsMode> requested_mode;
  std::int64_t diagnostic_timestamp_seconds = 0;
  std::int64_t now_seconds = 0;
  std::int64_t max_age_seconds = 0;
};

struct StrategyProfitabilityDiagnostic {
  bool actionable = false;
  bool diagnostics_available = false;
  DiagnosticsAvailability availability = DiagnosticsAvailability::Unavailable;
  DiagnosticsReasonCode reason_code = DiagnosticsReasonCode::MissingExpectedReturn;
  DiagnosticsMode mode = DiagnosticsMode::Unavailable;
  bool report_only = false;
  double directional_expected_edge_fraction = 0.0;
  double fee_adjusted_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  std::string factor = "unavailable";
  std::string reason;
};

// Evaluates the indicator-family strategies (sma, ema, rsi, bollinger, macd,
// stochastic, fibonacci, dca, buyandhold) over a price history ordered oldest
// to newest (last element = current price). Order-book strategies are handled
// by the caller. Returns hold with a "warming up" reason until the history is
// long enough for the requested indicator.
StrategySignalOutcome evaluateStrategySignal(const std::string &strategy,
                                             const std::deque<double> &prices,
                                             const StrategyParams &params,
                                             bool has_position,
                                             long long ticks_since_last_entry);

OrderBookProfitabilityGate evaluateOrderBookProfitabilityGate(
    const OrderBookProfitabilityInput &input);

// Strategy-neutral expected-return/profitability factoring. It keeps the
// directional semantics used by order-book trading explicit so every strategy
// can classify diagnostics as actionable, fee-negative, weak, hold, or
// unavailable before deciding whether to gate, size, exit, or report only.
StrategyProfitabilityDiagnostic evaluateStrategyProfitabilityDiagnostic(
    const StrategyProfitabilityInput &input);

} // namespace trading
} // namespace trade
