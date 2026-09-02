#pragma once

#include <json/json.h>

#include <cstddef>
#include <string>
#include <vector>

namespace trade::trading {

inline constexpr const char *kSimulatedTradingDiagnosisSchema =
    "simulated_trading_diagnosis.v1";

struct DiagnosisSummaryInput {
  std::string session_id;
  std::string mode = "simulated";
  std::string as_of;
  std::vector<std::string> selected_symbols;
  std::vector<Json::Value> symbols;
  std::size_t trade_count = 0;
  bool active = false;
  bool cancelled = false;
  bool fatal_error = false;
  Json::Value stage_counts = Json::Value(Json::objectValue);
};

Json::Value makeEmptySymbolDiagnosis(const std::string &symbol,
                                     std::size_t ordinal,
                                     const std::string &selected_at);

std::string classifyMarketDataErrorCode(const std::string &error);
std::string safeMarketDataErrorMessage(const std::string &code);
Json::Value makeSafeMarketDataError(const std::string &code, int attempts,
                                    const std::string &occurred_at,
                                    int http_status = 0);

Json::Value makeDiagnosisSummary(const DiagnosisSummaryInput &input);

} // namespace trade::trading
