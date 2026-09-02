#pragma once

#include <json/json.h>

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace trade::trading {

// Bounded, report-only timing for the order-book producer path. Durations are
// measured with steady_clock; serialized timestamps are UTC correlation anchors.
class CadenceDiagnostics {
public:
  static constexpr const char *kSchemaVersion = "order_book_cadence.v1";

  explicit CadenceDiagnostics(bool enabled = false);

  void setEnabled(bool enabled);
  bool enabled() const;
  void reset(const std::string &session_id, std::uint64_t universe_generation,
             const std::vector<std::string> &selected_symbols);

  std::uint64_t beginTick(std::size_t selected_symbols,
                          const std::string &started_at = "");
  void recordQuoteRequest(const std::string &result_class, int attempts,
                          double elapsed_ms);
  void recordQuoteBatch(double elapsed_ms, std::size_t success,
                        std::size_t missing);
  void recordSignal(const std::string &state, double elapsed_ms);
  void recordSerialization(double elapsed_ms);
  void recordApiPollCompleted();
  void recordWebsocketDelivered();
  void recordError(const std::string &stage, const std::string &error_class,
                   int attempt, const std::string &at);
  void finishTick(const std::string &finished_at = "",
                  double elapsed_ms = -1.0,
                  const std::string &outcome = "completed");

  std::uint64_t currentTickId() const;
  std::string currentBatchId() const;
  Json::Value correlationFor(const std::string &symbol,
                             const std::string &state = "generated") const;
  Json::Value toJson(const std::string &as_of = "") const;

private:
  struct Histogram {
    std::vector<double> bounds_ms;
    std::vector<std::uint64_t> counts;
    std::uint64_t count = 0;
    double sum_ms = 0.0;
    double max_ms = 0.0;

    void record(double elapsed_ms);
    Json::Value toJson() const;
  };

  struct Counters {
    std::uint64_t ticks_started = 0;
    std::uint64_t ticks_completed = 0;
    std::uint64_t ticks_overdue = 0;
    std::uint64_t quote_requests = 0;
    std::uint64_t quote_success = 0;
    std::uint64_t quote_failures = 0;
    std::uint64_t quote_timeouts = 0;
    std::uint64_t quote_rate_limited = 0;
    std::uint64_t quote_retries = 0;
    std::uint64_t quote_dropped = 0;
    std::uint64_t signals_evaluated = 0;
    std::uint64_t signals_generated = 0;
    std::uint64_t signals_not_generated = 0;
    std::uint64_t signals_delayed = 0;
    std::uint64_t serialization_errors = 0;
    std::uint64_t api_poll_completed = 0;
    std::uint64_t websocket_delivered = 0;
  };

  struct LastTick {
    std::uint64_t tick_id = 0;
    std::string started_at;
    std::string finished_at;
    double elapsed_ms = 0.0;
    std::size_t selected_symbols = 0;
    std::size_t quote_requested = 0;
    std::size_t quote_success = 0;
    std::size_t quote_missing = 0;
    std::size_t signals_generated = 0;
    std::size_t signals_not_generated = 0;
    std::size_t signals_dropped = 0;
    std::string outcome = "not_started";
  };

  static double safeDuration(double elapsed_ms);
  static std::string utcNow();
  static void writeCounter(Json::Value &out, const char *name,
                           std::uint64_t value);

  mutable std::mutex mutex_;
  bool enabled_ = false;
  std::string session_id_;
  std::uint64_t universe_generation_ = 0;
  std::vector<std::string> selected_symbols_;
  std::uint64_t next_tick_id_ = 0;
  std::uint64_t current_tick_id_ = 0;
  std::string current_tick_started_at_;
  std::string current_batch_id_;
  std::chrono::steady_clock::time_point current_tick_started_mono_;
  bool tick_in_progress_ = false;
  Counters counters_;
  LastTick last_tick_;
  Histogram worker_tick_ms_{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                            std::vector<std::uint64_t>(12)};
  Histogram quote_request_ms_{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                              std::vector<std::uint64_t>(12)};
  Histogram quote_batch_ms_{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                            std::vector<std::uint64_t>(12)};
  Histogram signal_generation_ms_{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                                   std::vector<std::uint64_t>(12)};
  Histogram serialization_ms_{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                              std::vector<std::uint64_t>(12)};
  std::deque<Json::Value> recent_errors_;
};

} // namespace trade::trading
