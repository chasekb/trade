#include "trading/LiquidationSafety.hpp"

#include <cmath>
#include <iostream>
#include <string>

namespace {
int failures = 0;
void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}
void expect_close(double actual, double expected, const std::string &label) {
  expect(std::fabs(actual - expected) < 1e-12, label);
}
} // namespace

int main() {
  using namespace trade::trading;
  expect(liquidationAttemptAllowed(false, false), "first attempt is allowed");
  expect(!liquidationAttemptAllowed(true, false), "duplicate retry is blocked");
  expect(!liquidationAttemptAllowed(false, true), "pending duplicate is blocked");
  expect_close(cappedLiquidationQuantity(10.0, 3.0), 3.0, "quantity is capped");
  expect_close(cappedLiquidationQuantity(10.0, 20.0), 10.0, "quantity never increases exposure");
  expect_close(cappedLiquidationQuantity(10.0, -1.0), 0.0, "negative availability fails closed");
  expect_close(cappedLiquidationQuantity(10.0, std::nan("")), 0.0,
               "non-finite availability fails closed");
  expect(isTerminalLiquidationFill("FILLED"), "filled is terminal");
  expect(isTerminalLiquidationFill("CANCELLED"), "cancelled partial is terminal");
  expect(!isTerminalLiquidationFill("OPEN"), "open fill is non-terminal");
  expect(std::string(kLiquidationAction) != std::string("close"),
         "liquidation action is distinct from close");
  expect(std::string(kLiquidationTradeType) != std::string("live"),
         "liquidation trade type is distinct from ordinary live trade");
  const std::string redacted = redactSensitiveText(
      "api_key=public api_secret=supersecret password=hunter2 order_id=ok");
  expect(redacted.find("supersecret") == std::string::npos, "API secret is redacted");
  expect(redacted.find("hunter2") == std::string::npos, "password is redacted");
  expect(redacted.find("order_id=ok") != std::string::npos,
         "non-secret diagnostics are preserved");
  return failures == 0 ? 0 : 1;
}