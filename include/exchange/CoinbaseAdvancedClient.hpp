#pragma once

#include <json/json.h>

#include <string>
#include <vector>

namespace trade {
namespace exchange {

struct CoinbaseCredentials {
  std::string api_key;
  std::string api_secret;

  bool configured() const { return !api_key.empty() && !api_secret.empty(); }
};

struct AccountBalance {
  std::string currency;
  double available = 0.0;
  double hold = 0.0;
};

struct ProductTicker {
  double price = 0.0;
  double bid = 0.0;
  double ask = 0.0;
  double volume_24h = 0.0;
};

struct OrderBookSummary {
  double best_bid = 0.0;
  double best_ask = 0.0;
  double bid_volume = 0.0;
  double ask_volume = 0.0;
  double mid = 0.0;
  double spread = 0.0;
  double imbalance = 0.0; // (bid_volume - ask_volume) / (bid_volume + ask_volume)
  int depth = 0;
};

struct OrderResult {
  bool success = false;
  std::string order_id;
  std::string client_order_id;
  std::string error;
};

// Thin client for the Coinbase Advanced Trade API (authenticated, JWT or
// legacy HMAC) plus the public Exchange market-data API (no auth). All calls
// are blocking with a bounded timeout; do not invoke while holding locks that
// API handlers contend on.
class CoinbaseAdvancedClient {
public:
  explicit CoinbaseAdvancedClient(CoinbaseCredentials credentials);

  bool configured() const { return credentials_.configured(); }

  // Authenticated: GET /api/v3/brokerage/accounts
  bool listAccounts(std::vector<AccountBalance> &out, std::string *error = nullptr);

  // Authenticated: POST /api/v3/brokerage/orders (market IOC). `amount` is a
  // quote-currency size for buys (amount_is_quote=true) or a base size.
  OrderResult placeMarketOrder(const std::string &product_id, const std::string &side,
                               double amount, bool amount_is_quote);

  // Public market data (api.exchange.coinbase.com), no credentials required.
  bool getTicker(const std::string &product_id, ProductTicker &out,
                 std::string *error = nullptr);
  bool getOrderBook(const std::string &product_id, OrderBookSummary &out,
                    std::string *error = nullptr);

private:
  Json::Value request(const std::string &method, const std::string &host,
                      const std::string &path, const std::string &body, bool authenticated,
                      std::string *error);

  CoinbaseCredentials credentials_;
};

} // namespace exchange
} // namespace trade
