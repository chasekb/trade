#include "trading/SimulatedTradingDiagnosis.hpp"

#include <algorithm>
#include <cctype>
#include <map>
#include <set>
#include <sstream>

namespace trade::trading {
namespace {

Json::Value nullableString(const std::string &value) {
  return value.empty() ? Json::Value(Json::nullValue) : Json::Value(value);
}

Json::Value reason(const std::string &code, const std::string &message,
                   bool retryable = true) {
  if (code.empty()) {
    return Json::Value(Json::nullValue);
  }
  Json::Value result(Json::objectValue);
  result["code"] = code;
  result["message"] = message;
  result["retryable"] = retryable;
  return result;
}

bool isTradeStatus(const std::string &status) {
  return status == "trade_open" || status == "trade_completed";
}

bool isProblemStatus(const std::string &status) {
  return status == "data_unavailable" || status == "quote_invalid" ||
         status == "quote_stale" || status == "transformer_not_ready" ||
         status == "feature_shape_mismatch" || status == "signal_unavailable" ||
         status == "gates_blocked" || status == "intent_not_executable" ||
         status == "execution_failed" || status == "internal_error";
}

std::string messageForReason(const std::string &code, std::size_t count) {
  if (code == "signal_hold") return "valid HOLD (" + std::to_string(count) + ")";
  if (code == "gate_blocked" || code == "ml_confidence_below_threshold" ||
      code == "profitability_below_threshold") {
    return "policy gate blocked (" + std::to_string(count) + ")";
  }
  if (code == "incomplete_reconciliation") return "incomplete reconciliation (" + std::to_string(count) + ")";
  if (code == "session_error") return "session error (" + std::to_string(count) + ")";
  return code + " (" + std::to_string(count) + ")";
}

void addReasonCounts(const Json::Value &record, std::map<std::string, std::size_t> &reasons) {
  const Json::Value status = record.get("status", Json::Value(Json::objectValue));
  const std::string primary = status.get("primary", Json::Value("pending")).asString();
  if (isTradeStatus(primary)) return;

  const Json::Value status_reason = status.get("reason", Json::Value(Json::nullValue));
  if (status_reason.isObject()) {
    const std::string code = status_reason.get("code", Json::Value("")).asString();
    if (!code.empty()) ++reasons[code];
  }

  // A gate-blocked signal can have several independent causes. Preserve each
  // policy reason instead of reducing the summary to the generic gate_blocked
  // status. The status reason remains useful as a fallback for older records.
  if (primary == "gates_blocked") {
    const Json::Value gates = record.get("gates", Json::Value(Json::objectValue));
    for (const char *gate : {"profitability", "ml"}) {
      const Json::Value gate_record = gates.get(gate, Json::Value(Json::objectValue));
      const Json::Value gate_reasons = gate_record.get("reasons", Json::Value(Json::arrayValue));
      for (const auto &gate_reason : gate_reasons) {
        if (gate_reason.isObject()) {
          const std::string code = gate_reason.get("code", Json::Value("")).asString();
          if (!code.empty()) ++reasons[code];
        }
      }
    }
  }
}

} // namespace

Json::Value makeEmptySymbolDiagnosis(const std::string &symbol,
                                     const std::size_t ordinal,
                                     const std::string &selected_at) {
  Json::Value result(Json::objectValue);
  result["symbol"] = symbol;
  result["selection"]["status"] = "selected";
  result["selection"]["ordinal"] = static_cast<Json::UInt64>(ordinal);
  result["selection"]["selected_at"] = selected_at;

  result["status"]["primary"] = "pending";
  result["status"]["terminal"] = false;
  result["status"]["reason"] = Json::nullValue;
  result["status"]["evaluated_at"] = Json::nullValue;

  result["market_data"]["state"] = "not_requested";
  result["market_data"]["provider"] = "coinbase";
  result["market_data"]["request_id"] = Json::nullValue;
  result["market_data"]["attempts"] = 0;
  result["market_data"]["last_success_at"] = Json::nullValue;
  result["market_data"]["error"] = Json::nullValue;

  result["quote"]["state"] = "unknown";
  result["quote"]["bid"] = Json::nullValue;
  result["quote"]["ask"] = Json::nullValue;
  result["quote"]["mid"] = Json::nullValue;
  result["quote"]["observed_at"] = Json::nullValue;
  result["quote"]["age_ms"] = Json::nullValue;
  result["quote"]["max_age_ms"] = 5000;
  result["quote"]["validation_errors"] = Json::arrayValue;

  result["transformer"]["state"] = "not_evaluated";
  result["transformer"]["lookback"]["expected"] = 60;
  result["transformer"]["lookback"]["actual"] = Json::nullValue;
  result["transformer"]["lookback"]["compatible"] = Json::nullValue;
  result["transformer"]["feature_width"]["expected"] = 353;
  result["transformer"]["feature_width"]["actual"] = Json::nullValue;
  result["transformer"]["feature_width"]["compatible"] = Json::nullValue;
  result["transformer"]["history_rows"] = 0;
  result["transformer"]["model_id"] = Json::nullValue;
  result["transformer"]["error"] = Json::nullValue;

  result["signal"]["state"] = "not_evaluated";
  result["signal"]["side"] = Json::nullValue;
  result["signal"]["generated_at"] = Json::nullValue;
  result["signal"]["confidence"] = Json::nullValue;
  result["signal"]["predicted_return"] = Json::nullValue;
  result["signal"]["reason"] = Json::nullValue;

  for (const char *gate : {"profitability", "ml"}) {
    result["gates"][gate]["state"] = "not_evaluated";
    result["gates"][gate]["reasons"] = Json::arrayValue;
    result["gates"][gate]["evaluated_at"] = Json::nullValue;
  }
  result["gates"]["all_passed"] = Json::nullValue;

  result["intent"]["state"] = "not_evaluated";
  result["intent"]["side"] = Json::nullValue;
  result["intent"]["quantity"] = Json::nullValue;
  result["intent"]["reason"] = Json::nullValue;
  result["intent"]["created_at"] = Json::nullValue;

  result["execution"]["state"] = "not_attempted";
  result["execution"]["side"] = Json::nullValue;
  result["execution"]["attempts"] = 0;
  result["execution"]["simulation_order_id"] = Json::nullValue;
  result["execution"]["filled_quantity"] = Json::nullValue;
  result["execution"]["average_price"] = Json::nullValue;
  result["execution"]["occurred_at"] = Json::nullValue;
  result["execution"]["error"] = Json::nullValue;

  result["trade"]["state"] = "not_applicable";
  result["trade"]["outcome"] = "not_applicable";
  result["trade"]["trade_id"] = Json::nullValue;
  result["trade"]["side"] = Json::nullValue;
  result["trade"]["opened_at"] = Json::nullValue;
  result["trade"]["closed_at"] = Json::nullValue;
  result["trade"]["realized_pnl"] = Json::nullValue;
  result["trade"]["fee"] = Json::nullValue;
  result["trade"]["reason"] = Json::nullValue;

  result["sequence"] = 0;
  result["event_id"] = Json::nullValue;
  result["occurred_at"] = selected_at;
  result["updated_at"] = selected_at;
  return result;
}

std::string classifyMarketDataErrorCode(const std::string &error) {
  std::string lower = error;
  std::transform(lower.begin(), lower.end(), lower.begin(),
                 [](const unsigned char c) { return static_cast<char>(std::tolower(c)); });
  // Some older HTTP-client paths report a combined "network or TLS" message
  // even though they did not expose which layer failed. Preserve that lack of
  // evidence rather than claiming a TLS handshake failure.
  const bool ambiguous_transport =
      (lower.find("network") != std::string::npos && lower.find("tls") != std::string::npos) ||
      lower.find("tls/network") != std::string::npos ||
      lower.find("network/tls") != std::string::npos;
  if (ambiguous_transport) return "unknown_network_error";
  if (lower.find("tls") != std::string::npos || lower.find("certificate") != std::string::npos ||
      lower.find("ssl") != std::string::npos) return "tls_handshake";
  if (lower.find("dns") != std::string::npos || lower.find("resolve") != std::string::npos ||
      lower.find("host") != std::string::npos) return "dns_failure";
  if (lower.find("timeout") != std::string::npos || lower.find("timed out") != std::string::npos) return "timeout";
  if (lower.find("cancel") != std::string::npos || lower.find("shutdown") != std::string::npos) return "cancelled";
  if (lower.find("http ") != std::string::npos || lower.find("status ") != std::string::npos) return "exchange_response";
  if (lower.find("rate") != std::string::npos && lower.find("limit") != std::string::npos) return "rate_limited";
  if (lower.find("network") != std::string::npos || lower.find("connection") != std::string::npos ||
      lower.find("connect") != std::string::npos) return "network_unreachable";
  return "unknown_network_error";
}

std::string safeMarketDataErrorMessage(const std::string &code) {
  if (code == "tls_handshake") return "TLS handshake failed while contacting the market-data provider.";
  if (code == "dns_failure") return "DNS lookup failed for the market-data provider.";
  if (code == "timeout") return "Market-data provider request timed out.";
  if (code == "cancelled") return "Market-data request was cancelled.";
  if (code == "exchange_response") return "Market-data provider returned an error response.";
  if (code == "rate_limited") return "Market-data provider rate limited the request.";
  if (code == "network_unreachable") return "Market-data provider could not be reached.";
  return "Market-data provider request failed.";
}

Json::Value makeSafeMarketDataError(const std::string &code, const int attempts,
                                    const std::string &occurred_at,
                                    const int http_status) {
  Json::Value result(Json::objectValue);
  result["code"] = code;
  result["message"] = safeMarketDataErrorMessage(code);
  result["retryable"] = code != "exchange_response" && code != "cancelled";
  result["attempts"] = std::max(0, attempts);
  if (!occurred_at.empty()) result["occurred_at"] = occurred_at;
  if (code == "exchange_response" && http_status > 0) result["http_status"] = http_status;
  return result;
}

Json::Value makeDiagnosisSummary(const DiagnosisSummaryInput &input) {
  Json::Value result(Json::objectValue);
  result["schema_version"] = kSimulatedTradingDiagnosisSchema;
  result["session_id"] = input.session_id;
  result["mode"] = input.mode;
  result["as_of"] = input.as_of;
  result["selected_count"] = static_cast<Json::UInt64>(input.selected_symbols.size());
  std::map<std::string, std::size_t> counts;
  std::map<std::string, std::size_t> reasons;
  std::size_t terminal_count = 0;
  bool has_non_trade = false;
  std::set<std::string> selected_symbols(input.selected_symbols.begin(),
                                         input.selected_symbols.end());
  std::set<std::string> seen_symbols;
  // An empty completed session is still a valid snapshot, but it must carry
  // an explicit reason so consumers never interpret zero symbols as an
  // unexplained zero-trade result.
  bool complete_reconciliation =
      selected_symbols.size() == input.selected_symbols.size() &&
      input.symbols.size() == input.selected_symbols.size();
  for (const auto &symbol : input.symbols) {
    const std::string symbol_id = symbol.get("symbol", Json::Value("")).asString();
    if (selected_symbols.count(symbol_id) == 0 ||
        !seen_symbols.insert(symbol_id).second) {
      complete_reconciliation = false;
      continue;
    }
    const std::string status = symbol.get("status", Json::Value(Json::objectValue))
                                   .get("primary", Json::Value("pending")).asString();
    ++counts[status];
    if (symbol.get("status", Json::Value(Json::objectValue)).get("terminal", false).asBool()) ++terminal_count;
    if (!isTradeStatus(status)) has_non_trade = true;
    addReasonCounts(symbol, reasons);
  }
  if (seen_symbols.size() != selected_symbols.size()) {
    complete_reconciliation = false;
  }
  if (input.fatal_error) ++reasons["session_error"];
  if (!complete_reconciliation ||
      (input.selected_symbols.empty() && input.symbols.empty() && input.trade_count == 0) ||
      (!input.active && !input.cancelled && input.trade_count == 0 &&
       terminal_count < input.selected_symbols.size())) {
    ++reasons["incomplete_reconciliation"];
  }
  Json::Value by_status(Json::objectValue);
  for (const auto &[status, count] : counts) by_status[status] = static_cast<Json::UInt64>(count);
  result["by_primary_status"] = by_status;
  Json::Value no_trade_reasons(Json::arrayValue);
  for (const auto &[code, count] : reasons) {
    Json::Value item(Json::objectValue);
    item["code"] = code;
    item["count"] = static_cast<Json::UInt64>(count);
    no_trade_reasons.append(item);
  }
  result["no_trade_reasons"] = no_trade_reasons;

  // Prefer a specific order-preventing reason over the generic terminal
  // status. The map iteration order provides a stable lexical tie-break while
  // excluding valid HOLDs and reconciliation/session bookkeeping reasons.
  std::string dominant_blocker_code;
  std::size_t dominant_blocker_count = 0;
  for (const auto &[code, count] : reasons) {
    if (code == "signal_hold" || code == "gate_blocked" ||
        code == "incomplete_reconciliation" || code == "session_error") {
      continue;
    }
    if (count > dominant_blocker_count ||
        (count == dominant_blocker_count &&
         (dominant_blocker_code.empty() || code < dominant_blocker_code))) {
      dominant_blocker_code = code;
      dominant_blocker_count = count;
    }
  }
  if (dominant_blocker_code.empty()) {
    const auto generic_gate = reasons.find("gate_blocked");
    if (generic_gate != reasons.end()) {
      dominant_blocker_code = generic_gate->first;
      dominant_blocker_count = generic_gate->second;
    }
  }
  Json::Value dominant_blocker(Json::objectValue);
  dominant_blocker["code"] = dominant_blocker_code.empty()
                                  ? Json::Value(Json::nullValue)
                                  : Json::Value(dominant_blocker_code);
  dominant_blocker["count"] = static_cast<Json::UInt64>(dominant_blocker_count);
  result["dominant_blocker"] = dominant_blocker;

  result["terminal_count"] = static_cast<Json::UInt64>(terminal_count);
  result["trade_count"] = static_cast<Json::UInt64>(input.trade_count);

  if (input.cancelled) {
    result["status"] = "cancelled";
    result["outcome"] = "cancelled";
  } else if (input.fatal_error) {
    result["status"] = "failed";
    result["outcome"] = "not_yet_determined";
  } else if (input.active) {
    result["status"] = terminal_count == 0 ? "starting" : (std::any_of(input.symbols.begin(), input.symbols.end(), [](const Json::Value &symbol) {
      return isProblemStatus(symbol.get("status", Json::Value(Json::objectValue)).get("primary", "").asString());
    }) ? "degraded" : "running");
    result["outcome"] = "not_yet_determined";
  } else if (complete_reconciliation && terminal_count == input.selected_symbols.size()) {
    result["status"] = "completed";
    result["outcome"] = input.trade_count == 0 ? "no_trade" : (has_non_trade ? "mixed" : "trades_recorded");
  } else {
    result["status"] = "failed";
    result["outcome"] = "not_yet_determined";
    if (no_trade_reasons.empty()) {
      Json::Value item(Json::objectValue);
      item["code"] = "incomplete_reconciliation";
      item["count"] = 1;
      no_trade_reasons.append(item);
      result["no_trade_reasons"] = no_trade_reasons;
    }
  }

  std::ostringstream message;
  if (input.trade_count > 0) {
    message << input.trade_count << " trade" << (input.trade_count == 1 ? "" : "s") << " recorded";
  } else if (!no_trade_reasons.empty()) {
    message << "No trades recorded: ";
    bool first = true;
    for (const auto &[code, count] : reasons) {
      if (!first) message << ", ";
      first = false;
      message << messageForReason(code, count);
    }
    message << ".";
  } else {
    message << "No trade result is available yet; reconciliation is incomplete.";
  }
  result["message"] = message.str();
  return result;
}

} // namespace trade::trading
