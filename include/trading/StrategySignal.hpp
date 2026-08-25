#pragma once

#include <deque>
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
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.22;
};

struct OrderBookProfitabilityGate {
  bool passes = false;
  double net_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  std::string reason;
};

struct StrategyProfitabilityInput {
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.0;
};

struct StrategyProfitabilityDiagnostic {
  bool actionable = false;
  bool diagnostics_available = false;
  double directional_expected_edge_fraction = 0.0;
  double fee_adjusted_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  std::string factor = "unavailable";
  std::string reason;
};

// Outcome-derived strength mappings are intentionally opt-in. A rule is
// usable only when its evidence and context contract are fully satisfied.
struct StrengthCalibrationBin {
  double raw_strength_min = 0.0;
  double raw_strength_max = 1.0;
  double calibrated_strength = 0.0;
  std::size_t evidence_count = 0;
};

struct StrengthCalibrationRule {
  std::string strategy;
  std::string regime = "unknown";
  double holding_period_min = 0.0;
  double holding_period_max = 0.0;
  double fee_fraction_min = 0.0;
  double fee_fraction_max = 0.0;
  std::size_t minimum_evidence = 0;
  bool validated_out_of_sample = false;
  std::vector<StrengthCalibrationBin> bins;
};

struct StrengthCalibrationContext {
  std::string regime = "unknown";
  double expected_holding_period = 0.0;
  double round_trip_fee_fraction = 0.0;
};

struct StrategyStrengthCalibration {
  bool enabled = false;
  std::vector<StrengthCalibrationRule> rules;
};

struct StrategySignalEvaluation {
  StrategySignalOutcome raw_signal;
  StrategySignalOutcome effective_signal;
  StrategyProfitabilityDiagnostic profitability;
  bool calibration_applied = false;
  std::string calibration_status = "disabled";
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

StrategySignalOutcome applyStrategyStrengthCalibration(
    const std::string &strategy,
    const StrategySignalOutcome &signal,
    const StrategyStrengthCalibration &calibration,
    const StrengthCalibrationContext &context,
    std::string *status = nullptr);

StrategySignalEvaluation evaluateStrategySignalWithDiagnostics(
    const std::string &strategy, const std::deque<double> &prices,
    const StrategyParams &params,
    const StrategyStrengthCalibration &calibration,
    const StrengthCalibrationContext &context,
    const StrategyProfitabilityInput &profitability_input,
    bool has_position, long long ticks_since_last_entry);

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
