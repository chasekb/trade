#include "trading/PreGateSignalAttribution.hpp"

#include <iostream>
#include <string>

namespace {

bool expects(const trade::trading::PreGateSignalInputs &inputs, bool signal_generated,
             const std::string &intended_side) {
  const auto result = trade::trading::resolvePreGateSignalState(inputs);
  return result.signal_generated == signal_generated && result.intended_side == intended_side;
}

} // namespace

int main() {
  // A profitability-gate-blocked buy candidate must still report as
  // generated with its original side, not collapse into "no signal".
  trade::trading::PreGateSignalInputs blocked_buy;
  blocked_buy.generated_before_gate = true;
  blocked_buy.candidate_signal_type = "buy";
  if (!expects(blocked_buy, true, "buy")) {
    std::cerr << "Profitability-gate-blocked buy must remain generated with side=buy\n";
    return 1;
  }

  trade::trading::PreGateSignalInputs blocked_sell;
  blocked_sell.generated_before_gate = true;
  blocked_sell.candidate_signal_type = "sell";
  if (!expects(blocked_sell, true, "sell")) {
    std::cerr << "Profitability-gate-blocked sell must remain generated with side=sell\n";
    return 1;
  }

  // A genuine no-signal hold (never generated) must not report a side.
  trade::trading::PreGateSignalInputs never_generated;
  never_generated.generated_before_gate = false;
  never_generated.candidate_signal_type = "hold";
  if (!expects(never_generated, false, "none")) {
    std::cerr << "A signal that was never generated must not report an intended side\n";
    return 1;
  }

  // Defensive: an unset/inconsistent candidate type alongside a generated
  // flag must not fabricate a side.
  trade::trading::PreGateSignalInputs malformed;
  malformed.generated_before_gate = true;
  malformed.candidate_signal_type = "hold";
  if (!expects(malformed, true, "none")) {
    std::cerr << "A generated flag without a buy/sell candidate must not fabricate a side\n";
    return 1;
  }

  std::cout << "pre-gate signal attribution tests passed\n";
  return 0;
}
