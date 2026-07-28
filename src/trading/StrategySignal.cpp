#include "trading/StrategySignal.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <sstream>

namespace trade {
namespace trading {
namespace {

double clamp01(double value) { return std::clamp(value, 0.0, 1.0); }

std::size_t windowSize(double raw, std::size_t minimum = 2) {
  const long long rounded = static_cast<long long>(std::llround(std::max(1.0, raw)));
  return std::max<std::size_t>(minimum, static_cast<std::size_t>(rounded));
}

double simpleMovingAverage(const std::deque<double> &prices, std::size_t window) {
  double sum = 0.0;
  for (std::size_t i = prices.size() - window; i < prices.size(); ++i) {
    sum += prices[i];
  }
  return sum / static_cast<double>(window);
}

// EMA seeded with the first price of the usable range and folded forward.
double exponentialMovingAverage(const std::deque<double> &prices, std::size_t window) {
  const double alpha = 2.0 / (static_cast<double>(window) + 1.0);
  const std::size_t start = prices.size() > window * 3 ? prices.size() - window * 3 : 0;
  double ema = prices[start];
  for (std::size_t i = start + 1; i < prices.size(); ++i) {
    ema = alpha * prices[i] + (1.0 - alpha) * ema;
  }
  return ema;
}

double standardDeviation(const std::deque<double> &prices, std::size_t window, double mean) {
  double variance = 0.0;
  for (std::size_t i = prices.size() - window; i < prices.size(); ++i) {
    const double diff = prices[i] - mean;
    variance += diff * diff;
  }
  return std::sqrt(variance / static_cast<double>(window));
}

double relativeStrengthIndex(const std::deque<double> &prices, std::size_t window) {
  double gains = 0.0;
  double losses = 0.0;
  for (std::size_t i = prices.size() - window; i < prices.size(); ++i) {
    const double change = prices[i] - prices[i - 1];
    if (change >= 0.0) {
      gains += change;
    } else {
      losses -= change;
    }
  }
  if (losses <= 0.0) {
    return gains > 0.0 ? 100.0 : 50.0;
  }
  const double rs = gains / losses;
  return 100.0 - 100.0 / (1.0 + rs);
}

// MACD line values for the last `count` bars (oldest first).
std::vector<double> macdSeries(const std::deque<double> &prices, std::size_t fast,
                               std::size_t slow, std::size_t count) {
  std::vector<double> series;
  series.reserve(count);
  const double alpha_fast = 2.0 / (static_cast<double>(fast) + 1.0);
  const double alpha_slow = 2.0 / (static_cast<double>(slow) + 1.0);
  double ema_fast = prices[0];
  double ema_slow = prices[0];
  for (std::size_t i = 1; i < prices.size(); ++i) {
    ema_fast = alpha_fast * prices[i] + (1.0 - alpha_fast) * ema_fast;
    ema_slow = alpha_slow * prices[i] + (1.0 - alpha_slow) * ema_slow;
    if (prices.size() - i <= count) {
      series.push_back(ema_fast - ema_slow);
    }
  }
  return series;
}

StrategySignalOutcome crossoverOutcome(double fast_value, double slow_value,
                                       double reference_price, const char *label) {
  StrategySignalOutcome outcome;
  const double gap = fast_value - slow_value;
  const double normalized =
      reference_price > 0.0 ? std::abs(gap) / reference_price : 0.0;
  outcome.strength = clamp01(0.3 + normalized * 200.0);
  if (gap > 0.0) {
    outcome.signal_type = "buy";
    outcome.reason = std::string(label) + " fast above slow";
  } else if (gap < 0.0) {
    outcome.signal_type = "sell";
    outcome.reason = std::string(label) + " fast below slow";
  } else {
    outcome.signal_type = "hold";
    outcome.strength = 0.0;
    outcome.reason = std::string(label) + " flat";
  }
  return outcome;
}

StrategySignalOutcome warmingUp(const char *label) {
  StrategySignalOutcome outcome;
  outcome.reason = std::string(label) + " warming up: insufficient price history";
  return outcome;
}

} // namespace

StrategySignalOutcome evaluateStrategySignal(const std::string &strategy,
                                             const std::deque<double> &prices,
                                             const StrategyParams &params,
                                             bool has_position,
                                             long long ticks_since_last_entry) {
  StrategySignalOutcome outcome;

  if (strategy == "buyandhold") {
    if (!has_position) {
      outcome.signal_type = "buy";
      outcome.strength = 1.0;
      outcome.reason = "Buy and hold: establishing position";
    } else {
      outcome.reason = "Buy and hold: position held";
    }
    return outcome;
  }

  if (strategy == "dca") {
    const long long interval = std::max<long long>(1, params.dca_interval_ticks);
    if (!has_position || ticks_since_last_entry >= interval) {
      outcome.signal_type = "buy";
      outcome.strength = 1.0;
      outcome.reason = "DCA: scheduled purchase";
    } else {
      outcome.reason = "DCA: waiting for next interval";
    }
    return outcome;
  }

  if (prices.empty()) {
    return warmingUp(strategy.c_str());
  }
  const double last_price = prices.back();

  if (strategy == "sma" || strategy == "ema") {
    const std::size_t short_window = windowSize(params.short_window);
    const std::size_t long_window = std::max(windowSize(params.long_window), short_window + 1);
    if (prices.size() < long_window + 1) {
      return warmingUp(strategy.c_str());
    }
    if (strategy == "sma") {
      return crossoverOutcome(simpleMovingAverage(prices, short_window),
                              simpleMovingAverage(prices, long_window), last_price, "SMA");
    }
    return crossoverOutcome(exponentialMovingAverage(prices, short_window),
                            exponentialMovingAverage(prices, long_window), last_price, "EMA");
  }

  if (strategy == "rsi") {
    const std::size_t window = windowSize(params.rsi_window);
    if (prices.size() < window + 1) {
      return warmingUp("RSI");
    }
    const double rsi = relativeStrengthIndex(prices, window);
    if (rsi <= params.rsi_oversold) {
      outcome.signal_type = "buy";
      outcome.strength = clamp01(0.3 + (params.rsi_oversold - rsi) / std::max(1.0, params.rsi_oversold));
      outcome.reason = "RSI oversold";
    } else if (rsi >= params.rsi_overbought) {
      outcome.signal_type = "sell";
      outcome.strength =
          clamp01(0.3 + (rsi - params.rsi_overbought) / std::max(1.0, 100.0 - params.rsi_overbought));
      outcome.reason = "RSI overbought";
    } else {
      outcome.reason = "RSI neutral";
    }
    return outcome;
  }

  if (strategy == "bollinger") {
    const std::size_t window = windowSize(params.bb_window);
    if (prices.size() < window) {
      return warmingUp("Bollinger");
    }
    const double mean = simpleMovingAverage(prices, window);
    const double stddev = standardDeviation(prices, window, mean);
    if (stddev <= 0.0) {
      outcome.reason = "Bollinger: no volatility";
      return outcome;
    }
    const double z = (last_price - mean) / stddev;
    if (z <= -params.bb_std_dev) {
      outcome.signal_type = "buy";
      outcome.strength = clamp01(std::abs(z) / 3.0);
      outcome.reason = "Price below lower Bollinger band";
    } else if (z >= params.bb_std_dev) {
      outcome.signal_type = "sell";
      outcome.strength = clamp01(std::abs(z) / 3.0);
      outcome.reason = "Price above upper Bollinger band";
    } else {
      outcome.reason = "Price inside Bollinger bands";
    }
    return outcome;
  }

  if (strategy == "macd") {
    const std::size_t fast = windowSize(params.macd_fast);
    const std::size_t slow = std::max(windowSize(params.macd_slow), fast + 1);
    const std::size_t signal_window = windowSize(params.macd_signal);
    if (prices.size() < slow + signal_window + 1) {
      return warmingUp("MACD");
    }
    const auto macd = macdSeries(prices, fast, slow, signal_window + 1);
    if (macd.size() < signal_window) {
      return warmingUp("MACD");
    }
    const double alpha = 2.0 / (static_cast<double>(signal_window) + 1.0);
    double signal_line = macd.front();
    for (std::size_t i = 1; i < macd.size(); ++i) {
      signal_line = alpha * macd[i] + (1.0 - alpha) * signal_line;
    }
    return crossoverOutcome(macd.back(), signal_line, last_price, "MACD");
  }

  if (strategy == "stochastic") {
    const std::size_t k_window = windowSize(params.stoch_k);
    const std::size_t d_window = windowSize(params.stoch_d, 1);
    if (prices.size() < k_window + d_window) {
      return warmingUp("Stochastic");
    }
    auto percent_k_at = [&](std::size_t end_exclusive) {
      double high = prices[end_exclusive - k_window];
      double low = high;
      for (std::size_t i = end_exclusive - k_window; i < end_exclusive; ++i) {
        high = std::max(high, prices[i]);
        low = std::min(low, prices[i]);
      }
      if (high <= low) {
        return 50.0;
      }
      return (prices[end_exclusive - 1] - low) / (high - low) * 100.0;
    };
    double percent_d = 0.0;
    for (std::size_t offset = 0; offset < d_window; ++offset) {
      percent_d += percent_k_at(prices.size() - offset);
    }
    percent_d /= static_cast<double>(d_window);
    if (percent_d <= params.stoch_oversold) {
      outcome.signal_type = "buy";
      outcome.strength =
          clamp01(0.3 + (params.stoch_oversold - percent_d) / std::max(1.0, params.stoch_oversold));
      outcome.reason = "Stochastic oversold";
    } else if (percent_d >= params.stoch_overbought) {
      outcome.signal_type = "sell";
      outcome.strength = clamp01(
          0.3 + (percent_d - params.stoch_overbought) / std::max(1.0, 100.0 - params.stoch_overbought));
      outcome.reason = "Stochastic overbought";
    } else {
      outcome.reason = "Stochastic neutral";
    }
    return outcome;
  }

  if (strategy == "fibonacci") {
    const std::size_t lookback = windowSize(params.fib_lookback, 5);
    if (prices.size() < lookback) {
      return warmingUp("Fibonacci");
    }
    double high = prices[prices.size() - lookback];
    double low = high;
    for (std::size_t i = prices.size() - lookback; i < prices.size(); ++i) {
      high = std::max(high, prices[i]);
      low = std::min(low, prices[i]);
    }
    const double range = high - low;
    if (range <= 0.0) {
      outcome.reason = "Fibonacci: no range";
      return outcome;
    }
    const bool uptrend = prices.back() >= prices[prices.size() - lookback];
    const double tolerance = range * 0.03;
    for (double level : params.fib_levels) {
      // Uptrend: retracement supports below the high; downtrend: resistances
      // above the low.
      const double level_price = uptrend ? high - level * range : low + level * range;
      if (std::abs(last_price - level_price) <= tolerance) {
        outcome.signal_type = uptrend ? "buy" : "sell";
        outcome.strength = clamp01(0.3 + level * 0.7);
        outcome.reason = uptrend ? "Price at Fibonacci retracement support"
                                 : "Price at Fibonacci retracement resistance";
        return outcome;
      }
    }
    outcome.reason = "Price between Fibonacci levels";
    return outcome;
  }

  outcome.reason = "Unknown strategy: " + strategy;
  return outcome;
}

OrderBookProfitabilityGate evaluateOrderBookProfitabilityGate(
    const OrderBookProfitabilityInput &input) {
  OrderBookProfitabilityGate gate;
  gate.required_edge_fraction = std::max(0.0, input.round_trip_fee_fraction) +
                                std::max(0.0, input.spread_fraction) +
                                std::max(0.0, input.slippage_buffer_fraction);
  double expected_edge = 0.0;
  if (input.signal_type == "buy") {
    expected_edge = input.expected_return_fraction;
  } else if (input.signal_type == "sell") {
    expected_edge = -input.expected_return_fraction;
  }
  gate.net_expected_return_fraction = expected_edge - gate.required_edge_fraction;

  if (input.signal_type == "hold") {
    gate.reason = "Order book signal is hold";
    return gate;
  }
  if (input.signal_strength < input.min_signal_strength) {
    std::ostringstream oss;
    oss << "Signal strength " << input.signal_strength << " below minimum "
        << input.min_signal_strength;
    gate.reason = oss.str();
    return gate;
  }
  if (gate.net_expected_return_fraction < 0.0) {
    std::ostringstream oss;
    oss << "Expected edge " << expected_edge
        << " below fee/spread/slippage hurdle " << gate.required_edge_fraction;
    gate.reason = oss.str();
    return gate;
  }

  gate.passes = true;
  gate.reason = "Expected edge exceeds fee/spread/slippage hurdle";
  return gate;
}

StrategyProfitabilityDiagnostic evaluateStrategyProfitabilityDiagnostic(
    const StrategyProfitabilityInput &input) {
  StrategyProfitabilityDiagnostic diagnostic;
  diagnostic.required_edge_fraction = std::max(0.0, input.round_trip_fee_fraction) +
                                      std::max(0.0, input.spread_fraction) +
                                      std::max(0.0, input.slippage_buffer_fraction);

  if (input.signal_type == "hold") {
    diagnostic.factor = "hold";
    diagnostic.reason = "Strategy signal is hold";
    return diagnostic;
  }

  if (input.signal_strength < input.min_signal_strength) {
    diagnostic.factor = "weak_strength";
    std::ostringstream oss;
    oss << "Signal strength " << input.signal_strength << " below minimum "
        << input.min_signal_strength;
    diagnostic.reason = oss.str();
    return diagnostic;
  }

  if (!input.expected_return_available ||
      !std::isfinite(input.expected_return_fraction)) {
    diagnostic.factor = "expected_return_unavailable";
    diagnostic.reason = "Expected-return diagnostic is unavailable";
    return diagnostic;
  }

  diagnostic.diagnostics_available = true;
  if (input.signal_type == "buy") {
    diagnostic.directional_expected_edge_fraction = input.expected_return_fraction;
  } else if (input.signal_type == "sell") {
    diagnostic.directional_expected_edge_fraction = -input.expected_return_fraction;
  } else {
    diagnostic.factor = "unsupported_signal";
    diagnostic.reason = "Unsupported strategy signal type: " + input.signal_type;
    return diagnostic;
  }

  diagnostic.fee_adjusted_expected_return_fraction =
      diagnostic.directional_expected_edge_fraction - diagnostic.required_edge_fraction;
  if (diagnostic.fee_adjusted_expected_return_fraction < 0.0) {
    diagnostic.factor = "negative_fee_adjusted_edge";
    std::ostringstream oss;
    oss << "Expected edge " << diagnostic.directional_expected_edge_fraction
        << " below fee/spread/slippage hurdle "
        << diagnostic.required_edge_fraction;
    diagnostic.reason = oss.str();
    return diagnostic;
  }

  diagnostic.actionable = true;
  diagnostic.factor = "fee_adjusted_edge_passed";
  diagnostic.reason = "Expected edge exceeds fee/spread/slippage hurdle";
  return diagnostic;
}

} // namespace trading
} // namespace trade
