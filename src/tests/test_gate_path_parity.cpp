#include "trading/DiagnosticsContract.hpp"
#include "trading/PositionSizingPolicy.hpp"
#include "trading/StrategySignal.hpp"

#include <cmath>
#include <iostream>
#include <string>
#include <vector>

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}

struct GateFixture {
  std::string signal_type;
  double signal_strength;
  double expected_return;
  double spread;
  double fees;
  double slippage;
  double minimum_strength = 0.22;
};

trade::trading::OrderBookProfitabilityInput liveInput(const GateFixture &fixture) {
  trade::trading::OrderBookProfitabilityInput input;
  input.signal_type = fixture.signal_type;
  input.signal_strength = fixture.signal_strength;
  input.expected_return_fraction = fixture.expected_return;
  input.spread_fraction = fixture.spread;
  input.round_trip_fee_fraction = fixture.fees;
  input.slippage_buffer_fraction = fixture.slippage;
  input.min_signal_strength = fixture.minimum_strength;
  return input;
}

trade::trading::DiagnosticsInput simulatedInput(const GateFixture &fixture) {
  trade::trading::DiagnosticsInput input;
  input.strategy = "orderbook";
  input.signal_type = fixture.signal_type;
  input.signal_strength = fixture.signal_strength;
  input.min_signal_strength = fixture.minimum_strength;
  input.expected_return_available = true;
  input.expected_return_fraction = fixture.expected_return;
  input.spread_fraction = fixture.spread;
  input.round_trip_fee_fraction = fixture.fees;
  input.slippage_buffer_fraction = fixture.slippage;
  return input;
}

void expectParity(const GateFixture &fixture, const std::string &label, bool expected_pass) {
  const auto live = trade::trading::evaluateOrderBookProfitabilityGate(liveInput(fixture));
  const auto simulated = trade::trading::normalizeDiagnostics(simulatedInput(fixture));

  expect(live.passes == expected_pass, label + " live gate result");
  expect(simulated.actionable == expected_pass, label + " simulated gate result");
  expect(live.passes == simulated.actionable, label + " live/simulated acceptance parity");
  expect(std::fabs(live.required_edge_fraction - simulated.required_edge_fraction) < 1e-12,
         label + " required edge parity");
  expect(std::fabs(live.net_expected_return_fraction -
                   simulated.fee_adjusted_expected_return_fraction) < 1e-12,
         label + " fee-adjusted edge parity");
}

} // namespace

int main() {
  // A strong positive edge clears the same gate in both service paths.
  expectParity({"buy", 0.90, 0.030, 0.001, 0.010, 0.002}, "favorable buy", true);

  // A weak order-book imbalance is rejected before profitability is considered.
  // The reason strings are intentionally service-specific, but admission is not.
  const GateFixture weak{"buy", 0.10, 0.030, 0.001, 0.010, 0.002};
  const auto weak_live = trade::trading::evaluateOrderBookProfitabilityGate(liveInput(weak));
  const auto weak_simulated = trade::trading::normalizeDiagnostics(simulatedInput(weak));
  expect(!weak_live.passes && !weak_simulated.actionable, "weak imbalance blocks both paths");
  expect(weak_live.reason.find("below minimum") != std::string::npos,
         "live weak imbalance reports strength threshold");
  expect(weak_simulated.reason_code == trade::trading::DiagnosticsReasonCode::WeakSignal,
         "simulated weak imbalance reports stable weak-signal reason");

  // The strength boundary is inclusive: a signal exactly at the configured
  // minimum is eligible, while the immediately lower value remains blocked.
  GateFixture at_minimum = weak;
  at_minimum.signal_strength = 0.22;
  const auto at_minimum_live = trade::trading::evaluateOrderBookProfitabilityGate(
      liveInput(at_minimum));
  const auto at_minimum_simulated =
      trade::trading::normalizeDiagnostics(simulatedInput(at_minimum));
  expect(at_minimum_live.passes && at_minimum_simulated.actionable,
         "minimum strength boundary admits both paths");
  GateFixture below_minimum = at_minimum;
  below_minimum.signal_strength = 0.22 - 1e-9;
  const auto below_minimum_live = trade::trading::evaluateOrderBookProfitabilityGate(
      liveInput(below_minimum));
  const auto below_minimum_simulated =
      trade::trading::normalizeDiagnostics(simulatedInput(below_minimum));
  expect(!below_minimum_live.passes && !below_minimum_simulated.actionable,
         "below-minimum strength boundary blocks both paths");

  // Directional handling must agree: a negative expected return is favorable
  // for a sell, but not for a buy.
  expectParity({"buy", 0.90, -0.030, 0.001, 0.010, 0.002},
               "negative expected-return buy", false);
  expectParity({"sell", 0.90, -0.030, 0.001, 0.010, 0.002},
               "negative expected-return sell", true);

  // Fees, spread, and slippage consuming the entire edge must fail closed,
  // including the exactly fee-neutral boundary.
  expectParity({"buy", 0.90, 0.013, 0.001, 0.010, 0.002},
               "fee-neutral buy", false);
  expectParity({"buy", 0.90, 0.012, 0.001, 0.010, 0.002},
               "fee-negative buy", false);

  // Both services pass the same signal-derived sizing inputs to the shared
  // sizing contract. Stronger inputs scale larger, while the configured base
  // remains a hard maximum.
  trade::trading::PositionSizingInputs weak_size{};
  weak_size.base_usd = 1000.0;
  weak_size.signal_strength = 0.35;
  weak_size.win_probability = 0.42;
  weak_size.expected_return = 0.005;
  weak_size.model_confidence = 0.35;
  weak_size.spread_percent = 0.01;
  weak_size.live_profit_factor = 1.0;

  trade::trading::PositionSizingInputs strong_size = weak_size;
  strong_size.signal_strength = 0.90;
  strong_size.win_probability = 0.72;
  strong_size.expected_return = 0.030;
  strong_size.model_confidence = 0.90;
  strong_size.spread_percent = 0.001;

  const double live_weak_size = trade::trading::calculate_position_size_usd(weak_size);
  const double simulated_weak_size = trade::trading::calculate_position_size_usd(weak_size);
  const double live_strong_size = trade::trading::calculate_position_size_usd(strong_size);
  const double simulated_strong_size = trade::trading::calculate_position_size_usd(strong_size);
  expect(std::fabs(live_weak_size - simulated_weak_size) < 1e-12,
         "weak sizing parity");
  expect(std::fabs(live_strong_size - simulated_strong_size) < 1e-12,
         "strong sizing parity");
  expect(live_strong_size > live_weak_size, "strong signal scales above weak signal");
  expect(live_strong_size <= strong_size.base_usd, "sizing never exceeds configured base");

  if (failures != 0) {
    std::cerr << failures << " gate-path parity expectation(s) failed\n";
    return 1;
  }
  return 0;
}
