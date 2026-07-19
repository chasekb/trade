#include "exchange/CoinbaseAdvancedClient.hpp"

#include "exchange/CoinbaseAuth.hpp"
#include "utils/Logger.hpp"

#include <drogon/HttpClient.h>
#include <drogon/drogon.h>

#include <atomic>
#include <chrono>
#include <cstdio>
#include <future>
#include <memory>
#include <random>
#include <sstream>

namespace trade {
namespace exchange {

namespace {

constexpr char kAdvancedTradeHost[] = "api.coinbase.com";
constexpr char kPublicExchangeHost[] = "api.exchange.coinbase.com";
constexpr double kRequestTimeoutSeconds = 10.0;

double toDouble(const Json::Value &value, double fallback = 0.0) {
  if (value.isNumeric()) {
    return value.asDouble();
  }
  if (value.isString()) {
    try {
      return std::stod(value.asString());
    } catch (...) {
    }
  }
  return fallback;
}

std::string randomHex(std::size_t bytes) {
  static thread_local std::mt19937_64 rng(std::random_device{}());
  static const char hex[] = "0123456789abcdef";
  std::string out;
  out.reserve(bytes * 2);
  for (std::size_t i = 0; i < bytes; ++i) {
    const unsigned char b = static_cast<unsigned char>(rng() & 0xFF);
    out += hex[(b >> 4) & 0xF];
    out += hex[b & 0xF];
  }
  return out;
}

std::string formatAmount(double amount) {
  char buffer[64];
  std::snprintf(buffer, sizeof(buffer), "%.8f", amount);
  std::string out(buffer);
  // Trim trailing zeros but keep at least one decimal digit.
  const auto dot = out.find('.');
  if (dot != std::string::npos) {
    auto last = out.find_last_not_of('0');
    if (last == dot) {
      ++last;
    }
    out.erase(last + 1);
  }
  return out;
}

Json::Value parseJson(const std::string &text, std::string *error) {
  Json::Value root;
  Json::CharReaderBuilder builder;
  std::string errs;
  std::istringstream stream(text);
  if (!Json::parseFromStream(builder, stream, &root, &errs)) {
    if (error) {
      *error = "invalid JSON response: " + errs;
    }
    return Json::Value();
  }
  return root;
}

} // namespace

CoinbaseAdvancedClient::CoinbaseAdvancedClient(CoinbaseCredentials credentials)
    : credentials_(std::move(credentials)) {}

Json::Value CoinbaseAdvancedClient::request(const std::string &method, const std::string &host,
                                            const std::string &path, const std::string &body,
                                            bool authenticated, std::string *error) {
  auto req = drogon::HttpRequest::newHttpRequest();
  req->setMethod(method == "POST" ? drogon::Post : drogon::Get);
  req->setPath(path);
  if (!body.empty()) {
    req->setBody(body);
    req->setContentTypeCode(drogon::CT_APPLICATION_JSON);
  }
  req->addHeader("Accept", "application/json");
  req->addHeader("User-Agent", "trade-bot-cpp/1.0");

  if (authenticated) {
    if (!credentials_.configured()) {
      if (error) {
        *error = "Coinbase API credentials are not configured";
      }
      return Json::Value();
    }

    // The signed path excludes the query string.
    const std::string signing_path = path.substr(0, path.find('?'));
    const long long now = std::chrono::duration_cast<std::chrono::seconds>(
                              std::chrono::system_clock::now().time_since_epoch())
                              .count();

    if (secretIsEcPrivateKeyPem(credentials_.api_secret)) {
      const std::string uri = method + " " + host + signing_path;
      std::string jwt_error;
      const std::string jwt = buildEs256Jwt(credentials_.api_key, credentials_.api_secret, uri,
                                            now, randomHex(16), &jwt_error);
      if (jwt.empty()) {
        if (error) {
          *error = "JWT signing failed: " + jwt_error;
        }
        return Json::Value();
      }
      req->addHeader("Authorization", "Bearer " + jwt);
    } else {
      const std::string timestamp = std::to_string(now);
      const std::string signature =
          hmacSha256Hex(credentials_.api_secret, timestamp + method + signing_path + body);
      req->addHeader("CB-ACCESS-KEY", credentials_.api_key);
      req->addHeader("CB-ACCESS-SIGN", signature);
      req->addHeader("CB-ACCESS-TIMESTAMP", timestamp);
    }
  }

  auto client = drogon::HttpClient::newHttpClient("https://" + host);

  auto promise = std::make_shared<std::promise<std::pair<drogon::ReqResult, std::string>>>();
  auto future = promise->get_future();
  auto fulfilled = std::make_shared<std::atomic_bool>(false);
  client->sendRequest(
      req,
      [promise, fulfilled](drogon::ReqResult result, const drogon::HttpResponsePtr &resp) {
        if (fulfilled->exchange(true)) {
          return;
        }
        std::string payload;
        if (result == drogon::ReqResult::Ok && resp) {
          payload = std::to_string(static_cast<int>(resp->getStatusCode())) + "\n" +
                    std::string(resp->getBody());
        }
        promise->set_value({result, payload});
      },
      kRequestTimeoutSeconds);

  if (future.wait_for(std::chrono::seconds(15)) != std::future_status::ready) {
    if (error) {
      *error = "request timed out";
    }
    return Json::Value();
  }

  const auto [result, payload] = future.get();
  if (result != drogon::ReqResult::Ok || payload.empty()) {
    if (error) {
      *error = "request failed (network or TLS error)";
    }
    return Json::Value();
  }

  const auto newline = payload.find('\n');
  const int status_code = std::stoi(payload.substr(0, newline));
  const std::string response_body = payload.substr(newline + 1);

  std::string parse_error;
  Json::Value json = parseJson(response_body, &parse_error);
  if (status_code < 200 || status_code >= 300) {
    if (error) {
      std::string detail = parse_error.empty() ? response_body.substr(0, 300) : parse_error;
      if (json.isObject()) {
        const Json::Value message = json.get("message", json.get("error", Json::Value("")));
        if (message.isString() && !message.asString().empty()) {
          detail = message.asString();
        }
      }
      *error = "HTTP " + std::to_string(status_code) + ": " + detail;
    }
    return Json::Value();
  }
  if (json.isNull() && !parse_error.empty()) {
    if (error) {
      *error = parse_error;
    }
  }
  return json;
}

bool CoinbaseAdvancedClient::listAccounts(std::vector<AccountBalance> &out, std::string *error) {
  const Json::Value json =
      request("GET", kAdvancedTradeHost, "/api/v3/brokerage/accounts?limit=250", "", true, error);
  if (!json.isObject() || !json.isMember("accounts")) {
    return false;
  }

  out.clear();
  for (const auto &account : json["accounts"]) {
    AccountBalance balance;
    balance.currency = account.get("currency", Json::Value("")).asString();
    balance.available =
        toDouble(account.get("available_balance", Json::Value(Json::objectValue))
                     .get("value", Json::Value(0.0)));
    balance.hold = toDouble(
        account.get("hold", Json::Value(Json::objectValue)).get("value", Json::Value(0.0)));
    if (!balance.currency.empty()) {
      out.push_back(balance);
    }
  }
  return true;
}

OrderResult CoinbaseAdvancedClient::placeMarketOrder(const std::string &product_id,
                                                     const std::string &side, double amount,
                                                     bool amount_is_quote) {
  OrderResult result;
  if (amount <= 0.0) {
    result.error = "amount must be positive";
    return result;
  }

  result.client_order_id = "trade-" + randomHex(12);

  Json::Value config(Json::objectValue);
  Json::Value market(Json::objectValue);
  market[amount_is_quote ? "quote_size" : "base_size"] = formatAmount(amount);
  config["market_market_ioc"] = market;

  Json::Value order(Json::objectValue);
  order["client_order_id"] = result.client_order_id;
  order["product_id"] = product_id;
  order["side"] = side == "sell" || side == "SELL" ? "SELL" : "BUY";
  order["order_configuration"] = config;

  Json::StreamWriterBuilder writer;
  writer["indentation"] = "";
  const std::string body = Json::writeString(writer, order);

  std::string error;
  const Json::Value json =
      request("POST", kAdvancedTradeHost, "/api/v3/brokerage/orders", body, true, &error);
  if (!json.isObject()) {
    result.error = error.empty() ? "order request failed" : error;
    return result;
  }

  if (json.get("success", Json::Value(false)).asBool()) {
    result.success = true;
    result.order_id = json.get("success_response", Json::Value(Json::objectValue))
                          .get("order_id", Json::Value(""))
                          .asString();
    return result;
  }

  const Json::Value error_response = json.get("error_response", Json::Value(Json::objectValue));
  std::string message = error_response.get("message", Json::Value("")).asString();
  if (message.empty()) {
    message = error_response.get("error", Json::Value("order rejected")).asString();
  }
  result.error = message;
  return result;
}

bool CoinbaseAdvancedClient::getTicker(const std::string &product_id, ProductTicker &out,
                                       std::string *error) {
  const Json::Value json = request("GET", kPublicExchangeHost,
                                   "/products/" + product_id + "/ticker", "", false, error);
  if (!json.isObject() || !json.isMember("price")) {
    if (error && error->empty()) {
      *error = "unexpected ticker response";
    }
    return false;
  }
  out.price = toDouble(json["price"]);
  out.bid = toDouble(json.get("bid", Json::Value(0.0)));
  out.ask = toDouble(json.get("ask", Json::Value(0.0)));
  out.volume_24h = toDouble(json.get("volume", Json::Value(0.0)));
  return out.price > 0.0;
}

bool CoinbaseAdvancedClient::getOrderBook(const std::string &product_id, OrderBookSummary &out,
                                          std::string *error) {
  const Json::Value json = request("GET", kPublicExchangeHost,
                                   "/products/" + product_id + "/book?level=2", "", false, error);
  if (!json.isObject() || !json.isMember("bids") || !json.isMember("asks")) {
    if (error && error->empty()) {
      *error = "unexpected order book response";
    }
    return false;
  }

  constexpr int kLevels = 20;
  int levels = 0;
  for (const auto &bid : json["bids"]) {
    if (levels >= kLevels || !bid.isArray() || bid.size() < 2) {
      break;
    }
    if (levels == 0) {
      out.best_bid = toDouble(bid[0]);
    }
    out.bid_volume += toDouble(bid[1]);
    ++levels;
  }
  int ask_levels = 0;
  for (const auto &ask : json["asks"]) {
    if (ask_levels >= kLevels || !ask.isArray() || ask.size() < 2) {
      break;
    }
    if (ask_levels == 0) {
      out.best_ask = toDouble(ask[0]);
    }
    out.ask_volume += toDouble(ask[1]);
    ++ask_levels;
  }

  out.depth = std::min(levels, ask_levels);
  if (out.best_bid <= 0.0 || out.best_ask <= 0.0) {
    if (error) {
      *error = "order book is empty";
    }
    return false;
  }
  out.mid = (out.best_bid + out.best_ask) / 2.0;
  out.spread = out.best_ask - out.best_bid;
  const double total_volume = out.bid_volume + out.ask_volume;
  out.imbalance = total_volume > 0.0 ? (out.bid_volume - out.ask_volume) / total_volume : 0.0;
  return true;
}

} // namespace exchange
} // namespace trade
