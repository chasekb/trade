#include "trading/CadenceDiagnostics.hpp"

#include <iostream>
#include <string>

using trade::trading::CadenceDiagnostics;

int main() {
  int failures = 0;
  const auto expect = [&](const bool condition, const char *label) {
    if (!condition) {
      std::cerr << "FAIL: " << label << '\n';
      ++failures;
    }
  };

  CadenceDiagnostics diagnostics(true);
  diagnostics.reset("session-1", 4, {"BTC-USD", "ETH-USD"});
  const auto tick_id = diagnostics.beginTick(2, "2026-09-01T17:22:18.100Z");
  expect(tick_id == 1, "tick IDs start at one per session");
  diagnostics.recordQuoteRequest("timeout", 2, 750.0);
  diagnostics.recordQuoteRequest("success", 1, 25.0);
  diagnostics.recordQuoteBatch(800.0, 1, 1);
  diagnostics.recordSignal("generated", 2.0);
  diagnostics.recordSignal("not_generated", 1.0);
  diagnostics.recordError("quote_request", "timeout", 2,
                          "2026-09-01T17:22:18.850Z");
  diagnostics.finishTick("2026-09-01T17:22:19.000Z", 900.0, "degraded");

  const auto output = diagnostics.toJson("2026-09-01T17:22:19.100Z");
  expect(output["schema_version"].asString() == "order_book_cadence.v1",
         "versioned cadence contract");
  expect(output["session_id"].asString() == "session-1" &&
             output["universe_generation"].asUInt64() == 4,
         "session identity and generation");
  expect(output["last_tick"]["tick_id"].asUInt64() == 1 &&
             output["last_tick"]["outcome"].asString() == "degraded" &&
             output["last_tick"]["quote_requested"].asUInt() == 2 &&
             output["last_tick"]["quote_missing"].asUInt() == 1,
         "last tick captures bounded partial coverage");
  expect(output["counters"]["quote_requests"].asUInt() == 2 &&
             output["counters"]["quote_retries"].asUInt() == 1 &&
             output["counters"]["quote_timeouts"].asUInt() == 1,
         "logical request and retry counters are distinct");
  expect(output["counters"]["signals_generated"].asUInt() == 1 &&
             output["counters"]["signals_not_generated"].asUInt() == 1,
         "hold is not counted as dropped");
  expect(output["histograms"]["worker_tick_ms"]["counts"].size() ==
             output["histograms"]["worker_tick_ms"]["bounds_ms"].size() + 1,
         "histograms have a fixed overflow bucket");
  expect(output["recent_errors"].size() == 1 &&
             !output["recent_errors"][0].isMember("symbol"),
         "errors are bounded and do not include symbols");

  const auto correlation = diagnostics.correlationFor("BTC-USD", "generated");
  expect(correlation["trace_id"].asString() == "session-1:g4:t1:sBTC-USD" &&
             correlation["event_id"].asString() == "session-1:g4:t1:sBTC-USD:e1" &&
             correlation["batch_id"].asString() == "session-1:g4:t1:q1",
         "correlation IDs share the tick boundary");

  diagnostics.beginTick(8, "2026-09-01T17:22:20.000Z");
  diagnostics.recordQuoteRequest("tls_error", 3, 1200.0);
  diagnostics.recordQuoteRequest("success", 1, 12.0);
  diagnostics.recordQuoteBatch(1215.0, 1, 1);
  diagnostics.recordSignal("delayed", 3.0);
  diagnostics.recordSerialization(85.0);
  diagnostics.recordApiPollCompleted();
  diagnostics.recordWebsocketDelivered();
  diagnostics.recordError("quote_request", "tls_error", 3,
                          "2026-09-01T17:22:21.200Z");
  diagnostics.finishTick("2026-09-01T17:22:21.300Z", 1300.0, "degraded");
  const auto multi_stage = diagnostics.toJson("2026-09-01T17:22:21.400Z");
  expect(multi_stage["last_tick"]["tick_id"].asUInt64() == 2 &&
             multi_stage["last_tick"]["quote_success"].asUInt() == 1 &&
             multi_stage["last_tick"]["quote_missing"].asUInt() == 1 &&
             multi_stage["last_tick"]["signals_generated"].asUInt() == 1,
         "partial batches retain valid symbols and delayed signals");
  expect(multi_stage["counters"]["quote_retries"].asUInt() == 2 &&
             multi_stage["counters"]["api_poll_completed"].asUInt() == 1 &&
             multi_stage["counters"]["websocket_delivered"].asUInt() == 1 &&
             multi_stage["counters"]["ticks_overdue"].asUInt() == 1,
         "retry, transport, and overdue cadence counters identify the stage");
  expect(multi_stage["histograms"]["quote_request_ms"]["max_ms"].asDouble() == 1200.0 &&
             multi_stage["histograms"]["serialization_ms"]["max_ms"].asDouble() == 85.0 &&
             multi_stage["histograms"]["worker_tick_ms"]["max_ms"].asDouble() == 1300.0,
         "quote, serialization, and worker latency remain separately measurable");
  expect(multi_stage["recent_errors"].size() == 2 &&
             multi_stage["recent_errors"][1]["class"].asString() == "tls_error" &&
             multi_stage["recent_errors"][1]["attempt"].asInt() == 3,
         "transport errors preserve retry attempt and ordering");

  diagnostics.reset("session-2", 1, {"SOL-USD"});
  const auto reset = diagnostics.toJson("2026-09-01T17:23:00.000Z");
  expect(reset["counters"]["quote_requests"].asUInt() == 0 &&
             reset["last_tick"]["tick_id"].asUInt() == 0 &&
             reset["recent_errors"].empty(),
         "session restart clears cumulative diagnostics");

  CadenceDiagnostics disabled;
  disabled.reset("secret-session", 1, {"SECRET-USD"});
  disabled.beginTick(1);
  expect(!disabled.toJson().isMember("counters"), "disabled diagnostics are inert");

  if (failures == 0) {
    std::cout << "All cadence diagnostics tests passed\n";
    return 0;
  }
  return 1;
}
