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

  Json::Value partial(Json::objectValue);
  partial["order"]["order_id"] = "order-partial";
  partial["order"]["status"] = "CANCELLED";
  partial["order"]["filled_size"] = "0.001";
  partial["order"]["filled_value"] = "100";
  partial["order"]["average_filled_price"] = "100000";
  partial["order"]["total_fees"] = "0.60";
  expect(trade::exchange::parseOrderFill(partial, fill, &error),
         "terminal partial IOC fill parses");
  expect_close(fill.filled_size, 0.001, "partial filled size");
  expect_close(fill.total_fees, 0.60, "partial actual fees");

  Json::Value rejected(Json::objectValue);
  rejected["order"]["order_id"] = "order-rejected";
  rejected["order"]["status"] = "CANCELLED";
  rejected["order"]["filled_size"] = "0";
  rejected["order"]["filled_value"] = "0";
  rejected["order"]["total_fees"] = "0";
  expect(trade::exchange::parseOrderFill(rejected, fill, &error),
         "terminal order with no fill parses for rejection handling");

  Json::Value malformed = partial;
  malformed["order"]["total_fees"] = "not-a-number";
  expect(!trade::exchange::parseOrderFill(malformed, fill, &error),
         "malformed fees never masquerade as zero actual fees");

  malformed["order"]["total_fees"] = " 0.60";
  expect(!trade::exchange::parseOrderFill(malformed, fill, &error),
         "leading whitespace is rejected");
  malformed["order"]["total_fees"] = "0x1p2";
  expect(!trade::exchange::parseOrderFill(malformed, fill, &error),
         "hexadecimal floats are rejected");
  malformed["order"]["total_fees"] = "0.60junk";
  expect(!trade::exchange::parseOrderFill(malformed, fill, &error),
         "trailing junk is rejected");

  Json::Value missing = partial;
  missing["order"].removeMember("total_fees");
  expect(!trade::exchange::parseOrderFill(missing, fill, &error),
         "filled order requires actual fees");
  missing = partial;
  missing["order"].removeMember("filled_value");
  expect(!trade::exchange::parseOrderFill(missing, fill, &error),
         "filled order requires filled value");
  missing = partial;
  missing["order"].removeMember("average_filled_price");
  expect(!trade::exchange::parseOrderFill(missing, fill, &error),
         "filled order requires average fill price");

  return failures == 0 ? 0 : 1;
}
