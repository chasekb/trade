#pragma once

#include <json/json.h>

#include <cstddef>
#include <map>
#include <mutex>
#include <string>
#include <vector>

namespace trade::trading {

struct DataAge {
  bool available = false;
  long long seconds = 0;
};

// Deterministic, opt-in counters for a reconciliation window. This type has no
// exchange or database dependencies; callers provide timestamps and outcomes.
class ReconciliationDiagnostics {
public:
  explicit ReconciliationDiagnostics(bool enabled = false) : enabled_(enabled) {}

  void setEnabled(bool enabled);

  static DataAge dataAge(long long observed_epoch_seconds,
                         long long now_epoch_seconds);

  void reset(const std::vector<std::string> &selected_symbols = {});
  void recordFetchAttempt(const std::string &symbol);
  void recordFetchResult(const std::string &symbol, bool success,
                         long long observed_epoch_seconds);
  void recordSignal(bool generated);
  void recordGateOutcome(const std::string &outcome);
  void recordBlocker(const std::string &reason);
  void recordPaperIntent();
  void recordFill();

  Json::Value toJson(long long now_epoch_seconds) const;

private:
  struct FetchStats {
    std::size_t attempts = 0;
    std::size_t successes = 0;
    std::size_t failures = 0;
    long long last_success_epoch_seconds = 0;
  };

  bool enabled_ = false;
  mutable std::mutex mutex_;
  std::vector<std::string> selected_symbols_;
  std::map<std::string, FetchStats> fetches_;
  std::map<std::string, std::size_t> gate_outcomes_;
  std::map<std::string, std::size_t> blockers_;
  std::size_t signals_evaluated_ = 0;
  std::size_t signals_generated_ = 0;
  std::size_t paper_intents_ = 0;
  std::size_t fills_ = 0;
};

} // namespace trade::trading
