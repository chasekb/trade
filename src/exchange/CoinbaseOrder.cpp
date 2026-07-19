#include "exchange/CoinbaseOrder.hpp"

#include <charconv>
#include <cmath>
#include <set>
#include <string>
#include <utility>

namespace trade {
namespace exchange {

namespace {

bool toDouble(const Json::Value &value, double &out) {
  if (value.isNumeric()) {
    out = value.asDouble();
    return true;
  }
  if (value.isString()) {
    const std::string text = value.asString();
    if (text.empty()) {
      return false;
    }
    const char *begin = text.data();
    const char *end = begin + text.size();
    const auto parsed = std::from_chars(begin, end, out, std::chars_format::general);
    return parsed.ec == std::errc() && parsed.ptr == end;
  }
  return false;
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
  if (!toDouble(order.get("filled_size", Json::Value(0.0)), parsed.filled_size) ||
      !toDouble(order.get("filled_value", Json::Value(0.0)), parsed.filled_value) ||
      !toDouble(order.get("average_filled_price", Json::Value(0.0)),
                parsed.average_filled_price) ||
      !toDouble(order.get("total_fees", Json::Value(0.0)), parsed.total_fees)) {
    if (error) {
      *error = "order fill contains malformed numeric values";
    }
    return false;
  }

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
  if (parsed.filled_size > 0.0 &&
      (!order.isMember("filled_value") || order["filled_value"].isNull() ||
       !order.isMember("average_filled_price") || order["average_filled_price"].isNull() ||
       !order.isMember("total_fees") || order["total_fees"].isNull() ||
       parsed.filled_value <= 0.0 || parsed.average_filled_price <= 0.0)) {
    if (error) {
      *error = "filled order is missing execution value, price, or actual fees";
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
