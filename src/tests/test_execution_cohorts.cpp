#include "ml/ExecutionCohorts.hpp"

#include <iostream>
#include <string>

using trade::ml::ExecutionCohortMetrics;
using trade::ml::OrderBookFeatures;
using trade::ml::TradeOutcome;

namespace {

OrderBookFeatures makeFeatures(long long ts, const std::string &symbol, double spread, double imbalance,
                               double volatility, double volume_24h) {
  OrderBookFeatures f{};
  f.timestamp = ts;
  f.symbol = symbol;
  f.bid_ask_imbalance = imbalance;
  f.spread_percent = spread;
  f.mid_price = 100.0;
  f.bid_volume = 500.0;
  f.ask_volume = 400.0;
  f.order_book_depth = 10;
  f.large_bid_wall = false;
  f.large_ask_wall = false;
  f.wall_size = 0.0;
  f.volume_weighted_price = 100.0;
  f.price_momentum = 0.0;
  f.volatility = volatility;
  f.volume_24h = volume_24h;
  f.prev_win_probability = 0.5;
  f.prev_expected_return = 0.0;
  f.prev_confidence = 0.0;
  return f;
}

TradeOutcome makeOutcome(const std::string &trade_id, double pnl) {
  TradeOutcome t{};
  t.trade_id = trade_id;
  t.symbol = "BTC-USD";
  t.side = "buy";
  t.entry_price = 100.0;
  t.exit_price = 100.0 + pnl;
  t.quantity = 1.0;
  t.pnl = pnl;
  t.fees = 0.0;
  t.duration_seconds = 60;
  t.signal_type = "buy";
  t.signal_strength = 0.8;
  t.entry_timestamp = 1700000000;
  t.exit_timestamp = 1700000060;
  t.is_win = pnl > 0.0;
  return t;
}

} // namespace

int main() {
  const auto regime = trade::ml::classify_execution_regime(
      makeFeatures(1700000000, "BTC-USD", 0.0002, 0.3, 0.1, 5e9));
  if (regime.find("liquidity=high") == std::string::npos ||
      regime.find("spread=low") == std::string::npos ||
      regime.find("imbalance=bullish") == std::string::npos ||
      regime.find("volatility=low") == std::string::npos) {
    std::cerr << "Unexpected regime label: " << regime << std::endl;
    return 1;
  }

  std::vector<std::pair<OrderBookFeatures, TradeOutcome>> samples = {
      {makeFeatures(1700000000, "BTC-USD", 0.0002, 0.3, 0.1, 5e9), makeOutcome("t1", 8.0)},
      {makeFeatures(1700000060, "BTC-USD", 0.0002, 0.3, 0.1, 5e9), makeOutcome("t2", -2.0)},
  };
  const auto metrics = trade::ml::summarize_execution_cohorts(samples);
  if (metrics.size() != 1) {
    std::cerr << "Expected exactly one cohort, found " << metrics.size() << std::endl;
    return 1;
  }

  const ExecutionCohortMetrics &cohort = metrics.front();
  if (cohort.sample_count != 2 || cohort.winning_trades != 1 || cohort.losing_trades != 1) {
    std::cerr << "Unexpected cohort counts" << std::endl;
    return 1;
  }
  if (cohort.win_rate < 49.9 || cohort.win_rate > 50.1) {
    std::cerr << "Unexpected win rate: " << cohort.win_rate << std::endl;
    return 1;
  }
  if (cohort.profit_factor < 3.9 || cohort.profit_factor > 4.1) {
    std::cerr << "Unexpected profit factor: " << cohort.profit_factor << std::endl;
    return 1;
  }
  if (cohort.max_drawdown < 1.9 || cohort.max_drawdown > 2.1) {
    std::cerr << "Unexpected max drawdown: " << cohort.max_drawdown << std::endl;
    return 1;
  }
  return 0;
}
