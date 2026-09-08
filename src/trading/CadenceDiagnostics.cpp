#include "trading/CadenceDiagnostics.hpp"

#include <algorithm>
#include <cmath>
#include <ctime>
#include <iomanip>
#include <limits>
#include <sstream>

namespace trade::trading {

namespace {
constexpr std::size_t kMaxRecentErrors = 32;
constexpr double kTickTargetMs = 1000.0;
constexpr double kQuoteRequestSloMs = 750.0;
constexpr double kDisplayStaleAfterMs = 6000.0;

Json::Value stringOrNull(const std::string &value) {
  return value.empty() ? Json::Value(Json::nullValue) : Json::Value(value);
}
}

CadenceDiagnostics::CadenceDiagnostics(const bool enabled) : enabled_(enabled) {}

void CadenceDiagnostics::setEnabled(const bool enabled) {
  std::lock_guard<std::mutex> lock(mutex_);
  enabled_ = enabled;
}

bool CadenceDiagnostics::enabled() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return enabled_;
}

void CadenceDiagnostics::reset(const std::string &session_id,
                               const std::uint64_t universe_generation,
                               const std::vector<std::string> &selected_symbols) {
  std::lock_guard<std::mutex> lock(mutex_);
  session_id_ = session_id;
  universe_generation_ = universe_generation;
  selected_symbols_ = selected_symbols;
  next_tick_id_ = 0;
  current_tick_id_ = 0;
  current_tick_started_at_.clear();
  current_batch_id_.clear();
  tick_in_progress_ = false;
  counters_ = {};
  last_tick_ = {};
  last_tick_.outcome = "not_started";
  recent_errors_.clear();
  worker_tick_ms_ = Histogram{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                              std::vector<std::uint64_t>(12)};
  quote_request_ms_ = Histogram{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                                std::vector<std::uint64_t>(12)};
  quote_batch_ms_ = Histogram{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                              std::vector<std::uint64_t>(12)};
  signal_generation_ms_ = Histogram{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                                     std::vector<std::uint64_t>(12)};
  serialization_ms_ = Histogram{{1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000},
                                std::vector<std::uint64_t>(12)};
}

std::uint64_t CadenceDiagnostics::beginTick(const std::size_t selected_symbols,
                                             const std::string &started_at) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return 0;
  current_tick_id_ = ++next_tick_id_;
  current_tick_started_at_ = started_at.empty() ? utcNow() : started_at;
  current_batch_id_ = session_id_ + ":g" + std::to_string(universe_generation_) +
                      ":t" + std::to_string(current_tick_id_) + ":q1";
  current_tick_started_mono_ = std::chrono::steady_clock::now();
  tick_in_progress_ = true;
  last_tick_ = {};
  last_tick_.tick_id = current_tick_id_;
  last_tick_.started_at = current_tick_started_at_;
  last_tick_.selected_symbols = selected_symbols;
  last_tick_.outcome = "in_progress";
  ++counters_.ticks_started;
  return current_tick_id_;
}

double CadenceDiagnostics::safeDuration(const double elapsed_ms) {
  return std::isfinite(elapsed_ms) && elapsed_ms >= 0.0 ? elapsed_ms : 0.0;
}

void CadenceDiagnostics::recordQuoteRequest(const std::string &result_class,
                                            const int attempts,
                                            const double elapsed_ms) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return;
  const double elapsed = safeDuration(elapsed_ms);
  ++counters_.quote_requests;
  if (attempts > 1) ++counters_.quote_retries;
  if (result_class == "success") {
    ++counters_.quote_success;
  } else {
    ++counters_.quote_failures;
    if (result_class == "timeout") ++counters_.quote_timeouts;
    if (result_class == "rate_limited") ++counters_.quote_rate_limited;
    if (result_class == "dropped" || result_class == "cancelled") ++counters_.quote_dropped;
  }
  quote_request_ms_.record(elapsed);
}

void CadenceDiagnostics::recordQuoteBatch(const double elapsed_ms,
                                           const std::size_t success,
                                           const std::size_t missing) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return;
  quote_batch_ms_.record(safeDuration(elapsed_ms));
  if (tick_in_progress_) {
    last_tick_.quote_requested += success + missing;
    last_tick_.quote_success += success;
    last_tick_.quote_missing += missing;
  }
}

void CadenceDiagnostics::recordSignal(const std::string &state, const double elapsed_ms) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return;
  ++counters_.signals_evaluated;
  signal_generation_ms_.record(safeDuration(elapsed_ms));
  if (state == "generated") {
    ++counters_.signals_generated;
    if (tick_in_progress_) ++last_tick_.signals_generated;
  } else if (state == "delayed") {
    ++counters_.signals_delayed;
    if (tick_in_progress_) ++last_tick_.signals_generated;
  } else if (state == "dropped") {
    ++counters_.quote_dropped;
    if (tick_in_progress_) ++last_tick_.signals_dropped;
  } else {
    ++counters_.signals_not_generated;
    if (tick_in_progress_) ++last_tick_.signals_not_generated;
  }
}

void CadenceDiagnostics::recordSerialization(const double elapsed_ms) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return;
  serialization_ms_.record(safeDuration(elapsed_ms));
}

void CadenceDiagnostics::recordApiPollCompleted() {
  std::lock_guard<std::mutex> lock(mutex_);
  if (enabled_) ++counters_.api_poll_completed;
}

void CadenceDiagnostics::recordWebsocketDelivered() {
  std::lock_guard<std::mutex> lock(mutex_);
  if (enabled_) ++counters_.websocket_delivered;
}

void CadenceDiagnostics::recordError(const std::string &stage,
                                     const std::string &error_class,
                                     const int attempt,
                                     const std::string &at) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_) return;
  Json::Value error(Json::objectValue);
  error["stage"] = stage;
  error["class"] = error_class;
  error["tick_id"] = static_cast<Json::UInt64>(current_tick_id_);
  error["batch_id"] = stringOrNull(current_batch_id_);
  error["attempt"] = std::max(0, attempt);
  error["at"] = at.empty() ? utcNow() : at;
  recent_errors_.push_back(std::move(error));
  while (recent_errors_.size() > kMaxRecentErrors) recent_errors_.pop_front();
}

void CadenceDiagnostics::finishTick(const std::string &finished_at,
                                    const double elapsed_ms,
                                    const std::string &outcome) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!enabled_ || !tick_in_progress_) return;
  double elapsed = elapsed_ms;
  if (!(std::isfinite(elapsed) && elapsed >= 0.0)) {
    elapsed = std::chrono::duration<double, std::milli>(
                  std::chrono::steady_clock::now() - current_tick_started_mono_)
                  .count();
  }
  elapsed = safeDuration(elapsed);
  last_tick_.finished_at = finished_at.empty() ? utcNow() : finished_at;
  last_tick_.elapsed_ms = elapsed;
  last_tick_.outcome = outcome.empty() ? "completed" : outcome;
  worker_tick_ms_.record(elapsed);
  if (elapsed > kTickTargetMs) ++counters_.ticks_overdue;
  ++counters_.ticks_completed;
  tick_in_progress_ = false;
}

std::uint64_t CadenceDiagnostics::currentTickId() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return current_tick_id_;
}

std::string CadenceDiagnostics::currentBatchId() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return current_batch_id_;
}

Json::Value CadenceDiagnostics::correlationFor(const std::string &symbol,
                                               const std::string &state) const {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value out(Json::objectValue);
  if (!enabled_ || current_tick_id_ == 0) return out;
  out["schema_version"] = kSchemaVersion;
  out["session_id"] = session_id_;
  out["universe_generation"] = static_cast<Json::UInt64>(universe_generation_);
  out["trace_id"] = session_id_ + ":g" + std::to_string(universe_generation_) +
                     ":t" + std::to_string(current_tick_id_) + ":s" + symbol;
  out["tick_id"] = static_cast<Json::UInt64>(current_tick_id_);
  out["batch_id"] = current_batch_id_;
  out["event_id"] = out["trace_id"].asString() + ":e1";
  out["symbol"] = symbol;
  out["producer"]["tick_started_at"] = current_tick_started_at_;
  out["state"] = state;
  return out;
}

void CadenceDiagnostics::writeCounter(Json::Value &out, const char *name,
                                      const std::uint64_t value) {
  out[name] = static_cast<Json::UInt64>(value);
}

Json::Value CadenceDiagnostics::toJson(const std::string &as_of) const {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value out(Json::objectValue);
  if (!enabled_) {
    out["enabled"] = false;
    return out;
  }
  out["schema_version"] = kSchemaVersion;
  out["session_id"] = session_id_;
  out["universe_generation"] = static_cast<Json::UInt64>(universe_generation_);
  out["as_of"] = as_of.empty() ? utcNow() : as_of;
  out["thresholds_ms"]["tick_target"] = kTickTargetMs;
  out["thresholds_ms"]["quote_request_slo"] = kQuoteRequestSloMs;
  out["thresholds_ms"]["display_stale_after"] = kDisplayStaleAfterMs;

  Json::Value tick(Json::objectValue);
  tick["tick_id"] = static_cast<Json::UInt64>(last_tick_.tick_id);
  tick["started_at"] = stringOrNull(last_tick_.started_at);
  tick["finished_at"] = stringOrNull(last_tick_.finished_at);
  tick["elapsed_ms"] = last_tick_.elapsed_ms;
  tick["scheduled_deadline_at"] = Json::nullValue;
  tick["outcome"] = last_tick_.outcome;
  tick["selected_symbols"] = static_cast<Json::UInt64>(last_tick_.selected_symbols);
  tick["quote_requested"] = static_cast<Json::UInt64>(last_tick_.quote_requested);
  tick["quote_success"] = static_cast<Json::UInt64>(last_tick_.quote_success);
  tick["quote_missing"] = static_cast<Json::UInt64>(last_tick_.quote_missing);
  tick["signals_generated"] = static_cast<Json::UInt64>(last_tick_.signals_generated);
  tick["signals_not_generated"] = static_cast<Json::UInt64>(last_tick_.signals_not_generated);
  tick["signals_dropped"] = static_cast<Json::UInt64>(last_tick_.signals_dropped);
  out["last_tick"] = tick;

  Json::Value counters(Json::objectValue);
  writeCounter(counters, "ticks_started", counters_.ticks_started);
  writeCounter(counters, "ticks_completed", counters_.ticks_completed);
  writeCounter(counters, "ticks_overdue", counters_.ticks_overdue);
  writeCounter(counters, "quote_requests", counters_.quote_requests);
  writeCounter(counters, "quote_success", counters_.quote_success);
  writeCounter(counters, "quote_failures", counters_.quote_failures);
  writeCounter(counters, "quote_timeouts", counters_.quote_timeouts);
  writeCounter(counters, "quote_rate_limited", counters_.quote_rate_limited);
  writeCounter(counters, "quote_retries", counters_.quote_retries);
  writeCounter(counters, "quote_dropped", counters_.quote_dropped);
  writeCounter(counters, "signals_evaluated", counters_.signals_evaluated);
  writeCounter(counters, "signals_generated", counters_.signals_generated);
  writeCounter(counters, "signals_not_generated", counters_.signals_not_generated);
  writeCounter(counters, "signals_delayed", counters_.signals_delayed);
  writeCounter(counters, "serialization_errors", counters_.serialization_errors);
  writeCounter(counters, "api_poll_completed", counters_.api_poll_completed);
  writeCounter(counters, "websocket_delivered", counters_.websocket_delivered);
  out["counters"] = counters;

  Json::Value histograms(Json::objectValue);
  histograms["worker_tick_ms"] = worker_tick_ms_.toJson();
  histograms["quote_request_ms"] = quote_request_ms_.toJson();
  histograms["quote_batch_ms"] = quote_batch_ms_.toJson();
  histograms["signal_generation_ms"] = signal_generation_ms_.toJson();
  histograms["serialization_ms"] = serialization_ms_.toJson();
  out["histograms"] = histograms;

  Json::Value coverage(Json::objectValue);
  coverage["selected_symbols"] = static_cast<Json::UInt64>(last_tick_.selected_symbols);
  coverage["quote_requested"] = static_cast<Json::UInt64>(last_tick_.quote_requested);
  coverage["quote_received"] = static_cast<Json::UInt64>(last_tick_.quote_success);
  coverage["signal_generated"] = static_cast<Json::UInt64>(last_tick_.signals_generated);
  coverage["not_generated"] = static_cast<Json::UInt64>(last_tick_.signals_not_generated);
  coverage["delayed"] = static_cast<Json::UInt64>(counters_.signals_delayed);
  coverage["retried"] = static_cast<Json::UInt64>(counters_.quote_retries);
  coverage["dropped"] = static_cast<Json::UInt64>(last_tick_.signals_dropped);
  coverage["latest_symbol_rows"] = static_cast<Json::UInt64>(last_tick_.selected_symbols);
  out["coverage"] = coverage;

  out["recent_errors"] = Json::arrayValue;
  for (const auto &error : recent_errors_) out["recent_errors"].append(error);
  return out;
}

void CadenceDiagnostics::Histogram::record(const double elapsed_ms) {
  const double value = CadenceDiagnostics::safeDuration(elapsed_ms);
  const auto it = std::lower_bound(bounds_ms.begin(), bounds_ms.end(), value);
  const std::size_t bucket = static_cast<std::size_t>(it - bounds_ms.begin());
  if (counts.size() < bounds_ms.size() + 1) counts.resize(bounds_ms.size() + 1, 0);
  ++counts[bucket];
  ++count;
  sum_ms += value;
  max_ms = std::max(max_ms, value);
}

Json::Value CadenceDiagnostics::Histogram::toJson() const {
  Json::Value out(Json::objectValue);
  out["bounds_ms"] = Json::arrayValue;
  for (const auto bound : bounds_ms) out["bounds_ms"].append(bound);
  out["counts"] = Json::arrayValue;
  for (const auto count_value : counts) out["counts"].append(static_cast<Json::UInt64>(count_value));
  out["count"] = static_cast<Json::UInt64>(count);
  out["sum_ms"] = sum_ms;
  out["max_ms"] = max_ms;
  return out;
}

std::string CadenceDiagnostics::utcNow() {
  const auto now = std::chrono::system_clock::now();
  const auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(
      now.time_since_epoch()) % 1000;
  const auto time = std::chrono::system_clock::to_time_t(now);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &time);
#else
  gmtime_r(&time, &tm);
#endif
  std::ostringstream out;
  out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%S") << '.'
      << std::setfill('0') << std::setw(3) << millis.count() << 'Z';
  return out.str();
}

} // namespace trade::trading
