#pragma once

#include <algorithm>
#include <cmath>
#include <regex>
#include <string>

namespace trade::trading {

inline constexpr const char *kLiquidationAction = "liquidate_holding";
inline constexpr const char *kLiquidationTradeType = "live_liquidation";

inline double cappedLiquidationQuantity(double position_quantity,
                                        double available_quantity) {
  if (!std::isfinite(position_quantity) || !std::isfinite(available_quantity)) {
    return 0.0;
  }
  return std::max(0.0, std::min(position_quantity, available_quantity));
}

inline bool liquidationAttemptAllowed(bool already_attempted, bool pending) {
  return !already_attempted && !pending;
}

inline bool isTerminalLiquidationFill(const std::string &status) {
  return status == "FILLED" || status == "DONE" || status == "CANCELLED" ||
         status == "EXPIRED" || status == "REJECTED";
}

inline std::string redactSensitiveText(std::string text) {
  static const std::regex secret_pattern(
      R"((api[_-]?key|api[_-]?secret|private[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,;]+)",
      std::regex_constants::icase);
  return std::regex_replace(text, secret_pattern, "$1=[REDACTED]");
}

} // namespace trade::trading