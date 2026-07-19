#include "exchange/CoinbaseOrder.hpp"

#include <cmath>
#include <iostream>
#include <string>

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

void expect_close(double actual, double expected, const std::string &label) {
  expect(std::fabs(actual - expected) < 1e-9,
         label + " expected " + std::to_string(expected) + " got " + std::to_string(actual));
}

} // namespace

int main() {
  Json::Value response(Json::objectValue);
  Json::Value order(Json::objectValue);
  order["order_id"] = "order-123";
  order["status"] = "FILLED";
  order["filled_size"] = "0.0025";
  order["filled_value"] = "250.75";
  order["average_filled_price"] = "100300.00";
  order["total_fees"] = "1.37";
  response["order"] = order;

  trade::exchange::OrderFill fill;
  std::string error;
  expect(trade::exchange::parseOrderFill(response, fill, &error),
         "filled Coinbase order parses: " + error);
  expect(fill.order_id == "order-123", "order id");
  expect(fill.status == "FILLED", "status");
  expect_close(fill.filled_size, 0.0025, "filled size");
  expect_close(fill.filled_value, 250.75, "filled value");
  expect_close(fill.average_filled_price, 100300.0, "average price");
  expect_close(fill.total_fees, 1.37, "actual fees");

  Json::Value pending(Json::objectValue);
  pending["order"]["order_id"] = "order-456";
  pending["order"]["status"] = "OPEN";
  pending["order"]["filled_size"] = "0";
  expect(!trade::exchange::parseOrderFill(pending, fill, &error),
         "unfilled order is not accepted as an actual fill");

  return failures == 0 ? 0 : 1;
}
