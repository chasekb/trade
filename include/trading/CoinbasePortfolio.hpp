#pragma once

#include "exchange/CoinbaseAdvancedClient.hpp"

#include <json/json.h>

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

// Convert an account asset symbol to the Coinbase USD product id used by
// live positions. Preserve an already-qualified product id.
std::string coinbaseProductIdForAsset(const std::string &asset);

CoinbasePortfolioSnapshot buildCoinbasePortfolioSnapshot(
    const std::vector<exchange::AccountBalance> &accounts,
    const std::map<std::string, double> &prices_usd);

Json::Value coinbasePortfolioSnapshotToJson(
    const CoinbasePortfolioSnapshot &snapshot);

} // namespace trading
} // namespace trade
