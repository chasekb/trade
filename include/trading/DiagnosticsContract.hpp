#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace trade {
namespace trading {

enum class DiagnosticsMode {
  Gate,
  Size,
  Exit,
  Report,
  Unavailable,
};

enum class DiagnosticsAvailability {
  Valid,
  Unavailable,
  Stale,
  Malformed,
};

enum class DiagnosticsReasonCode {
  Actionable,
  ReportOnly,
  HoldSignal,
  MissingExpectedReturn,
  StaleDiagnostic,
  NonFiniteDiagnostic,
  MalformedDiagnostic,
  UnsupportedStrategy,
  UnsupportedMode,
  UnsupportedSignal,
  DirectionMismatch,
  WeakSignal,
  NonPositiveFeeAdjustedEdge,
};

const char *toString(DiagnosticsMode mode);
const char *toString(DiagnosticsAvailability availability);
const char *toString(DiagnosticsReasonCode reason);

// The ablation review approved fee-adjusted gating only for order-book paths.
// Other strategies remain explicitly unavailable until outcome-backed
// expected-return calibration exists; hold rows are report-only.
DiagnosticsMode resolveDiagnosticsMode(const std::string &strategy,
                                       const std::string &signal_type);

struct DiagnosticsInput {
  std::string strategy;
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  double min_signal_strength = 0.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;

  // A zero timestamp means that freshness is not asserted by the producer.
  // Callers that require freshness must provide both timestamps and a limit.
  std::int64_t diagnostic_timestamp_seconds = 0;
  std::int64_t now_seconds = 0;
  std::int64_t max_age_seconds = 0;
  std::optional<DiagnosticsMode> requested_mode;
};

struct NormalizedDiagnostics {
  DiagnosticsMode mode = DiagnosticsMode::Unavailable;
  DiagnosticsAvailability availability = DiagnosticsAvailability::Unavailable;
  DiagnosticsReasonCode reason_code = DiagnosticsReasonCode::MissingExpectedReturn;
  bool actionable = false;
  bool report_only = false;
  double directional_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  double fee_adjusted_expected_return_fraction = 0.0;
  std::string reason;
};

// Normalize untrusted producer diagnostics before any live-affecting decision.
// Invalid, missing, stale, non-finite, unsupported, or fee-negative values are
// never actionable. Consumers may use report_only only for explicitly
// report-only decisions; it never authorizes an order or position mutation.
NormalizedDiagnostics normalizeDiagnostics(const DiagnosticsInput &input);

} // namespace trading
} // namespace trade
