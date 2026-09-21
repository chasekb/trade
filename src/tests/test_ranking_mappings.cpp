#include "trading/StrategyExpectancyHarness.hpp"

#include <iostream>
#include <string>
#include <vector>

using trade::trading::StrategyExpectancyRow;
using trade::trading::StrategyProfitabilityInput;
using trade::trading::defaultStrategyExpectancyFixtures;
using trade::trading::evaluateStrategyExpectancy;
using trade::trading::evaluateStrategyProfitabilityDiagnostic;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

const StrategyExpectancyRow *findRow(
    const std::vector<StrategyExpectancyRow> &rows, const std::string &fixture_name) {
  for (const auto &row : rows) {
    if (row.fixture_name == fixture_name) {
      return &row;
    }
  }
  return nullptr;
}

} // namespace

int main() {
  const auto report = evaluateStrategyExpectancy(defaultStrategyExpectancyFixtures());

  // The ranking mapping must prefer a known fee-positive candidate over the
  // same strategy's fee-negative candidate. This exercises the production C++
  // profitability factoring path rather than the retired Python backend.
  const auto *good = findRow(report.rows, "sma-uptrend-positive-edge");
  const auto *bad = findRow(report.rows, "sma-uptrend-fee-negative-edge");
  expect(good != nullptr && bad != nullptr, "known-good and known-bad fixtures exist");
  if (good != nullptr && bad != nullptr) {
    expect(good->diagnostics_available && bad->diagnostics_available,
           "ranking fixtures expose diagnostics");
    expect(good->fee_adjusted_expected_return_fraction >
               bad->fee_adjusted_expected_return_fraction,
           "fee-adjusted ranking puts the known-good fixture above the known-bad fixture");
    expect(good->profitability_actionable && good->filled,
           "known-good fixture remains actionable and filled");
    expect(bad->diagnostic_factor == "negative_fee_adjusted_edge" && bad->blocked &&
               !bad->filled,
           "known-bad fixture is explicitly rejected before fill");
  }

  // Signal strength remains a separate gate. A stronger otherwise-identical
  // candidate is actionable; a weaker one is rejected, not silently promoted
  // by a combined or frontend-only score.
  StrategyProfitabilityInput strength_input;
  strength_input.signal_type = "buy";
  strength_input.expected_return_available = true;
  strength_input.expected_return_fraction = 0.030;
  strength_input.round_trip_fee_fraction = 0.015;
  strength_input.slippage_buffer_fraction = 0.002;
  strength_input.min_signal_strength = 0.50;

  strength_input.signal_strength = 0.80;
  const auto strong = evaluateStrategyProfitabilityDiagnostic(strength_input);
  strength_input.signal_strength = 0.20;
  const auto weak = evaluateStrategyProfitabilityDiagnostic(strength_input);
  expect(strong.actionable, "strong candidate passes the strength gate");
  expect(!weak.actionable && weak.factor == "weak_strength",
         "weak candidate is explicitly rejected by the strength gate");
  expect(strong.fee_adjusted_expected_return_fraction ==
             weak.fee_adjusted_expected_return_fraction,
         "strength and expected-return diagnostics remain separate mappings");

  // Held and unavailable mappings must remain unchanged and fail closed.
  StrategyProfitabilityInput held_input;
  held_input.signal_type = "hold";
  held_input.expected_return_available = true;
  held_input.expected_return_fraction = 0.100;
  const auto held = evaluateStrategyProfitabilityDiagnostic(held_input);
  expect(!held.actionable && held.factor == "hold",
         "held mapping remains explicitly non-actionable");
  expect(held.fee_adjusted_expected_return_fraction == 0.0,
         "held mapping does not acquire a ranking score");

  held_input.signal_type = "buy";
  held_input.expected_return_available = false;
  const auto unavailable = evaluateStrategyProfitabilityDiagnostic(held_input);
  expect(!unavailable.actionable && unavailable.factor == "expected_return_unavailable",
         "unavailable mapping remains explicitly rejected");

  if (failures > 0) {
    std::cerr << failures << " ranking mapping expectation(s) failed" << std::endl;
    return 1;
  }
  return 0;
}