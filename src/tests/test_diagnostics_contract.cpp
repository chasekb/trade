#include "trading/DiagnosticsContract.hpp"

#include <cmath>
#include <iostream>
#include <limits>
#include <string>

using namespace trade::trading;

namespace {
int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}

DiagnosticsInput validBuy() {
  DiagnosticsInput input;
  input.strategy = "orderbook";
  input.signal_type = "buy";
  input.signal_strength = 0.9;
  input.min_signal_strength = 0.2;
  input.expected_return_available = true;
  input.expected_return_fraction = 0.03;
  input.spread_fraction = 0.001;
  input.round_trip_fee_fraction = 0.01;
  input.slippage_buffer_fraction = 0.002;
  return input;
}
} // namespace

int main() {
  expect(resolveDiagnosticsMode("orderbook", "buy") == DiagnosticsMode::Gate,
         "orderbook resolves to gate mode");
  expect(resolveDiagnosticsMode("ml_enhanced_orderbook", "sell") == DiagnosticsMode::Gate,
         "ml orderbook resolves to gate mode");
  for (const char *strategy : {"sma", "ema", "rsi", "bollinger", "macd",
                               "stochastic", "fibonacci", "dca", "buyandhold"}) {
    expect(resolveDiagnosticsMode(strategy, "buy") == DiagnosticsMode::Unavailable,
           std::string(strategy) + " explicitly resolves unavailable");
  }
  expect(resolveDiagnosticsMode("sma", "hold") == DiagnosticsMode::Report,
         "hold resolves report-only mode");

  {
    const auto result = normalizeDiagnostics(validBuy());
    expect(result.availability == DiagnosticsAvailability::Valid,
           "valid buy is available");
    expect(result.actionable, "valid buy is actionable");
    expect(result.reason_code == DiagnosticsReasonCode::Actionable,
           "valid buy has actionable reason");
    expect(std::abs(result.directional_expected_return_fraction - 0.03) < 1e-12,
           "buy preserves positive direction");
    expect(std::abs(result.fee_adjusted_expected_return_fraction - 0.017) < 1e-12,
           "buy subtracts fees spread and slippage");
  }
  {
    auto input = validBuy();
    input.signal_type = "sell";
    input.expected_return_fraction = -0.03;
    const auto result = normalizeDiagnostics(input);
    expect(result.actionable, "negative sell return is favorable");
    expect(std::abs(result.directional_expected_return_fraction - 0.03) < 1e-12,
           "sell negates expected return directionally");
  }
  {
    auto input = validBuy();
    input.expected_return_available = false;
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.availability == DiagnosticsAvailability::Unavailable,
           "missing return fails closed");
    expect(result.reason_code == DiagnosticsReasonCode::MissingExpectedReturn,
           "missing return has stable reason");
  }
  {
    auto input = validBuy();
    input.diagnostic_timestamp_seconds = 100;
    input.now_seconds = 200;
    input.max_age_seconds = 10;
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.availability == DiagnosticsAvailability::Stale,
           "stale return fails closed");
    expect(result.reason_code == DiagnosticsReasonCode::StaleDiagnostic,
           "stale return has stable reason");
  }
  {
    auto input = validBuy();
    input.expected_return_fraction = std::numeric_limits<double>::quiet_NaN();
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.availability == DiagnosticsAvailability::Malformed,
           "non-finite return fails closed");
    expect(result.reason_code == DiagnosticsReasonCode::NonFiniteDiagnostic,
           "non-finite return has stable reason");
  }
  {
    auto input = validBuy();
    input.requested_mode = DiagnosticsMode::Report;
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.report_only,
           "explicit report mode cannot authorize action");
    expect(result.reason_code == DiagnosticsReasonCode::ReportOnly,
           "report mode has stable reason");
  }
  {
    DiagnosticsInput input;
    input.strategy = "sma";
    input.signal_type = "buy";
    input.signal_strength = 0.9;
    input.expected_return_available = true;
    input.expected_return_fraction = 0.5;
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.availability == DiagnosticsAvailability::Unavailable,
           "uncalibrated strategy cannot fail open");
  }
  {
    DiagnosticsInput input;
    input.strategy = "sma";
    input.signal_type = "hold";
    const auto result = normalizeDiagnostics(input);
    expect(!result.actionable && result.report_only,
           "hold is report-only even without expected return");
    expect(result.reason_code == DiagnosticsReasonCode::ReportOnly,
           "hold has stable report-only reason");
  }

  // Live and simulated execution pass the same normalized producer values to
  // the shared contract. Keep the parity assertion here so a future caller
  // cannot silently reintroduce a mode-specific eligibility calculation.
  for (const auto &fixture : {validBuy(), [&] {
                                auto input = validBuy();
                                input.signal_type = "sell";
                                input.expected_return_fraction = -0.03;
                                return input;
                              }(), [&] {
                                auto input = validBuy();
                                input.expected_return_fraction = 0.005;
                                return input;
                              }(), [&] {
                                auto input = validBuy();
                                input.expected_return_available = false;
                                return input;
                              }()}) {
    const auto live_facing = normalizeDiagnostics(fixture);
    const auto simulated = normalizeDiagnostics(fixture);
    expect(live_facing.actionable == simulated.actionable,
           "live and simulated eligibility remain equivalent");
    expect(live_facing.reason_code == simulated.reason_code,
           "live and simulated blocker reason codes remain equivalent");
    expect(live_facing.mode == simulated.mode,
           "live and simulated diagnostics modes remain equivalent");
    expect(live_facing.fee_adjusted_expected_return_fraction ==
               simulated.fee_adjusted_expected_return_fraction,
           "live and simulated directional fee-adjusted returns remain equivalent");
  }

  if (failures != 0) {
    std::cerr << failures << " diagnostics contract expectation(s) failed\n";
    return 1;
  }
  return 0;
}
