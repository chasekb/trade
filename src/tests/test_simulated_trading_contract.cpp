#include "trading/SimulatedTradingContract.hpp"

#include <cmath>
#include <iostream>
#include <limits>
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
} // namespace

int main() {
  const auto symbols = normalizeSimulatedSymbols(
      {"BTC-USD", "", "BTC-USD", "ETH-USD", "ETH-USD"});
  expect(symbols == std::vector<std::string>({"BTC-USD", "ETH-USD"}),
         "symbol universes are stable and deduplicated");

  const auto empty_symbols = normalizeSimulatedSymbols({});
  expect(empty_symbols.empty(), "empty symbol input remains empty for defaulting");

  const auto first_page = normalizeSignalPagination(1, 10, 205);
  expect(first_page.page == 1 && first_page.per_page == 10,
         "pagination preserves normal page inputs");
  expect(first_page.total == 205 && first_page.total_pages == 21,
         "pagination reports the full signal universe");
  expect(first_page.has_next && !first_page.has_prev,
         "first page navigation flags are consistent");

  const auto last_page = normalizeSignalPagination(21, 10, 205);
  expect(last_page.has_prev && !last_page.has_next,
         "last page navigation flags are consistent");

  const auto invalid_page = normalizeSignalPagination(-4, 0, 0);
  expect(invalid_page.page == 1 && invalid_page.per_page == 1,
         "invalid pagination inputs fail closed to safe values");
  expect(invalid_page.total_pages == 0 && !invalid_page.has_next && !invalid_page.has_prev,
         "empty pagination has no navigation");

  const auto huge_page = normalizeSignalPagination(
      std::numeric_limits<int>::max(), std::numeric_limits<int>::max(),
      std::numeric_limits<std::size_t>::max());
  expect(huge_page.page == std::numeric_limits<int>::max(),
         "large page values do not wrap");
  expect(huge_page.total_pages > 0 && huge_page.has_next && huge_page.has_prev,
         "large universes produce bounded pagination metadata");

  const auto active_match = resolveSimulatedSessionRequest(true, "sess-2", "sess-2");
  expect(active_match.requested_session_matches && active_match.is_active,
         "active session request identifies the active session");

  const auto inactive_match = resolveSimulatedSessionRequest(false, "sess-2", "sess-2");
  expect(!inactive_match.is_active && inactive_match.requested_session_matches,
         "inactive session request remains explicitly identifiable");

  const auto mismatch = resolveSimulatedSessionRequest(true, "sess-2", "sess-1");
  expect(!mismatch.requested_session_matches && mismatch.requested_session_id == "sess-1",
         "status exposes a requested-session mismatch");

  // The deterministic fixture advances through initial, buy-open, sell-open,
  // and sell-close-long states, leaving the short position open. The response
  // contract is total_value = cash_balance + total_positions_value; the
  // legacy current_capital field must not be used as cash.
  DeterministicSimulatedPortfolioFixture fixture;
  const auto has_portfolio_fields = [](const Json::Value &response) {
    return response.isMember("cash_balance") &&
           response.isMember("total_positions_value") &&
           response.isMember("total_value");
  };
  expect(fixture.status()["event"].asString() == "initial",
         "portfolio fixture starts at the initial state");
  expect(has_portfolio_fields(fixture.status()) &&
             fixture.status()["cash_balance"].asDouble() == 10000.0 &&
             fixture.status()["total_positions_value"].asDouble() == 0.0 &&
             fixture.status()["total_value"].asDouble() == 10000.0,
         "initial portfolio response exposes canonical values");

  expect(fixture.advance() && fixture.status()["event"].asString() == "buy-open",
         "portfolio fixture advances through the purchase state");
  const auto &after_buy = fixture.status();
  expect(std::fabs(after_buy["cash_balance"].asDouble() - 9499.75) < 1e-9 &&
             has_portfolio_fields(after_buy) &&
             std::fabs(after_buy["total_positions_value"].asDouble() - 500.0) < 1e-9 &&
             std::fabs(after_buy["total_value"].asDouble() - 9999.75) < 1e-9,
         "buy-open response reconciles cash, signed positions, and total value");
  expect(std::fabs(after_buy["total_value"].asDouble() -
                   (after_buy["cash_balance"].asDouble() +
                    after_buy["total_positions_value"].asDouble())) < 1e-9,
         "buy-open response uses the canonical total-value identity");

  expect(fixture.advance() && fixture.status()["event"].asString() == "sell-open",
         "portfolio fixture advances through the sale/open-short state");
  const auto &after_sell_open = fixture.status();
  expect(has_portfolio_fields(after_sell_open) &&
             std::fabs(after_sell_open["cash_balance"].asDouble() - 9749.625) < 1e-9 &&
             std::fabs(after_sell_open["total_positions_value"].asDouble() - 250.0) < 1e-9 &&
             std::fabs(after_sell_open["total_positions_exposure"].asDouble() - 750.0) < 1e-9 &&
             std::fabs(after_sell_open["total_value"].asDouble() - 9999.625) < 1e-9,
         "sell-open response keeps signed value separate from gross exposure");
  expect(std::fabs(after_sell_open["total_value"].asDouble() -
                   (after_sell_open["cash_balance"].asDouble() +
                    after_sell_open["total_positions_value"].asDouble())) < 1e-9,
         "sell-open response uses the canonical total-value identity");

  expect(fixture.advance() && fixture.status()["event"].asString() == "sell-close-long",
         "portfolio fixture advances through the sale/close-long state");
  const auto &final_state = fixture.status();
  expect(std::fabs(final_state["cash_balance"].asDouble() - 10299.35) < 1e-9 &&
             has_portfolio_fields(final_state) &&
             std::fabs(final_state["total_positions_value"].asDouble() - (-250.0)) < 1e-9 &&
             std::fabs(final_state["total_positions_exposure"].asDouble() - 250.0) < 1e-9 &&
             std::fabs(final_state["total_value"].asDouble() - 10049.35) < 1e-9,
         "final response leaves a signed short position open");
  expect(final_state["positions"].isArray() && final_state["positions"].size() == 1 &&
             final_state["positions"][0]["side"].asString() == "sell",
         "final fixture state contains exactly the remaining short position");
  expect(final_state["cash_balance"].asDouble() != final_state["current_capital"].asDouble(),
         "cash balance is distinct from the stale current-capital alias");
  expect(std::fabs(final_state["total_value"].asDouble() -
                   (final_state["cash_balance"].asDouble() +
                    final_state["total_positions_value"].asDouble())) < 1e-9,
         "every final response uses the canonical total-value identity");
  expect(!fixture.advance(), "portfolio fixture remains stable after the final state");

  return failures == 0 ? 0 : 1;
}
