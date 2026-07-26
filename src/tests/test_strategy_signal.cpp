#include "trading/StrategySignal.hpp"

#include <cmath>
#include <deque>
#include <iostream>
#include <string>

using trade::trading::evaluateStrategySignal;
using trade::trading::evaluateOrderBookProfitabilityGate;
using trade::trading::OrderBookProfitabilityInput;
using trade::trading::StrategyParams;
using trade::trading::StrategySignalOutcome;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

void expectSignal(const StrategySignalOutcome &outcome, const std::string &expected,
                  const std::string &label) {
  expect(outcome.signal_type == expected,
         label + " expected " + expected + " got " + outcome.signal_type +
             " (" + outcome.reason + ")");
  expect(outcome.strength >= 0.0 && outcome.strength <= 1.0,
         label + " strength in [0,1]");
  if (expected != "hold") {
    expect(outcome.strength > 0.0, label + " nonzero strength when signaling");
  }
}

std::deque<double> linearSeries(double start, double step, std::size_t count) {
  std::deque<double> prices;
  for (std::size_t i = 0; i < count; ++i) {
    prices.push_back(start + step * static_cast<double>(i));
  }
  return prices;
}

} // namespace

int main() {
  StrategyParams params;

  // sma / ema: rising series puts the short average above the long one.
  expectSignal(evaluateStrategySignal("sma", linearSeries(100.0, 0.5, 60), params, false, 0),
               "buy", "sma uptrend");
  expectSignal(evaluateStrategySignal("sma", linearSeries(130.0, -0.5, 60), params, false, 0),
               "sell", "sma downtrend");
  expectSignal(evaluateStrategySignal("ema", linearSeries(100.0, 0.5, 60), params, false, 0),
               "buy", "ema uptrend");
  expectSignal(evaluateStrategySignal("ema", linearSeries(130.0, -0.5, 60), params, false, 0),
               "sell", "ema downtrend");

  // rsi: a monotonic rise is overbought (sell); a monotonic fall oversold (buy).
  expectSignal(evaluateStrategySignal("rsi", linearSeries(100.0, 1.0, 30), params, false, 0),
               "sell", "rsi overbought");
  expectSignal(evaluateStrategySignal("rsi", linearSeries(130.0, -1.0, 30), params, false, 0),
               "buy", "rsi oversold");

  // bollinger: flat series then a large spike/drop leaves price outside the bands.
  {
    auto spike = linearSeries(100.0, 0.0, 25);
    spike.back() = 110.0;
    expectSignal(evaluateStrategySignal("bollinger", spike, params, false, 0), "sell",
                 "bollinger spike above upper band");
    auto drop = linearSeries(100.0, 0.0, 25);
    drop.back() = 90.0;
    expectSignal(evaluateStrategySignal("bollinger", drop, params, false, 0), "buy",
                 "bollinger drop below lower band");
  }

  // macd: sustained rise keeps the MACD line above its signal line.
  expectSignal(evaluateStrategySignal("macd", linearSeries(100.0, 0.4, 80), params, false, 0),
               "buy", "macd uptrend");
  expectSignal(evaluateStrategySignal("macd", linearSeries(140.0, -0.4, 80), params, false, 0),
               "sell", "macd downtrend");

  // stochastic: price pinned at the range extremes.
  {
    auto at_low = linearSeries(120.0, -1.0, 30); // ends at the low of its range
    expectSignal(evaluateStrategySignal("stochastic", at_low, params, false, 0), "buy",
                 "stochastic at range low");
    auto at_high = linearSeries(100.0, 1.0, 30); // ends at the high of its range
    expectSignal(evaluateStrategySignal("stochastic", at_high, params, false, 0), "sell",
                 "stochastic at range high");
  }

  // fibonacci: uptrend that pulls back to the 0.5 retracement of its range.
  {
    std::deque<double> pullback;
    for (int i = 0; i <= 10; ++i) {
      pullback.push_back(100.0 + i * 2.0); // rally 100 -> 120
    }
    for (int i = 0; i < 8; ++i) {
      pullback.push_back(120.0 - i * 1.2);
    }
    pullback.push_back(110.0); // exactly the 0.5 level of the 100-120 range
    expectSignal(evaluateStrategySignal("fibonacci", pullback, params, false, 0), "buy",
                 "fibonacci pullback to support in uptrend");
  }

  // dca: first purchase immediately, then only after the interval elapses.
  {
    const auto prices = linearSeries(100.0, 0.1, 5);
    expectSignal(evaluateStrategySignal("dca", prices, params, false, 0), "buy",
                 "dca initial purchase");
    expectSignal(evaluateStrategySignal("dca", prices, params, true, 10), "hold",
                 "dca waits inside interval");
    expectSignal(evaluateStrategySignal("dca", prices, params, true,
                                        params.dca_interval_ticks),
                 "buy", "dca buys after interval");
  }

  // buyandhold: exactly one entry, then holds forever.
  expectSignal(evaluateStrategySignal("buyandhold", linearSeries(100.0, 0.0, 3), params, false, 0),
               "buy", "buyandhold establishes");
  expectSignal(evaluateStrategySignal("buyandhold", linearSeries(100.0, 0.0, 3), params, true, 1000),
               "hold", "buyandhold never re-enters");

  // warm-up: insufficient history yields hold for indicator strategies.
  for (const char *strategy : {"sma", "ema", "rsi", "bollinger", "macd", "stochastic", "fibonacci"}) {
    expectSignal(evaluateStrategySignal(strategy, linearSeries(100.0, 1.0, 3), params, false, 0),
                 "hold", std::string(strategy) + " warm-up hold");
  }

  // unknown strategies never trade.
  expectSignal(evaluateStrategySignal("mystery", linearSeries(100.0, 1.0, 50), params, false, 0),
               "hold", "unknown strategy holds");

  // order-book live entries must clear a fee/spread/slippage hurdle before
  // they are eligible for real Coinbase execution.
  {
    OrderBookProfitabilityInput gate_input;
    gate_input.signal_type = "buy";
    gate_input.signal_strength = 0.8;
    gate_input.expected_return_fraction = 0.020;
    gate_input.spread_fraction = 0.001;
    gate_input.round_trip_fee_fraction = 0.010;
    gate_input.slippage_buffer_fraction = 0.002;
    const auto passing = evaluateOrderBookProfitabilityGate(gate_input);
    expect(passing.passes, "order-book gate passes fee-adjusted edge");
    expect(passing.net_expected_return_fraction > 0.0,
           "order-book gate reports positive net edge");

    gate_input.expected_return_fraction = 0.005;
    const auto failing = evaluateOrderBookProfitabilityGate(gate_input);
    expect(!failing.passes, "order-book gate blocks fee-negative edge");
    expect(failing.reason.find("fee/spread/slippage") != std::string::npos,
           "order-book gate explains fee hurdle");

    gate_input.expected_return_fraction = -0.050;
    const auto negative_buy = evaluateOrderBookProfitabilityGate(gate_input);
    expect(!negative_buy.passes, "order-book gate blocks negative expected return buys");

    gate_input.signal_type = "sell";
    const auto favorable_sell = evaluateOrderBookProfitabilityGate(gate_input);
    expect(favorable_sell.passes, "order-book gate treats negative expected return as favorable for sells");

    // Regression coverage for the live order-book heuristic fallback: the old
    // 1.2% maximum edge could never clear the default 1.7%+ fee/spread/slippage
    // hurdle, so every fallback signal was downgraded to hold in the Live
    // Trading tab. A strong imbalance at the new 2.4% scale is actionable.
    gate_input.signal_type = "buy";
    gate_input.signal_strength = 0.92;
    gate_input.spread_fraction = 0.0;
    gate_input.round_trip_fee_fraction = 0.015;
    gate_input.slippage_buffer_fraction = 0.002;
    gate_input.expected_return_fraction = 0.012 * 0.92;
    const auto old_scale = evaluateOrderBookProfitabilityGate(gate_input);
    expect(!old_scale.passes, "old live order-book fallback scale remains below default hurdle");
    gate_input.expected_return_fraction = 0.024 * 0.92;
    const auto new_scale = evaluateOrderBookProfitabilityGate(gate_input);
    expect(new_scale.passes, "new live order-book fallback scale clears default hurdle for strong signals");
  }

  if (failures > 0) {
    std::cerr << failures << " strategy signal expectation(s) failed" << std::endl;
    return 1;
  }
  return 0;
}
