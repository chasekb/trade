#include "trading/DiagnosticsContract.hpp"

#include <cmath>
#include <sstream>

namespace trade {
namespace trading {
namespace {

bool finite(double value) { return std::isfinite(value); }

NormalizedDiagnostics invalid(const DiagnosticsInput &input,
                             DiagnosticsAvailability availability,
                             DiagnosticsReasonCode reason,
                             const char *message) {
  NormalizedDiagnostics result;
  result.mode = input.requested_mode.value_or(
      resolveDiagnosticsMode(input.strategy, input.signal_type));
  result.availability = availability;
  result.reason_code = reason;
  result.report_only = result.mode == DiagnosticsMode::Report;
  result.reason = message;
  return result;
}

} // namespace

const char *toString(DiagnosticsMode mode) {
  switch (mode) {
  case DiagnosticsMode::Gate:
    return "gate";
  case DiagnosticsMode::Size:
    return "size";
  case DiagnosticsMode::Exit:
    return "exit";
  case DiagnosticsMode::Report:
    return "report";
  case DiagnosticsMode::Unavailable:
    return "unavailable";
  }
  return "unavailable";
}

const char *toString(DiagnosticsAvailability availability) {
  switch (availability) {
  case DiagnosticsAvailability::Valid:
    return "valid";
  case DiagnosticsAvailability::Unavailable:
    return "unavailable";
  case DiagnosticsAvailability::Stale:
    return "stale";
  case DiagnosticsAvailability::Malformed:
    return "malformed";
  }
  return "malformed";
}

const char *toString(DiagnosticsReasonCode reason) {
  switch (reason) {
  case DiagnosticsReasonCode::Actionable:
    return "actionable";
  case DiagnosticsReasonCode::ReportOnly:
    return "report_only";
  case DiagnosticsReasonCode::HoldSignal:
    return "hold_signal";
  case DiagnosticsReasonCode::MissingExpectedReturn:
    return "missing_expected_return";
  case DiagnosticsReasonCode::StaleDiagnostic:
    return "stale_diagnostic";
  case DiagnosticsReasonCode::NonFiniteDiagnostic:
    return "non_finite_diagnostic";
  case DiagnosticsReasonCode::MalformedDiagnostic:
    return "malformed_diagnostic";
  case DiagnosticsReasonCode::UnsupportedStrategy:
    return "unsupported_strategy";
  case DiagnosticsReasonCode::UnsupportedMode:
    return "unsupported_mode";
  case DiagnosticsReasonCode::UnsupportedSignal:
    return "unsupported_signal";
  case DiagnosticsReasonCode::DirectionMismatch:
    return "direction_mismatch";
  case DiagnosticsReasonCode::WeakSignal:
    return "weak_signal";
  case DiagnosticsReasonCode::NonPositiveFeeAdjustedEdge:
    return "non_positive_fee_adjusted_edge";
  }
  return "malformed_diagnostic";
}

DiagnosticsMode resolveDiagnosticsMode(const std::string &strategy,
                                       const std::string &signal_type) {
  if (signal_type == "hold") {
    return DiagnosticsMode::Report;
  }
  if (strategy == "orderbook" || strategy == "ml_enhanced_orderbook") {
    return DiagnosticsMode::Gate;
  }
  if (strategy == "sma" || strategy == "ema" || strategy == "rsi" ||
      strategy == "bollinger" || strategy == "macd" ||
      strategy == "stochastic" || strategy == "fibonacci" ||
      strategy == "dca" || strategy == "buyandhold") {
    return DiagnosticsMode::Unavailable;
  }
  return DiagnosticsMode::Unavailable;
}

NormalizedDiagnostics normalizeDiagnostics(const DiagnosticsInput &input) {
  const auto resolved_mode =
      resolveDiagnosticsMode(input.strategy, input.signal_type);
  const auto mode = input.requested_mode.value_or(resolved_mode);
  DiagnosticsInput normalized_input = input;
  normalized_input.requested_mode = mode;

  if (input.signal_type == "hold") {
    NormalizedDiagnostics result = invalid(
        normalized_input, DiagnosticsAvailability::Valid,
        DiagnosticsReasonCode::HoldSignal, "hold signal is report-only");
    result.reason_code = DiagnosticsReasonCode::ReportOnly;
    result.reason = "hold signal is report-only";
    result.report_only = true;
    return result;
  }
  if (input.signal_type != "buy" && input.signal_type != "sell") {
    return invalid(normalized_input, DiagnosticsAvailability::Malformed,
                   DiagnosticsReasonCode::UnsupportedSignal,
                   "unsupported signal type");
  }
  const bool known_strategy =
      input.strategy == "orderbook" ||
      input.strategy == "ml_enhanced_orderbook" || input.strategy == "sma" ||
      input.strategy == "ema" || input.strategy == "rsi" ||
      input.strategy == "bollinger" || input.strategy == "macd" ||
      input.strategy == "stochastic" || input.strategy == "fibonacci" ||
      input.strategy == "dca" || input.strategy == "buyandhold";
  if (!known_strategy) {
    return invalid(normalized_input, DiagnosticsAvailability::Unavailable,
                   DiagnosticsReasonCode::UnsupportedStrategy,
                   "strategy has no approved diagnostics mode");
  }
  // A caller may explicitly downgrade a decision to report-only, but it may
  // not upgrade an approved unavailable/report mode into an executable mode.
  if (input.requested_mode.has_value() && mode != resolved_mode &&
      mode != DiagnosticsMode::Report) {
    return invalid(normalized_input, DiagnosticsAvailability::Unavailable,
                   DiagnosticsReasonCode::UnsupportedMode,
                   "requested diagnostics mode is not approved for strategy");
  }
  if (!finite(input.signal_strength) || !finite(input.min_signal_strength) ||
      !finite(input.expected_return_fraction) ||
      !finite(input.spread_fraction) ||
      !finite(input.round_trip_fee_fraction) ||
      !finite(input.slippage_buffer_fraction)) {
    return invalid(normalized_input, DiagnosticsAvailability::Malformed,
                   DiagnosticsReasonCode::NonFiniteDiagnostic,
                   "diagnostic contains a non-finite value");
  }
  if (input.signal_strength < 0.0 || input.signal_strength > 1.0 ||
      input.min_signal_strength < 0.0 || input.min_signal_strength > 1.0 ||
      input.spread_fraction < 0.0 || input.round_trip_fee_fraction < 0.0 ||
      input.slippage_buffer_fraction < 0.0 || input.max_age_seconds < 0 ||
      input.diagnostic_timestamp_seconds < 0 || input.now_seconds < 0) {
    return invalid(normalized_input, DiagnosticsAvailability::Malformed,
                   DiagnosticsReasonCode::MalformedDiagnostic,
                   "diagnostic contains an invalid value");
  }
  if (input.diagnostic_timestamp_seconds != 0 || input.now_seconds != 0 ||
      input.max_age_seconds != 0) {
    if (input.diagnostic_timestamp_seconds == 0 || input.now_seconds == 0 ||
        input.max_age_seconds == 0 ||
        input.diagnostic_timestamp_seconds > input.now_seconds ||
        input.now_seconds - input.diagnostic_timestamp_seconds >
            input.max_age_seconds) {
      return invalid(normalized_input, DiagnosticsAvailability::Stale,
                     DiagnosticsReasonCode::StaleDiagnostic,
                     "diagnostic is stale or has invalid freshness metadata");
    }
  }
  if (input.signal_strength < input.min_signal_strength) {
    return invalid(normalized_input, DiagnosticsAvailability::Valid,
                   DiagnosticsReasonCode::WeakSignal,
                   "signal strength is below the configured minimum");
  }
  if (!input.expected_return_available) {
    return invalid(normalized_input, DiagnosticsAvailability::Unavailable,
                   DiagnosticsReasonCode::MissingExpectedReturn,
                   "expected-return diagnostic is unavailable");
  }
  if (resolved_mode == DiagnosticsMode::Unavailable) {
    return invalid(normalized_input, DiagnosticsAvailability::Unavailable,
                   DiagnosticsReasonCode::MissingExpectedReturn,
                   "strategy has no approved expected-return mode");
  }

  NormalizedDiagnostics result;
  result.mode = mode;
  result.availability = DiagnosticsAvailability::Valid;
  result.required_edge_fraction = input.spread_fraction +
                                  input.round_trip_fee_fraction +
                                  input.slippage_buffer_fraction;
  result.directional_expected_return_fraction =
      input.signal_type == "buy" ? input.expected_return_fraction
                                  : -input.expected_return_fraction;
  if (result.directional_expected_return_fraction <= 0.0) {
    result.reason_code = DiagnosticsReasonCode::DirectionMismatch;
    result.reason = "expected return is not favorable for signal direction";
    return result;
  }
  result.fee_adjusted_expected_return_fraction =
      result.directional_expected_return_fraction - result.required_edge_fraction;
  if (result.fee_adjusted_expected_return_fraction <= 0.0) {
    result.reason_code = DiagnosticsReasonCode::NonPositiveFeeAdjustedEdge;
    std::ostringstream message;
    message << "directional expected return does not exceed fee/spread/slippage hurdle";
    result.reason = message.str();
    return result;
  }
  result.actionable = mode != DiagnosticsMode::Report;
  result.report_only = mode == DiagnosticsMode::Report;
  result.reason_code = result.report_only ? DiagnosticsReasonCode::ReportOnly
                                          : DiagnosticsReasonCode::Actionable;
  result.reason = result.report_only ? "diagnostic is report-only"
                                     : "fee-adjusted expected return is actionable";
  return result;
}

} // namespace trading
} // namespace trade
