#include "trading/ReconciliationDiagnostics.hpp"

#include <algorithm>

namespace trade::trading {

void ReconciliationDiagnostics::setEnabled(const bool enabled) {
  std::lock_guard<std::mutex> lock(mutex_);
  enabled_ = enabled;
}

DataAge ReconciliationDiagnostics::dataAge(const long long observed,
                                           const long long now) {
  if (observed <= 0 || now < observed) {
    return {};
  }
  return DataAge{true, now - observed};
}

void ReconciliationDiagnostics::reset(const std::vector<std::string> &selected_symbols) {
  if (!enabled_) {
    return;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  selected_symbols_ = selected_symbols;
  fetches_.clear();
  gate_outcomes_.clear();
  blockers_.clear();
  signals_evaluated_ = 0;
  signals_generated_ = 0;
  paper_intents_ = 0;
  fills_ = 0;
}

void ReconciliationDiagnostics::recordFetchAttempt(const std::string &symbol) {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++fetches_[symbol].attempts;
}

void ReconciliationDiagnostics::recordFetchResult(const std::string &symbol,
                                                  const bool success,
                                                  const long long observed) {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  auto &stats = fetches_[symbol];
  if (success) {
    ++stats.successes;
    stats.last_success_epoch_seconds = observed;
  } else {
    ++stats.failures;
  }
}

void ReconciliationDiagnostics::recordSignal(const bool generated) {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++signals_evaluated_;
  if (generated) ++signals_generated_;
}

void ReconciliationDiagnostics::recordGateOutcome(const std::string &outcome) {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++gate_outcomes_[outcome.empty() ? "unknown" : outcome];
}

void ReconciliationDiagnostics::recordBlocker(const std::string &reason) {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++blockers_[reason.empty() ? "unknown" : reason];
}

void ReconciliationDiagnostics::recordPaperIntent() {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++paper_intents_;
}

void ReconciliationDiagnostics::recordFill() {
  if (!enabled_) return;
  std::lock_guard<std::mutex> lock(mutex_);
  ++fills_;
}

Json::Value ReconciliationDiagnostics::toJson(const long long now) const {
  Json::Value out(Json::objectValue);
  if (!enabled_) {
    out["enabled"] = false;
    return out;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  out["enabled"] = true;
  out["selected_symbols"] = Json::arrayValue;
  for (const auto &symbol : selected_symbols_) out["selected_symbols"].append(symbol);
  out["selected_symbol_count"] = static_cast<Json::UInt64>(selected_symbols_.size());
  out["signals_evaluated"] = static_cast<Json::UInt64>(signals_evaluated_);
  out["signals_generated"] = static_cast<Json::UInt64>(signals_generated_);
  out["paper_intents"] = static_cast<Json::UInt64>(paper_intents_);
  out["fills"] = static_cast<Json::UInt64>(fills_);

  Json::Value fetches(Json::objectValue);
  for (const auto &[symbol, stats] : fetches_) {
    Json::Value item(Json::objectValue);
    item["attempts"] = static_cast<Json::UInt64>(stats.attempts);
    item["successes"] = static_cast<Json::UInt64>(stats.successes);
    item["failures"] = static_cast<Json::UInt64>(stats.failures);
    const DataAge age = dataAge(stats.last_success_epoch_seconds, now);
    item["data_age_seconds"] = age.available ? Json::Value(static_cast<Json::Int64>(age.seconds))
                                              : Json::Value(Json::nullValue);
    fetches[symbol] = item;
  }
  out["fetches"] = fetches;

  const auto mapToJson = [](const std::map<std::string, std::size_t> &values) {
    Json::Value result(Json::objectValue);
    for (const auto &[key, value] : values) result[key] = static_cast<Json::UInt64>(value);
    return result;
  };
  out["gate_outcomes"] = mapToJson(gate_outcomes_);
  out["blockers"] = mapToJson(blockers_);
  return out;
}

} // namespace trade::trading
