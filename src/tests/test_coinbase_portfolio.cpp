#include "trading/CoinbasePortfolio.hpp"

#include <cmath>
#include <iostream>

namespace {
bool close(double left, double right) { return std::abs(left - right) < 1e-9; }
}

int main() {
  using trade::exchange::AccountBalance;
  using trade::trading::buildCoinbasePortfolioSnapshot;

  const std::vector<AccountBalance> accounts = {
      {"USD", 9.5, 0.25}, {"USDC", 0.5, 0.0}, {"BTC", 0.0006, 0.0002},
      {"BTC", 0.0004, 0.0}, {"ETH", 0.0, 0.01}};
  const auto snapshot = buildCoinbasePortfolioSnapshot(accounts, {{"BTC", 50000.0}, {"ETH", 2000.0}});
  if (!close(snapshot.cash_available, 10.0) || !close(snapshot.cash_hold, 0.25) ||
      !close(snapshot.positions_value, 80.0) || !close(snapshot.total_value, 90.25)) {
    std::cerr << "Coinbase account snapshot did not preserve available, hold, and marked equity" << std::endl;
    return 1;
  }
  if (snapshot.holdings.size() != 2 || !close(snapshot.holdings[0].available, 0.001) ||
      !close(snapshot.holdings[0].hold, 0.0002)) {
    std::cerr << "Coinbase holdings were not retained" << std::endl;
    return 1;
  }

  const auto json = trade::trading::coinbasePortfolioSnapshotToJson(snapshot);
  if (!close(json["cash_balance"].asDouble(), 10.0) ||
      !close(json["cash_hold"].asDouble(), 0.25) ||
      !close(json["total_positions_value"].asDouble(), 80.0) ||
      !close(json["total_value"].asDouble(), 90.25) ||
      json["holdings"].size() != 2) {
    std::cerr << "Coinbase portfolio JSON did not preserve authoritative account fields" << std::endl;
    return 1;
  }

  const auto malformed = buildCoinbasePortfolioSnapshot(
      {{"USD", std::nan(""), -2.0}, {"BTC", 1.0, 0.0}}, {{"BTC", std::nan("")}});
  if (!close(malformed.cash_available, 0.0) || !close(malformed.total_value, 0.0)) {
    std::cerr << "Malformed balances or prices must not create spendable value" << std::endl;
    return 1;
  }
  return 0;
}
