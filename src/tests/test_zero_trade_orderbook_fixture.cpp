#include "trading/SimulatedTradingDiagnosis.hpp"

#include <fstream>
#include <iostream>
#include <string>

using namespace trade::trading;

#ifndef ZERO_TRADE_FIXTURE_PATH
#define ZERO_TRADE_FIXTURE_PATH "src/tests/fixtures/zero_trade_orderbook_run.json"
#endif

namespace {
int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}

Json::Value loadFixture() {
  std::ifstream input(ZERO_TRADE_FIXTURE_PATH);
  expect(input.good(), "zero-trade fixture is checked in beside the replay test");
  Json::CharReaderBuilder builder;
  Json::Value fixture;
  std::string errors;
  expect(Json::parseFromStream(builder, input, &fixture, &errors),
         "zero-trade fixture is valid JSON");
  if (!errors.empty()) {
    std::cerr << errors;
  }
  return fixture;
}

const Json::Value &recordFor(const Json::Value &fixture, const std::string &symbol) {
  for (const auto &record : fixture["representative_symbols"]) {
    if (record["symbol"].asString() == symbol) return record;
  }
  static const Json::Value missing(Json::nullValue);
  return missing;
}

Json::Value replaySummary(const Json::Value &fixture) {
  DiagnosisSummaryInput input;
  input.session_id = fixture["session_id"].asString();
  input.mode = fixture["mode"].asString();
  input.as_of = fixture["as_of"].asString();
  for (const auto &symbol : fixture["selected_symbols"]) {
    input.selected_symbols.push_back(symbol.asString());
  }
  for (const auto &record : fixture["representative_symbols"]) {
    input.symbols.push_back(record);
  }
  input.trade_count = fixture["stage_counts"]["persisted_trades"].asUInt();
  return makeDiagnosisSummary(input);
}

} // namespace

int main() {
  const Json::Value fixture = loadFixture();
  expect(fixture["schema_version"].asString() == "zero_trade_orderbook_replay.v1",
         "fixture schema version is explicit");
  expect(fixture["strategy"].asString() == "ml_enhanced_orderbook",
         "fixture identifies the order-book strategy");
  expect(fixture["model"]["transformer_configured"].asBool() &&
             !fixture["model"]["classifier_configured"].asBool() &&
             !fixture["model"]["regressor_configured"].asBool() &&
             fixture["model"]["confidence_threshold"].asDouble() == 0.6,
         "fixture preserves the transformer-only model and confidence threshold");

  const Json::Value &counts = fixture["stage_counts"];
  expect(counts["selected_symbols"].asUInt() == 401 &&
             counts["diagnosis_evaluations"].asUInt() == 2635,
         "fixture records the selected universe and diagnosis evaluations");
  expect(counts["quote_success_evaluations"].asUInt() == 2635 &&
             counts["quote_failures"].asUInt() == 0,
         "quote success and failure outcomes remain separate");
  expect(counts["transformer_warmup_events"].asUInt() == 401 &&
             counts["transformer_ready_evaluations"].asUInt() == 2234,
         "transformer warm-up and ready evaluations are distinct");
  expect(counts["signal_holds"].asUInt() == 1119 &&
             counts["generated_candidates"].asUInt() == 1115 &&
             counts["signal_holds"].asUInt() + counts["generated_candidates"].asUInt() +
                     counts["transformer_warmup_events"].asUInt() ==
                 counts["diagnosis_evaluations"].asUInt(),
         "HOLDs, candidates, and warm-up reconcile to all evaluations");
  expect(counts["profitability_gate_passed"].asUInt() == 1115 &&
             counts["profitability_gate_blocked"].asUInt() == 0 &&
             counts["ml_gate_passed"].asUInt() == 0 &&
             counts["ml_gate_blocked"].asUInt() == 1115,
         "profitability and ML gate decisions are preserved separately");
  expect(counts["executable_intents"].asUInt() == 0 &&
             counts["simulated_fills"].asUInt() == 0 &&
             counts["persisted_trades"].asUInt() == 0 &&
             counts["persistence_failures"].asUInt() == 0,
         "zero-trade execution and persistence results are explicit");
  expect(fixture["dominant_blocker"]["code"].asString() ==
                 "ml_confidence_below_threshold" &&
             fixture["dominant_blocker"]["count"].asUInt() == 1115,
         "fixture identifies the ML confidence blocker without relaxing a gate");

  const Json::Value &hold = recordFor(fixture, "BTC-USD");
  expect(hold["status"]["primary"].asString() == "hold" &&
             hold["signal"]["state"].asString() == "hold" &&
             hold["gates"]["profitability"]["state"].asString() == "not_evaluated" &&
             hold["gates"]["ml"]["state"].asString() == "not_evaluated" &&
             hold["intent"]["state"].asString() == "not_created" &&
             hold["execution"]["state"].asString() == "not_attempted" &&
             hold["trade"]["state"].asString() == "not_applicable",
         "valid HOLDs do not become gate failures or intents");

  const Json::Value &blocked = recordFor(fixture, "ETH-USD");
  expect(blocked["status"]["primary"].asString() == "gates_blocked" &&
             blocked["signal"]["state"].asString() == "buy" &&
             blocked["gates"]["profitability"]["state"].asString() == "passed" &&
             blocked["gates"]["ml"]["state"].asString() == "blocked" &&
             blocked["gates"]["ml"]["reasons"][0]["code"].asString() ==
                 "ml_confidence_below_threshold" &&
             blocked["intent"]["state"].asString() == "blocked" &&
             blocked["execution"]["state"].asString() == "not_attempted" &&
             blocked["trade"]["state"].asString() == "not_applicable",
         "generated BUY candidates retain the ML gate blocker and stop before execution");

  const Json::Value &warming = recordFor(fixture, "SOL-USD");
  expect(warming["status"]["primary"].asString() == "transformer_not_ready" &&
             warming["transformer"]["state"].asString() == "warming_up" &&
             warming["transformer"]["error"]["code"].asString() ==
                 "transformer_warming_up" &&
             warming["signal"]["state"].asString() == "not_evaluated" &&
             warming["gates"]["ml"]["state"].asString() == "not_evaluated",
         "transformer warm-up remains distinct from HOLD and gate outcomes");

  const Json::Value &quote_failure = fixture["negative_controls"][0];
  expect(quote_failure["status"]["primary"].asString() == "data_unavailable" &&
             quote_failure["market_data"]["state"].asString() == "unavailable" &&
             quote_failure["quote"]["state"].asString() == "unknown" &&
             quote_failure["signal"]["state"].asString() == "not_evaluated" &&
             quote_failure["intent"]["state"].asString() == "not_created",
         "quote failures remain distinct and never become synthetic HOLDs");

  expect(fixture["events"].isArray() && fixture["events"].empty() &&
             fixture["persisted_trades"].isArray() && fixture["persisted_trades"].empty(),
         "fixture contains no trade lifecycle events or persisted trades");
  for (const auto &record : fixture["representative_symbols"]) {
    expect(record["status"]["primary"].asString() != "trade_open" &&
               record["status"]["primary"].asString() != "trade_completed",
           "representative outcomes contain no trade lifecycle status");
    for (const char *dimension : {"market_data", "quote", "transformer", "signal",
                                  "gates", "intent", "execution", "trade"}) {
      expect(record.isMember(dimension) && record[dimension].isObject(),
             std::string("production diagnosis dimension is present: ") + dimension);
    }
  }

  // The fixture is replayed through the same summary function called by
  // SimulatedTradingService::buildDiagnosisJson; fixed input must yield fixed
  // counts and blocker classification on every execution.
  const Json::Value first = replaySummary(fixture);
  const Json::Value second = replaySummary(fixture);
  expect(first == second, "repeated replay executions are byte-equivalent JSON values");
  expect(first["status"].asString() == "completed" &&
             first["outcome"].asString() == "no_trade" &&
             first["selected_count"].asUInt() == 4 &&
             first["terminal_count"].asUInt() == 4 &&
             first["trade_count"].asUInt() == 0,
         "production reconciliation reports a complete zero-trade snapshot");
  expect(first["by_primary_status"]["hold"].asUInt() == 2 &&
             first["by_primary_status"]["gates_blocked"].asUInt() == 1 &&
             first["by_primary_status"]["transformer_not_ready"].asUInt() == 1 &&
             !first["by_primary_status"].isMember("trade_open") &&
             !first["by_primary_status"].isMember("trade_completed"),
         "production reconciliation keeps terminal status categories distinct");
  expect(first["dominant_blocker"]["code"].asString() ==
                 "ml_confidence_below_threshold" &&
             first["dominant_blocker"]["count"].asUInt() == 1 &&
             first["dominant_blocker"] == second["dominant_blocker"],
         "production reconciliation classifies the same dominant blocker repeatedly");

  if (failures == 0) {
    std::cout << "All zero-trade order-book replay tests passed\n";
    return 0;
  }
  std::cerr << failures << " zero-trade order-book replay test(s) failed\n";
  return 1;
}
