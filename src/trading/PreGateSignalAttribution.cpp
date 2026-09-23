#include "trading/PreGateSignalAttribution.hpp"

namespace trade {
namespace trading {

PreGateSignalState resolvePreGateSignalState(const PreGateSignalInputs &inputs) {
  PreGateSignalState state;
  state.signal_generated = inputs.generated_before_gate;
  if (state.signal_generated && inputs.candidate_signal_type == "buy") {
    state.intended_side = "buy";
  } else if (state.signal_generated && inputs.candidate_signal_type == "sell") {
    state.intended_side = "sell";
  } else {
    state.intended_side = "none";
  }
  return state;
}

} // namespace trading
} // namespace trade
