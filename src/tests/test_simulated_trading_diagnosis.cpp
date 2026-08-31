#include "trading/SimulatedTradingDiagnosis.hpp"

#include <iostream>
#include <string>
#include <vector>

using namespace trade::trading;

namespace {
int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}

Json::Value terminal(const std::string &primary, const std::string &code) {
  Json::Value symbol = makeEmptySymbolDiagnosis("TEST-USD", 0, "2026-08-28T00:00:00Z");
  symbol["status"]["primary"] = primary;
  symbol["status"]["terminal"] = true;
  symbol["status"]["reason"]["code"] = code;
  symbol["status"]["reason"]["message"] = code;
  return symbol;
}
} // namespace

int main() {
  const Json::Value pending =
      makeEmptySymbolDiagnosis("BTC-USD", 0, "2026-08-28T00:00:00Z");
  expect(pending["symbol"].asString() == "BTC-USD", "symbol is retained exactly");
  expect(pending["selection"]["ordinal"].asInt() == 0, "selection ordinal is present");
  expect(pending["status"]["primary"].asString() == "pending" &&
             !pending["status"]["terminal"].asBool(),
         "new symbols start pending");
  for (const auto *dimension : {"market_data", "quote", "transformer", "signal",
                                "gates", "intent", "execution", "trade"}) {
    expect(pending.isMember(dimension) && pending[dimension].isObject(),
           std::string("dimension exists: ") + dimension);
  }
  expect(pending["transformer"]["lookback"]["expected"].asInt() == 60 &&
             pending["transformer"]["feature_width"]["expected"].asInt() == 353,
         "transformer contract dimensions are explicit");
  expect(pending["quote"]["bid"].isNull() && pending["quote"]["ask"].isNull(),
         "unknown quote prices are null rather than zero sentinels");

  expect(classifyMarketDataErrorCode("request failed (network or TLS error)") ==
             "unknown_network_error",
         "generic transport errors do not claim TLS without evidence");
  expect(classifyMarketDataErrorCode("certificate verify failed") == "tls_handshake",
         "TLS errors have a stable code");
  expect(classifyMarketDataErrorCode("HTTP 404: NotFound") == "exchange_response",
         "HTTP failures have a stable code");
  const std::string safe = safeMarketDataErrorMessage("tls_handshake");
  expect(safe.find("certificate") == std::string::npos &&
             safe.find("token") == std::string::npos,
         "safe error messages do not expose transport details");

  Json::Value unavailable = terminal("data_unavailable", "tls_handshake");
  unavailable["market_data"]["state"] = "unavailable";
  unavailable["market_data"]["error"]["code"] = "tls_handshake";
  Json::Value hold = terminal("hold", "signal_hold");
  hold["signal"]["state"] = "hold";
  hold["intent"]["state"] = "not_created";

  DiagnosisSummaryInput input;
  input.session_id = "session-1";
  input.mode = "live_parity";
  input.as_of = "2026-08-28T00:00:08Z";
  input.selected_symbols = {"BTC-USD", "ETH-USD"};
  input.symbols = {unavailable, hold};
  const Json::Value summary = makeDiagnosisSummary(input);
  expect(summary["status"].asString() == "completed" &&
             summary["outcome"].asString() == "no_trade",
         "zero-trade complete sessions have an explicit outcome");
  expect(summary["selected_count"].asInt() == 2 && summary["terminal_count"].asInt() == 2 &&
             summary["trade_count"].asInt() == 0,
         "summary counts selected and terminal symbols");
  expect(summary["by_primary_status"]["data_unavailable"].asInt() == 1 &&
             summary["by_primary_status"]["hold"].asInt() == 1,
         "summary preserves mixed primary statuses");
  expect(summary["no_trade_reasons"].size() == 2 &&
             summary["message"].asString().find("No trades recorded") != std::string::npos,
         "zero-trade summary contains actionable reasons and message");

  Json::Value blocked = terminal("gates_blocked", "gate_blocked");
  blocked["gates"]["profitability"]["reasons"].append(
      Json::Value(Json::objectValue));
  blocked["gates"]["profitability"]["reasons"][0]["code"] =
      "profitability_below_threshold";
  blocked["gates"]["ml"]["reasons"].append(Json::Value(Json::objectValue));
  blocked["gates"]["ml"]["reasons"][0]["code"] =
      "ml_confidence_below_threshold";
  input.selected_symbols = {"TEST-USD"};
  input.symbols = {blocked};
  const Json::Value blocked_summary = makeDiagnosisSummary(input);
  expect(blocked_summary["no_trade_reasons"].size() == 3 &&
             blocked_summary["message"].asString().find("policy gate blocked") !=
                 std::string::npos,
         "gate summary retains generic and detailed policy reasons");

  input.selected_symbols.clear();
  input.symbols.clear();
  const Json::Value empty_summary = makeDiagnosisSummary(input);
  expect(empty_summary["status"].asString() == "completed" &&
             empty_summary["no_trade_reasons"].size() == 1 &&
             empty_summary["no_trade_reasons"][0]["code"].asString() ==
                 "incomplete_reconciliation",
         "empty zero-trade sessions cannot claim an unexplained result");

  input.selected_symbols = {"BTC-USD", "ETH-USD"};
  input.symbols = {terminal("hold", "signal_hold"),
                   terminal("hold", "signal_hold")};
  input.symbols[0]["symbol"] = "BTC-USD";
  input.symbols[1]["symbol"] = "BTC-USD";
  const Json::Value incomplete_summary = makeDiagnosisSummary(input);
  bool has_incomplete_reason = false;
  for (const auto &reason : incomplete_summary["no_trade_reasons"]) {
    has_incomplete_reason = has_incomplete_reason ||
                            reason["code"].asString() == "incomplete_reconciliation";
  }
  expect(incomplete_summary["status"].asString() == "failed" && has_incomplete_reason,
         "duplicate records cannot make an incomplete universe look complete");

  input.selected_symbols = {"BTC-USD", "BTC-USD"};
  input.symbols = {terminal("hold", "signal_hold"), terminal("hold", "signal_hold")};
  const Json::Value duplicate_selection_summary = makeDiagnosisSummary(input);
  expect(duplicate_selection_summary["status"].asString() == "failed",
         "duplicate selected symbols cannot make the universe look complete");

  input.selected_symbols = {"TEST-USD"};
  input.symbols = {terminal("trade_open", "")};
  const Json::Value open_summary = makeDiagnosisSummary(input);
  expect(open_summary["terminal_count"].asInt() == 1 &&
             open_summary["by_primary_status"]["trade_open"].asInt() == 1,
         "an open trade is terminal for the current symbol evaluation");

  input.trade_count = 1;
  input.selected_symbols = {"TEST-USD"};
  input.symbols = {terminal("trade_completed", "")};
  const Json::Value traded = makeDiagnosisSummary(input);
  expect(traded["outcome"].asString() == "trades_recorded" &&
             traded["trade_count"].asInt() == 1,
         "trade count changes aggregate outcome");

  return failures == 0 ? 0 : 1;
}
