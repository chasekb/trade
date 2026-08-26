#include "trading/StrategySignal.hpp"

#include <cmath>
#include <deque>
#include <iostream>
#include <string>

using trade::trading::evaluateStrategySignal;
using trade::trading::evaluateOrderBookProfitabilityGate;
using trade::trading::evaluateStrategyProfitabilityDiagnostic;
using trade::trading::evaluateStrategySignalWithDiagnostics;
using trade::trading::OrderBookProfitabilityInput;
using trade::trading::StrategyParams;
using trade::trading::StrategyProfitabilityInput;
using trade::trading::StrategySignalOutcome;
using trade::trading::StrengthCalibrationContext;
using trade::trading::StrengthCalibrationRule;
using trade::trading::StrategyStrengthCalibration;

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

  // Calibration is opt-in and fail-closed. These values are test mappings,
  // not approved production calibration constants.
  {
    StrategySignalOutcome raw;
    raw.signal_type = "buy";
    raw.strength = 0.5;
    raw.reason = "fixture signal";
    StrengthCalibrationContext context;
    context.regime = "trend";
    context.expected_holding_period = 5.0;
    context.round_trip_fee_fraction = 0.01;
    StrengthCalibrationRule rule;
    rule.strategy = "sma";
    rule.regime = "trend";
    rule.holding_period_min = 0.0;
    rule.holding_period_max = 10.0;
    rule.fee_fraction_min = 0.0;
    rule.fee_fraction_max = 0.02;
    rule.minimum_evidence = 3;
    rule.validated_out_of_sample = true;
    rule.bins = {{0.0, 0.5, 0.4, 3}, {0.5, 1.0, 0.8, 3}};
    StrategyStrengthCalibration calibration;
    calibration.enabled = true;
    calibration.rules.push_back(rule);

    std::string status;
    const auto mapped = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(status == "applied", "validated calibration applies");
    expect(mapped.strength == 0.8, "upper bin lower boundary is inclusive");

    raw.strength = 0.0;
    const auto lower = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(lower.strength == 0.4, "first bin lower boundary is inclusive");
    raw.strength = 1.0;
    const auto final = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(final.strength == 0.8, "final bin upper boundary is inclusive");

    rule.validated_out_of_sample = false;
    calibration.rules[0] = rule;
    const auto held = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(status == "not_validated" && held.strength == raw.strength,
           "unvalidated mapping is held with identity strength");

    rule.validated_out_of_sample = true;
    rule.minimum_evidence = 4;
    calibration.rules[0] = rule;
    const auto insufficient = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(status == "insufficient_evidence" && insufficient.strength == raw.strength,
           "insufficient evidence uses identity fallback");

    StrategySignalOutcome hold;
    hold.signal_type = "hold";
    hold.strength = 0.9;
    const auto held_signal = trade::trading::applyStrategyStrengthCalibration(
        "sma", hold, calibration, context, &status);
    expect(status == "hold" && held_signal.strength == 0.0,
           "calibration cannot promote or strengthen hold");

    rule.minimum_evidence = 3;
    calibration.rules[0] = rule;
    raw.strength = 0.4;
    const auto known_bad = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    raw.strength = 0.8;
    const auto known_good = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(known_good.strength > known_bad.strength,
           "validated mapping ranks known-good strength above known-bad strength");

    // Context specificity is field-wise: exact regime, then narrower holding
    // period, then narrower fee interval. Widths must not be summed because a
    // narrow fee band can otherwise lose to an unrelated holding-period band.
    StrengthCalibrationRule broad_holding;
    broad_holding.strategy = "sma";
    broad_holding.regime = "trend";
    broad_holding.holding_period_min = 0.0;
    broad_holding.holding_period_max = 2.05;
    broad_holding.fee_fraction_min = 0.0095;
    broad_holding.fee_fraction_max = 0.0105;
    broad_holding.minimum_evidence = 1;
    broad_holding.validated_out_of_sample = true;
    broad_holding.bins = {{0.0, 1.0, 0.3, 1}};
    StrengthCalibrationRule narrow_holding = broad_holding;
    narrow_holding.holding_period_min = 0.0;
    narrow_holding.holding_period_max = 2.0;
    narrow_holding.fee_fraction_min = 0.0;
    narrow_holding.fee_fraction_max = 0.1;
    narrow_holding.bins = {{0.0, 1.0, 0.9, 1}};
    StrategyStrengthCalibration competing;
    competing.enabled = true;
    competing.rules = {broad_holding, narrow_holding};
    raw.strength = 0.5;
    auto competing_context = context;
    competing_context.expected_holding_period = 1.0;
    const auto specific = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, competing, competing_context, &status);
    expect(status == "applied" && specific.strength == 0.9,
           "narrower holding-period rule wins over narrower fee rule");

    // Unsorted bins are rejected before any mapping can be applied.
    rule.bins = {{0.5, 1.0, 0.8, 3}, {0.0, 0.5, 0.4, 3}};
    calibration.rules[0] = rule;
    const auto unsorted = trade::trading::applyStrategyStrengthCalibration(
        "sma", raw, calibration, context, &status);
    expect(status == "invalid_rule" && unsorted.strength == raw.strength,
           "unsorted calibration bins use identity fallback");

    // "unknown" is an explicit fallback key, not a wildcard. It can be used
    // for a known context only when no eligible exact-regime rule exists.
    StrengthCalibrationRule unknown_regime = rule;
    unknown_regime.regime = "unknown";
    unknown_regime.validated_out_of_sample = true;
    unknown_regime.bins = {{0.0, 0.5, 0.4, 3}, {0.5, 1.0, 0.8, 3}};
    calibration.rules[0] = unknown_regime;
    auto known_context = context;
    known_context.regime = "trend";
    const auto unknown_for_known =
        trade::trading::applyStrategyStrengthCalibration(
            "sma", raw, calibration, known_context, &status);
    expect(status == "applied" && unknown_for_known.strength == 0.8,
           "unknown regime is an explicit fallback for known context");

    StrengthCalibrationRule exact_regime = unknown_regime;
    exact_regime.regime = "trend";
    exact_regime.bins = {{0.0, 0.5, 0.2, 3}, {0.5, 1.0, 0.3, 3}};
    calibration.rules = {unknown_regime, exact_regime};
    const auto exact_precedence =
        trade::trading::applyStrategyStrengthCalibration(
            "sma", raw, calibration, known_context, &status);
    expect(status == "applied" && exact_precedence.strength == 0.3,
           "exact regime takes precedence over unknown fallback");

    StrengthCalibrationRule ambiguous_fallback = unknown_regime;
    ambiguous_fallback.bins = {{0.0, 0.5, 0.6, 3}, {0.5, 1.0, 0.9, 3}};
    calibration.rules = {unknown_regime, ambiguous_fallback};
    const auto ambiguous_unknown =
        trade::trading::applyStrategyStrengthCalibration(
            "sma", raw, calibration, known_context, &status);
    expect(status == "ambiguous" && ambiguous_unknown.strength == raw.strength,
           "equally specific unknown fallbacks fail closed");
    auto unknown_context = context;
    unknown_context.regime = "unknown";
    calibration.rules = {unknown_regime};
    const auto unknown_for_unknown =
        trade::trading::applyStrategyStrengthCalibration(
            "sma", raw, calibration, unknown_context, &status);
    expect(status == "applied" && unknown_for_unknown.strength == 0.8,
           "unknown regime applies to unknown context");

    // The integrated seam keeps a held/rejected mapping at raw strength and
    // still fails closed when expected-return diagnostics are unavailable.
    rule.bins = {{0.0, 0.5, 0.4, 3}, {0.5, 1.0, 0.8, 3}};
    rule.validated_out_of_sample = false;
    calibration.rules[0] = rule;
    StrategyProfitabilityInput unavailable_profitability;
    unavailable_profitability.expected_return_available = false;
    const auto held_evaluation = evaluateStrategySignalWithDiagnostics(
        "sma", linearSeries(100.0, 0.5, 60), params, calibration, context,
        unavailable_profitability, false, 0);
    expect(held_evaluation.calibration_status == "not_validated" &&
               held_evaluation.effective_signal.strength ==
                   held_evaluation.raw_signal.strength,
           "integrated held mapping preserves raw strength");
    expect(!held_evaluation.profitability.actionable &&
               held_evaluation.profitability.factor == "expected_return_unavailable",
           "integrated missing diagnostics fail closed");

    // Restore the validated fixture for the profitability assertions below.
    rule.validated_out_of_sample = true;
    calibration.rules[0] = rule;

    StrategyProfitabilityInput profitability;
    profitability.expected_return_available = true;
    profitability.expected_return_fraction = 0.020;
    profitability.round_trip_fee_fraction = 0.010;
    profitability.slippage_buffer_fraction = 0.002;
    const auto evaluated = evaluateStrategySignalWithDiagnostics(
        "sma", linearSeries(100.0, 0.5, 60), params, calibration, context,
        profitability, false, 0);
    expect(evaluated.profitability.actionable,
           "effective calibrated strength still uses fee-adjusted diagnostic");
    profitability.expected_return_fraction = 0.005;
    const auto fee_negative = evaluateStrategySignalWithDiagnostics(
        "sma", linearSeries(100.0, 0.5, 60), params, calibration, context,
        profitability, false, 0);
    expect(!fee_negative.profitability.actionable &&
               fee_negative.profitability.factor == "negative_fee_adjusted_edge",
           "fee-negative high-strength diagnostic remains blocked");
  }

  // Strategy-neutral profitability diagnostics fail safe until expected-return
  // data is available, then apply the same directional fee-adjusted edge
  // factoring that order-book live execution uses.
  {
    StrategyProfitabilityInput diagnostic_input;
    diagnostic_input.signal_type = "buy";
    diagnostic_input.signal_strength = 0.8;
    diagnostic_input.min_signal_strength = 0.2;
    diagnostic_input.expected_return_available = false;
    diagnostic_input.expected_return_fraction = 0.050;
    diagnostic_input.round_trip_fee_fraction = 0.010;
    diagnostic_input.slippage_buffer_fraction = 0.002;
    const auto unavailable = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(!unavailable.actionable, "missing expected-return diagnostic fails safe");
    expect(unavailable.factor == "expected_return_unavailable",
           "missing expected-return diagnostic is explicitly attributed");

    diagnostic_input.expected_return_available = true;
    diagnostic_input.expected_return_fraction = 0.020;
    const auto favorable_buy = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(favorable_buy.actionable, "positive fee-adjusted buy diagnostic is actionable");
    expect(favorable_buy.factor == "fee_adjusted_edge_passed",
           "passing diagnostic records fee-adjusted factor");

    diagnostic_input.expected_return_fraction = 0.005;
    const auto weak_edge = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(!weak_edge.actionable, "fee-negative expected return blocks actionability");
    expect(weak_edge.factor == "negative_fee_adjusted_edge",
           "fee-negative diagnostic is attributed");

    diagnostic_input.expected_return_fraction = 0.012;
    const auto zero_net_edge = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(!zero_net_edge.actionable,
           "exactly fee-neutral expected return is not actionable");

    diagnostic_input.signal_type = "sell";
    diagnostic_input.expected_return_fraction = -0.020;
    const auto favorable_sell = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(favorable_sell.actionable,
           "negative expected return is favorable for sell diagnostics");

    diagnostic_input.signal_strength = 0.1;
    const auto weak_strength = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);
    expect(!weak_strength.actionable, "weak strength blocks diagnostic actionability");
    expect(weak_strength.factor == "weak_strength", "weak strength factor is recorded");
  }

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

    gate_input.expected_return_fraction = 0.013;
    const auto zero_net_gate = evaluateOrderBookProfitabilityGate(gate_input);
    expect(!zero_net_gate.passes,
           "order-book gate blocks exactly fee-neutral expected edge");

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

    gate_input.signal_strength = 0.10;
    const auto weak_signal = evaluateOrderBookProfitabilityGate(gate_input);
    expect(!weak_signal.passes, "shared order-book gate blocks weak live/simulated signals");

    gate_input.signal_type = "sell";
    gate_input.signal_strength = 0.92;
    gate_input.expected_return_fraction = -0.024 * 0.92;
    const auto strong_sell = evaluateOrderBookProfitabilityGate(gate_input);
    expect(strong_sell.passes, "shared order-book gate treats strong negative edge as actionable sell");
  }

  if (failures > 0) {
    std::cerr << failures << " strategy signal expectation(s) failed" << std::endl;
    return 1;
  }
  return 0;
}
