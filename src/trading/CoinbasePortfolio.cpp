#include "trading/CoinbasePortfolio.hpp"

#include <algorithm>
#include <cmath>

namespace trade {
namespace trading {

CoinbasePortfolioSnapshot buildCoinbasePortfolioSnapshot(
    const std::vector<exchange::AccountBalance> &accounts,
    const std::map<std::string, double> &prices_usd) {
  CoinbasePortfolioSnapshot snapshot;
  std::map<std::string, CoinbaseHolding> holdings_by_currency;
  for (const auto &account : accounts) {
    const double available = std::isfinite(account.available) ? std::max(0.0, account.available) : 0.0;
    const double hold = std::isfinite(account.hold) ? std::max(0.0, account.hold) : 0.0;
    if (account.currency == "USD" || account.currency == "USDC") {
      snapshot.cash_available += available;
      snapshot.cash_hold += hold;
      continue;
    }
    if (account.currency.empty() || available + hold <= 1e-12) {
      continue;
    }
    const auto price_it = prices_usd.find(account.currency);
    const double price = price_it != prices_usd.end() && std::isfinite(price_it->second)
                             ? std::max(0.0, price_it->second)
                             : 0.0;
    auto &holding = holdings_by_currency[account.currency];
    holding.asset = account.currency;
    holding.available += available;
    holding.hold += hold;
    holding.price_usd = price;
  }
  for (auto &[currency, holding] : holdings_by_currency) {
    snapshot.positions_value += (holding.available + holding.hold) * holding.price_usd;
    snapshot.holdings.push_back(std::move(holding));
  }
  snapshot.total_value = snapshot.cash_available + snapshot.cash_hold + snapshot.positions_value;
  return snapshot;
}

} // namespace trading
} // namespace trade
