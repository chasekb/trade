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

} // namespace trading
} // namespace trade
