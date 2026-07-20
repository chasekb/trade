#pragma once

#include "exchange/CoinbaseAdvancedClient.hpp"

#include <map>
#include <string>
#include <vector>

namespace trade {
namespace trading {

struct CoinbaseHolding {
  std::string asset;
  double available = 0.0;
  double hold = 0.0;
  double price_usd = 0.0;
};

struct CoinbasePortfolioSnapshot {
  double cash_available = 0.0;
  double cash_hold = 0.0;
  double positions_value = 0.0;
  double total_value = 0.0;
  std::vector<CoinbaseHolding> holdings;
};

CoinbasePortfolioSnapshot buildCoinbasePortfolioSnapshot(
    const std::vector<exchange::AccountBalance> &accounts,
    const std::map<std::string, double> &prices_usd);

} // namespace trading
} // namespace trade
