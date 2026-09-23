#pragma once

#include <string>

namespace trade {
namespace trading {

// A downstream gate (profitability, model-readiness, etc.) may rewrite a
// generated buy/sell candidate's public signal_type to "hold" so the
// simulator never opens on a rejected candidate. Callers that build
// attribution/reporting JSON from a SignalRecord must not re-derive
// "was a signal generated" and "which side" from that (possibly rewritten)
// signal_type, or a genuinely-generated-then-blocked signal becomes
// indistinguishable from one where no signal was ever generated.
struct PreGateSignalInputs {
  // Whether the strategy elected a buy/sell candidate before any downstream
  // gate could veto it.
  bool generated_before_gate = false;
  // The candidate side chosen before any downstream gate: "buy", "sell", or
  // "hold". Ignored when generated_before_gate is false.
  std::string candidate_signal_type = "hold";
};

struct PreGateSignalState {
  bool signal_generated = false;
  std::string intended_side; // "buy", "sell", or "none"
};

PreGateSignalState resolvePreGateSignalState(const PreGateSignalInputs &inputs);

} // namespace trading
} // namespace trade
