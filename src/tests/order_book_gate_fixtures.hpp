#pragma once

#include "trading/PositionSizingPolicy.hpp"
#include "trading/StrategySignal.hpp"

#include <cmath>
#include <string>
#include <utility>

namespace trade::trading::test_fixtures {

// A deterministic, offline scenario shared by order-book gate tests. The
// imbalance is signed as bid-volume minus ask-volume; its sign indicates the
// observed book direction, while expected_return_fraction is kept explicit so
// tests can also model an unfavorable or fee-negative forecast.
struct OrderBookGateFixture {
  std::string signal_type = "buy";
  double imbalance = 0.0;
  double signal_strength = 0.0;
  double edge_scale_fraction = 0.024;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.001;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.22;

  double price = 100.0;
  double configured_max_notional_usd = 100.0;
  double minimum_net_pnl_usd = 1.0;
};

inline double directionalExpectedReturn(const std::string &signal_type,
                                        double favorable_edge_fraction) {
  if (signal_type == "buy") {
    return favorable_edge_fraction;
  }
  if (signal_type == "sell") {
    return -favorable_edge_fraction;
  }
  return 0.0;
}

inline OrderBookGateFixture makeOrderBookGateFixture(
    std::string signal_type = "buy", double imbalance = 0.92,
    double edge_scale_fraction = 0.024) {
  OrderBookGateFixture fixture;
  fixture.signal_type = std::move(signal_type);
  fixture.imbalance = imbalance;
  fixture.signal_strength = std::abs(imbalance);
  fixture.edge_scale_fraction = edge_scale_fraction;
  fixture.expected_return_fraction = directionalExpectedReturn(
      fixture.signal_type, std::abs(fixture.imbalance) * fixture.edge_scale_fraction);
  return fixture;
}

inline OrderBookGateFixture favorableBuy() {
  return makeOrderBookGateFixture("buy", 0.92);
}

inline OrderBookGateFixture favorableSell() {
  return makeOrderBookGateFixture("sell", -0.92);
}

inline OrderBookGateFixture weakSignal() {
  auto fixture = makeOrderBookGateFixture("buy", 0.10);
  fixture.expected_return_fraction =
      directionalExpectedReturn(fixture.signal_type,
                                 std::abs(fixture.imbalance) * fixture.edge_scale_fraction);
  return fixture;
}

inline OrderBookGateFixture zeroEdge() {
  auto fixture = favorableBuy();
  fixture.expected_return_fraction = fixture.round_trip_fee_fraction +
                                     fixture.spread_fraction +
                                     fixture.slippage_buffer_fraction;
  return fixture;
}

inline OrderBookGateFixture negativeEdge() {
  auto fixture = favorableBuy();
  fixture.expected_return_fraction = -0.005;
  return fixture;
}

inline OrderBookProfitabilityInput orderBookInput(
    const OrderBookGateFixture &fixture) {
  OrderBookProfitabilityInput input;
  input.signal_type = fixture.signal_type;
  input.signal_strength = fixture.signal_strength;
  input.expected_return_fraction = fixture.expected_return_fraction;
  input.spread_fraction = fixture.spread_fraction;
  input.round_trip_fee_fraction = fixture.round_trip_fee_fraction;
  input.slippage_buffer_fraction = fixture.slippage_buffer_fraction;
  input.min_signal_strength = fixture.min_signal_strength;
  return input;
}

inline MinimumTradeSizeInputs sizingInput(const OrderBookGateFixture &fixture) {
  MinimumTradeSizeInputs input;
  input.price = fixture.price;
  input.expected_return_fraction = fixture.expected_return_fraction;
  input.round_trip_fee_fraction = fixture.round_trip_fee_fraction;
  input.slippage_buffer_fraction = fixture.slippage_buffer_fraction;
  input.spread_fraction = fixture.spread_fraction;
  input.minimum_net_pnl_usd = fixture.minimum_net_pnl_usd;
  input.configured_max_notional_usd = fixture.configured_max_notional_usd;
  return input;
}

} // namespace trade::trading::test_fixtures
