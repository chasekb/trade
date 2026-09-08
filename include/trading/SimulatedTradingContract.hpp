#pragma once

#include "trading/PortfolioAccounting.hpp"

#include <algorithm>
#include <cstddef>
#include <json/json.h>
#include <set>
#include <string>
#include <vector>

namespace trade {
namespace trading {

// API-level pagination values are normalized once at the backend boundary so
// every signal source reports the same metadata and cannot overflow offset math.
struct SignalPagination {
  int page = 1;
  int per_page = 1;
  std::size_t total = 0;
  std::size_t total_pages = 0;
  bool has_next = false;
  bool has_prev = false;
};

inline SignalPagination normalizeSignalPagination(int requested_page,
                                                   int requested_per_page,
                                                   std::size_t total) {
  SignalPagination pagination;
  pagination.page = std::max(1, requested_page);
  pagination.per_page = std::max(1, requested_per_page);
  pagination.total = total;
  pagination.total_pages = total == 0
                               ? 0
                               : total / static_cast<std::size_t>(pagination.per_page) +
                                     (total % static_cast<std::size_t>(pagination.per_page) == 0 ? 0 : 1);
  pagination.has_next = static_cast<std::size_t>(pagination.page) < pagination.total_pages;
  pagination.has_prev = pagination.page > 1;
  return pagination;
}

inline std::vector<std::string> normalizeSimulatedSymbols(
    const std::vector<std::string> &requested) {
  std::vector<std::string> normalized;
  normalized.reserve(requested.size());
  std::set<std::string> seen;
  for (const auto &symbol : requested) {
    if (!symbol.empty() && seen.insert(symbol).second) {
      normalized.push_back(symbol);
    }
  }
  return normalized;
}

struct SimulatedSessionRequest {
  bool is_active = false;
  std::string session_id;
  std::string requested_session_id;
  bool requested_session_matches = true;
};

inline SimulatedSessionRequest resolveSimulatedSessionRequest(
    bool is_active, const std::string &session_id,
    const std::string &requested_session_id) {
  SimulatedSessionRequest result;
  result.is_active = is_active;
  result.session_id = session_id;
  result.requested_session_id = requested_session_id;
  result.requested_session_matches = requested_session_id.empty() ||
                                     (!session_id.empty() &&
                                      requested_session_id == session_id);
  return result;
}

// A fixed backend-shaped status response used by contract tests. The fixture
// deliberately includes current_capital as a legacy equity alias so a test
// cannot accidentally treat that field as cash. `total_positions_value` is
// the wire name for the signed positions value; gross exposure is separate.
inline Json::Value makeSimulatedPortfolioFixtureStatus(
    const std::string &event, double cash_balance,
    double total_positions_value, double total_positions_exposure,
    const Json::Value &positions) {
  Json::Value response(Json::objectValue);
  response["event"] = event;
  response["cash_balance"] = cash_balance;
  response["total_positions_value"] = total_positions_value;
  response["total_positions_exposure"] = total_positions_exposure;
  response["total_value"] = cash_balance + total_positions_value;
  response["current_capital"] = response["total_value"];
  response["positions"] = positions;
  return response;
}

inline Json::Value simulatedPortfolioFixturePosition(
    const std::string &symbol, const std::string &side, double quantity,
    double entry_price, double current_price) {
  Json::Value position(Json::objectValue);
  position["symbol"] = symbol;
  position["side"] = side;
  position["quantity"] = quantity;
  position["entry_price"] = entry_price;
  position["current_price"] = current_price;
  return position;
}

// Ordered, deterministic status snapshots for the simulated portfolio
// contract. Call advance() once per event: buy-open, sell-open, then
// sell-close-long. The final state intentionally leaves SHORT-USD open.
class DeterministicSimulatedPortfolioFixture {
public:
  DeterministicSimulatedPortfolioFixture() {
    Json::Value empty_positions(Json::arrayValue);
    states_.push_back(makeSimulatedPortfolioFixtureStatus(
        "initial", 10000.0, 0.0, 0.0, empty_positions));

    Json::Value long_only(Json::arrayValue);
    long_only.append(simulatedPortfolioFixturePosition(
        "LONG-USD", "buy", 5.0, 100.0, 100.0));
    const double buy_notional = 5.0 * 100.0;
    const double buy_fee = buy_notional * 0.0005;
    const double cash_after_buy =
        10000.0 + openCashDelta("buy", buy_notional, buy_fee);
    states_.push_back(makeSimulatedPortfolioFixtureStatus(
        "buy-open", cash_after_buy, 500.0, 500.0, long_only));

    Json::Value long_and_short(Json::arrayValue);
    long_and_short.append(simulatedPortfolioFixturePosition(
        "LONG-USD", "buy", 5.0, 100.0, 100.0));
    long_and_short.append(simulatedPortfolioFixturePosition(
        "SHORT-USD", "sell", 2.0, 125.0, 125.0));
    const double short_notional = 2.0 * 125.0;
    const double short_fee = short_notional * 0.0005;
    const double cash_after_sell_open =
        cash_after_buy + openCashDelta("sell", short_notional, short_fee);
    states_.push_back(makeSimulatedPortfolioFixtureStatus(
        "sell-open", cash_after_sell_open, 250.0, 750.0, long_and_short));

    Json::Value short_only(Json::arrayValue);
    short_only.append(simulatedPortfolioFixturePosition(
        "SHORT-USD", "sell", 2.0, 125.0, 125.0));
    const double close_notional = 5.0 * 110.0;
    const double close_fee = close_notional * 0.0005;
    const double cash_after_close =
        cash_after_sell_open + closeCashDelta("buy", close_notional, close_fee);
    states_.push_back(makeSimulatedPortfolioFixtureStatus(
        "sell-close-long", cash_after_close, -250.0, 250.0, short_only));
  }

  const Json::Value &status() const { return states_[step_]; }

  bool advance() {
    if (step_ + 1 >= states_.size()) {
      return false;
    }
    ++step_;
    return true;
  }

  std::size_t step() const { return step_; }

private:
  std::vector<Json::Value> states_;
  std::size_t step_ = 0;
};

} // namespace trading
} // namespace trade
