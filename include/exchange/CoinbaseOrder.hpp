#pragma once

#include <json/json.h>

#include <string>

namespace trade {
namespace exchange {

struct OrderFill {
  std::string order_id;
  std::string status;
  double filled_size = 0.0;
  double filled_value = 0.0;
  double average_filled_price = 0.0;
  double total_fees = 0.0;
};

// Parse Coinbase Advanced Trade's historical-order response. Only an order
// with a positive fill is considered complete enough for actual fee accounting.
bool parseOrderFill(const Json::Value &response, OrderFill &out, std::string *error = nullptr);

} // namespace exchange
} // namespace trade
