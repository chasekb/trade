#pragma once

#include <string>

namespace trade {
namespace trading {

// Pure cash-accounting helpers shared by the simulated trading engine and its
// tests. Convention: opening a long spends cash (notional + fee), opening a
// short credits the proceeds (notional - fee); closing reverses the leg. With
// this convention the identity
//   total_value == cash + signed_positions_value
// holds at every tick for both longs and shorts.

inline double openCashDelta(const std::string &side, double notional, double fee) {
  return side == "buy" ? -(notional + fee) : (notional - fee);
}

inline double closeCashDelta(const std::string &side, double exit_notional, double fee) {
  return side == "buy" ? (exit_notional - fee) : -(exit_notional + fee);
}

inline double signedPositionValue(const std::string &side, double quantity, double price) {
  const double market_value = quantity * price;
  return side == "buy" ? market_value : -market_value;
}

} // namespace trading
} // namespace trade
