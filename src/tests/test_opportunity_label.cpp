#include "ml/DataCollector.hpp"

#include <iostream>
#include <string>

using trade::ml::compute_opportunity_label;
using trade::ml::OpportunityLabelResult;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

} // namespace

// compute_opportunity_label backs DataCollector::sync_opportunity_labels,
// which labels EVERY logged order_book_signals row (see
// DataCollector.cpp), not only the ones a strategy's raw-imbalance strength
// floor would have turned into a buy/sell signal. These tests exercise that
// function directly: it takes only price/spread/fee inputs, no signal_type
// or strength, which is what proves labeling here is independent of
// whether a signal would have fired.
int main() {
  {
    // A forward move large enough to clear the fee/spread/slippage hurdle
    // is labeled a profitable "buy" opportunity, even though nothing here
    // ever computed an order-book imbalance or a signal strength.
    const auto result = compute_opportunity_label(
        /*mid_price=*/100.0, /*forward_price=*/103.0,
        /*spread_fraction=*/0.001, /*round_trip_fee_fraction=*/0.015,
        /*slippage_buffer_fraction=*/0.002);
    expect(result.best_direction == "buy",
           "3% forward move clears the hurdle as a buy opportunity");
    expect(result.is_profitable_after_costs,
           "3% forward move is profitable after costs");
    expect(result.net_return_fraction > 0.0,
           "net_return_fraction is positive for a profitable buy");
  }

  {
    // Symmetric case: a large enough downward move is a profitable "sell"
    // opportunity.
    const auto result = compute_opportunity_label(
        100.0, 97.0, 0.001, 0.015, 0.002);
    expect(result.best_direction == "sell",
           "3% adverse forward move clears the hurdle as a sell opportunity");
    expect(result.is_profitable_after_costs,
           "3% adverse forward move is profitable after costs as a short");
  }

  {
    // A move that does not clear round-trip fees + spread + slippage must
    // not be labeled actionable in either direction. This is the case a
    // trade-outcome-only pipeline would never see labeled at all, since no
    // signal or trade exists for it — here it is still correctly labeled
    // "hold" rather than silently dropped.
    const auto result = compute_opportunity_label(
        100.0, 100.05, 0.001, 0.015, 0.002);
    expect(result.best_direction == "hold",
           "a small forward move within the cost hurdle is not actionable");
    expect(!result.is_profitable_after_costs,
           "a small forward move within the cost hurdle is not profitable");
    expect(result.net_return_fraction == 0.0,
           "net_return_fraction is zero when no direction clears the hurdle");
  }

  {
    // Boundary: a move that lands exactly on the hurdle is not profitable
    // (net edge must be strictly positive).
    const double round_trip_fee_fraction = 0.015;
    const double slippage_buffer_fraction = 0.002;
    const double spread_fraction = 0.001;
    const double required_edge =
        round_trip_fee_fraction + slippage_buffer_fraction + spread_fraction;
    const double mid_price = 100.0;
    const double forward_price = mid_price * (1.0 + required_edge);
    const auto result = compute_opportunity_label(
        mid_price, forward_price, spread_fraction, round_trip_fee_fraction,
        slippage_buffer_fraction);
    expect(result.best_direction == "hold",
           "a move exactly at the cost hurdle is not actionable");
    expect(!result.is_profitable_after_costs,
           "a move exactly at the cost hurdle is not profitable");
  }

  {
    // A wider real spread raises the required edge and can flip a
    // marginally profitable move back to hold, same directional semantics
    // as trading::evaluateOrderBookProfitabilityGate. With a 0.1% spread the
    // hurdle is 1.8%, so a 2.2% move clears it; with a 1% spread the hurdle
    // rises to 2.7%, so the same 2.2% move no longer clears it.
    const auto tight_spread = compute_opportunity_label(100.0, 102.2, 0.001, 0.015, 0.002);
    const auto wide_spread = compute_opportunity_label(100.0, 102.2, 0.01, 0.015, 0.002);
    expect(tight_spread.best_direction == "buy",
           "2.2% move clears the hurdle with a tight spread");
    expect(wide_spread.best_direction == "hold",
           "the same 2.2% move does not clear the hurdle with a much wider spread");
  }

  {
    // Invalid/zero mid_price fails safe to "hold" rather than dividing by
    // zero or fabricating a direction.
    const auto result = compute_opportunity_label(0.0, 100.0, 0.001, 0.015, 0.002);
    expect(result.best_direction == "hold", "zero mid_price fails safe to hold");
    expect(!result.is_profitable_after_costs, "zero mid_price is never profitable");
  }

  if (failures > 0) {
    std::cerr << failures << " opportunity label expectation(s) failed" << std::endl;
    return 1;
  }
  return 0;
}
