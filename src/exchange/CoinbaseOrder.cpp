#include "exchange/CoinbaseOrder.hpp"

#include <cmath>
#include <set>
#include <string>
#include <utility>

namespace trade {
namespace exchange {

namespace {

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

} // namespace

bool parseOrderFill(const Json::Value &response, OrderFill &out, std::string *error) {
  if (!response.isObject() || !response["order"].isObject()) {
    if (error) {
      *error = "historical order response is missing order details";
    }
    return false;
  }

  const Json::Value &order = response["order"];
  OrderFill parsed;
  parsed.order_id = order.get("order_id", Json::Value("")).asString();
  parsed.status = order.get("status", Json::Value("")).asString();
  parsed.filled_size = toDouble(order.get("filled_size", Json::Value(0.0)));
  parsed.filled_value = toDouble(order.get("filled_value", Json::Value(0.0)));
  parsed.average_filled_price =
      toDouble(order.get("average_filled_price", Json::Value(0.0)));
  parsed.total_fees = toDouble(order.get("total_fees", Json::Value(0.0)));

  static const std::set<std::string> terminal_statuses = {
      "FILLED", "CANCELLED", "EXPIRED", "FAILED"};
  if (parsed.order_id.empty() || terminal_statuses.count(parsed.status) == 0) {
    if (error) {
      *error = "order is not terminal yet";
    }
    return false;
  }
  if (!std::isfinite(parsed.filled_size) || parsed.filled_size < 0.0 ||
      !std::isfinite(parsed.filled_value) || parsed.filled_value < 0.0 ||
      !std::isfinite(parsed.average_filled_price) || parsed.average_filled_price < 0.0 ||
      !std::isfinite(parsed.total_fees) || parsed.total_fees < 0.0) {
    if (error) {
      *error = "order fill contains invalid numeric values";
    }
    return false;
  }

  out = std::move(parsed);
  if (error) {
    error->clear();
  }
  return true;
}

} // namespace exchange
} // namespace trade
