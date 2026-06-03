#pragma once

#include <drogon/drogon.h>

#include <atomic>
#include <chrono>
#include <deque>
#include <map>
#include <mutex>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace trade {
namespace trading {

class TradingStatsService;

class SimulatedTradingService {
public:
  static SimulatedTradingService &getInstance();

  Json::Value startSession(const Json::Value &payload, const std::string &mode);
  Json::Value stopSession();
  Json::Value getStatus(const std::string &session_id = "");
  Json::Value updateStrategyParameters(const Json::Value &payload);
  Json::Value getLivePortfolioStatus();
  Json::Value getOrderBookSignals(const std::vector<std::string> &symbols,
                                  int page,
                                  int per_page);
  Json::Value closePosition(const std::string &symbol);
  Json::Value getOpenPositions();

private:
  SimulatedTradingService() = default;
  ~SimulatedTradingService();
  SimulatedTradingService(const SimulatedTradingService &) = delete;
  SimulatedTradingService &operator=(const SimulatedTradingService &) = delete;

  struct PositionState {
    std::string symbol;
    std::string side;
    double quantity = 0.0;
    double entry_price = 0.0;
    double current_price = 0.0;
    double unrealized_pnl = 0.0;
    double pnl_percentage = 0.0;
    long long entry_timestamp = 0;
    std::string entry_time;
    std::string status = "open";
    std::size_t age_ticks = 0;
  };

  struct TradeRecord {
    std::string trade_id;
    std::string session_id;
    std::string symbol;
    std::string side;
    double quantity = 0.0;
    double price = 0.0;
    long long timestamp = 0;
    std::string timestamp_iso;
    std::string strategy_type;
    std::string signal_reason;
    double pnl = 0.0;
    double fees = 0.0;
    double win_probability = 0.0;
    double expected_return = 0.0;
    double model_confidence = 0.0;
    std::string trade_type = "simulated";
  };

  struct SignalRecord {
    std::string signal_id;
    std::string session_id;
    std::string symbol;
    std::string signal_type;
    double strength = 0.0;
    double price = 0.0;
    long long timestamp = 0;
    std::string timestamp_iso;
    Json::Value payload;
    double spread = 0.0;
    double imbalance = 0.0;
    double mid_price = 0.0;
    double best_bid = 0.0;
    double best_ask = 0.0;
    int order_book_depth = 0;
    double volume = 0.0;
    int total_signals = 0;
  };

  void ensureSchema();
  void startWorkerLocked();
  void workerLoop();
  void generateTickLocked();
  SignalRecord buildSignalRecordLocked(const std::string &symbol, std::size_t symbol_index);
  void persistSignalLocked(const SignalRecord &signal);
  void persistTradeLocked(const TradeRecord &trade);
  void openPositionLocked(const SignalRecord &signal, const std::string &reason);
  Json::Value closePositionLocked(const std::string &symbol, const std::string &reason);
  void updateMarkToMarketLocked(const std::map<std::string, double> &prices);
  double basePriceForSymbol(const std::string &symbol) const;
  double positionSizeUsdForSignal(double price) const;
  long long nowEpochSeconds() const;
  std::string nowIsoUtc() const;
  std::string makeId(const std::string &prefix, long long ts, const std::string &symbol,
                     std::size_t sequence) const;
  std::string escapeSql(const std::string &value) const;
  std::string jsonToString(const Json::Value &value) const;
  Json::Value buildStatusJson() const;
  Json::Value buildPortfolioJson() const;
  Json::Value tradeToJson(const TradeRecord &trade) const;
  Json::Value signalToJson(const SignalRecord &signal) const;
  Json::Value positionToJson(const PositionState &position) const;
  void trimHistoryLocked();

  mutable std::mutex mutex_;
  std::thread worker_;
  bool active_ = false;
  bool stop_requested_ = false;
  std::string session_id_;
  std::string mode_ = "simulated";
  std::string strategy_ = "orderbook";
  std::vector<std::string> symbols_;
  Json::Value parameters_ = Json::objectValue;
  std::string started_at_;
  std::string updated_at_;
  long long start_epoch_seconds_ = 0;
  long long tick_ = 0;
  int max_positions_ = 100;
  int position_update_interval_ = 5;
  double initial_capital_ = 10000.0;
  double cash_ = 10000.0;
  double realized_pnl_ = 0.0;
  double unrealized_pnl_ = 0.0;
  double total_fees_ = 0.0;
  double total_positions_value_ = 0.0;
  std::map<std::string, PositionState> positions_;
  std::deque<TradeRecord> recent_trades_;
  std::deque<SignalRecord> recent_signals_;
};

} // namespace trading
} // namespace trade
