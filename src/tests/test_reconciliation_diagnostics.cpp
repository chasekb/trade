#include "trading/ReconciliationDiagnostics.hpp"

#include <cmath>
#include <iostream>

using trade::trading::ReconciliationDiagnostics;

int main() {
  int failures = 0;
  const auto expect = [&](bool condition, const char *label) {
    if (!condition) {
      std::cerr << "FAIL: " << label << '\n';
      ++failures;
    }
  };

  const auto age = ReconciliationDiagnostics::dataAge(100, 145);
  expect(age.available && age.seconds == 45, "data age uses injected timestamps");
  expect(!ReconciliationDiagnostics::dataAge(0, 145).available,
         "missing observation has no age");
  expect(!ReconciliationDiagnostics::dataAge(200, 145).available,
         "future observation fails closed");

  ReconciliationDiagnostics diagnostics(true);
  diagnostics.reset({"BTC-USD", "ETH-USD"});
  diagnostics.recordFetchAttempt("BTC-USD");
  diagnostics.recordFetchResult("BTC-USD", false, 100);
  diagnostics.recordFetchAttempt("BTC-USD");
  diagnostics.recordFetchResult("BTC-USD", true, 110);
  diagnostics.recordSignal(true);
  diagnostics.recordSignal(false);
  diagnostics.recordGateOutcome("passed");
  diagnostics.recordGateOutcome("blocked");
  diagnostics.recordBlocker("stale_data");
  diagnostics.recordPaperIntent();
  diagnostics.recordFill();

  const Json::Value output = diagnostics.toJson(125);
  expect(output["enabled"].asBool(), "enabled diagnostics are marked enabled");
  expect(output["selected_symbol_count"].asUInt() == 2,
         "selected universe is retained");
  expect(output["signals_evaluated"].asUInt() == 2 &&
             output["signals_generated"].asUInt() == 1,
         "signal counters update deterministically");
  expect(output["paper_intents"].asUInt() == 1 && output["fills"].asUInt() == 1,
         "paper intent and fill counters update");
  expect(output["fetches"]["BTC-USD"]["attempts"].asUInt() == 2 &&
             output["fetches"]["BTC-USD"]["successes"].asUInt() == 1 &&
             output["fetches"]["BTC-USD"]["failures"].asUInt() == 1,
         "fetch attempts, successes, and failures are separated");
  expect(output["fetches"]["BTC-USD"]["data_age_seconds"].asInt64() == 15,
         "fetch data age is calculated from supplied now");
  expect(output["gate_outcomes"]["passed"].asUInt() == 1 &&
             output["blockers"]["stale_data"].asUInt() == 1,
         "gate and blocker attribution is retained");

  ReconciliationDiagnostics disabled;
  disabled.recordFetchAttempt("SECRET_SHOULD_NOT_APPEAR");
  const Json::Value inert = disabled.toJson(125);
  expect(!inert["enabled"].asBool() && !inert.isMember("fetches"),
         "disabled diagnostics are inert");

  if (failures == 0) {
    std::cout << "All reconciliation diagnostics tests passed\n";
    return 0;
  }
  return 1;
}
