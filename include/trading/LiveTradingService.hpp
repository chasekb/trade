#pragma once

#include "exchange/CoinbaseAdvancedClient.hpp"
#include "trading/CoinbasePortfolio.hpp"
#include "trading/TradingStatsCalculator.hpp"

#include <drogon/drogon.h>

#include <atomic>
#include <chrono>
#include <deque>
#include <map>
#include <mutex>
#include <memory>

#include <set>
#include <string>
#include <thread>
#include <vector>

namespace trade {
namespace trading {

class TradingStatsService;

class LiveTradingService {
public:
  static LiveTradingService &getInstance();
  Json::Value startSession(const Json::Value &payload);
  Json::Value stopSession();
  Json::Value getStatus(const std::string &session_id = "");
  Json::Value updateStrategyParameters(const Json::Value &payload);
  Json::Value getLivePortfolioStatus();
  Json::Value refreshLivePortfolioStatus();
  Json::Value refreshLiveTabProducerStatus();
  Json::Value submitLiveOrder(const Json::Value &payload);
  Json::Value liquidateCoinbaseHoldings(const Json::Value &payload);
  Json::Value getOrderBookSignals(const std::vector<std::string> &symbols,
                                  int page,
                                  int per_page);
  Json::Value closePosition(const std::string &symbol);
  Json::Value getOpenPositions();

private:
  LiveTradingService();
  ~LiveTradingService();

  LiveTradingService(const LiveTradingService &) = delete;
  LiveTradingService &operator=(const LiveTradingService &) = delete;

  struct PositionState {
    std::string symbol;
    std::string side;
    double quantity = 0.0;
    double managed_quantity = 0.0;
    double entry_price = 0.0;
    double managed_entry_price = 0.0;
    double current_price = 0.0;
    double unrealized_pnl = 0.0;
    double pnl_percentage = 0.0;
    long long entry_timestamp = 0;
    std::string entry_time;
    std::string entry_signal_id;
    std::string status = "open";
    bool session_managed = false;
    double inherited_quantity = 0.0;
    std::string management_state = "coinbase_unmanaged";
    bool eligible_for_strategy_management = false;
    std::size_t age_ticks = 0;
    // Prediction-time ML values captured at entry; exit rows persist these so
    // calibration analysis never sees outcome-derived (hindsight) numbers.
    double entry_win_probability = 0.5;
    double entry_expected_return = 0.0;
    double entry_model_confidence = 0.0;
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
    std::string trade_type = "live";
    bool is_closing_leg = false;
  };

  // Per-symbol rolling state derived only from Coinbase market data.
  struct SymbolMarketState {
    double price = 0.0;
    double imbalance = 0.0;
    double last_return = 0.0;

    // Rolling close history for the indicator strategies (sma/ema/rsi/...).
    std::deque<double> price_history;
    long long last_entry_tick = -1;
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

  // Rows produced under the mutex, flushed to Postgres outside it so API
  // handlers sharing the mutex never wait on database I/O.
  struct PendingWrites {
    std::vector<SignalRecord> signals;
    std::vector<TradeRecord> trades;
  };

  // Real market snapshot fetched from Coinbase public endpoints (live mode)
  // outside the mutex, then consumed by the tick under it.
  struct MarketQuote {
    bool valid = false;
    double mid = 0.0;
    double spread = 0.0;
    double best_bid = 0.0;
    double best_ask = 0.0;
    double imbalance = 0.0;
    double volume = 0.0;
    int depth = 0;
  };

  // Exchange order produced by a live tick with order execution enabled;
  // dispatched outside the mutex.
  struct OrderIntent {
    std::string session_id;
    std::string product_id;
    std::string side;
    double amount = 0.0;
    bool amount_is_quote = false;
    std::string reason;
    std::string action;
    SignalRecord signal;
    PositionState position;
    double reserved_cash = 0.0;
  };

  struct PendingLiveOrder {
    std::string order_id;
    std::string client_order_id;
    OrderIntent intent;
    bool persisted = false;
    bool fill_applied = false;
    bool account_snapshot_reflects_fill = false;
    int client_lookup_attempts = 0;
  };

  struct OrderDispatchResult {
    bool attempted = false;
    bool accepted = false;
    std::string error;
  };

  void ensureSchema();
  void startWorkerLocked();
  void workerLoop();
  std::vector<std::string> selectLiveQuoteBatchLocked();
  void generateTickLocked(const std::map<std::string, MarketQuote> &quotes);
  SignalRecord buildSignalRecordLocked(const std::string &symbol, std::size_t symbol_index,
                                       const MarketQuote &quote);
  bool signalPassesMlGateLocked(const SignalRecord &signal) const;
  Json::Value buildEntryExecutionAnalysisLocked(const SignalRecord &signal) const;
  void queueSignalWriteLocked(const SignalRecord &signal);
  void queueTradeWriteLocked(const TradeRecord &trade);
  PendingWrites takePendingWritesLocked();
  bool flushWrites(PendingWrites &&writes);
  void queueOrderIntentLocked(OrderIntent intent);
  std::vector<OrderIntent> takePendingOrdersLocked();
  OrderDispatchResult dispatchOrders(std::vector<OrderIntent> &&orders);
  void resolvePendingLiveOrders();
  bool persistSubmittedOrder(const std::string &client_order_id,
                             const OrderIntent &intent);
  bool persistAcceptedOrder(const std::string &order_id,
                            const std::string &client_order_id);
  bool markPersistedOrderByClientId(const std::string &client_order_id,
                                    const std::string &status);
  bool markPersistedOrderTerminal(const std::string &order_id,
                                  const std::string &status);
  bool recoverPendingOrders();
  void applyLiveFillLocked(const OrderIntent &intent, const exchange::OrderFill &fill,
                           bool account_snapshot_reflects_fill = false);
  bool liveOrderExecutionEnabledLocked() const;
  std::map<std::string, MarketQuote> fetchLiveQuotes(const std::vector<std::string> &symbols);
  bool fetchLiveAccountSnapshot(CoinbasePortfolioSnapshot &snapshot, std::string *error);
  void applyLiveAccountSnapshotLocked(const CoinbasePortfolioSnapshot &snapshot,
                                      bool establish_baseline);
  void openPositionLocked(const SignalRecord &signal, const std::string &reason);
  void addToPositionLocked(const SignalRecord &signal, const std::string &reason);
  Json::Value closePositionLocked(const std::string &symbol, const std::string &reason);
  Json::Value liquidateCoinbaseHoldingLocked(const std::string &symbol);
  void updateMarkToMarketLocked(const std::map<std::string, double> &prices);

  double positionSizeUsdForSignal(const SignalRecord &signal) const;
  std::size_t managedPositionCountLocked() const;
  std::string accountPositionManagementModeLocked() const;
  bool accountPositionManagementAllowsExitsLocked() const;
  bool accountPositionManagementAllowsEntriesLocked() const;
  std::string positionManagementStateLocked(const PositionState &position) const;
  long long nowEpochSeconds() const;
  std::string nowIsoUtc() const;
  std::string makeId(const std::string &prefix, long long ts, const std::string &symbol,
                     std::size_t sequence) const;
  std::string escapeSql(const std::string &value) const;
  std::string jsonToString(const Json::Value &value) const;
  Json::Value buildStatusJson() const;
  Json::Value buildPortfolioJson() const;
  Json::Value buildOrderBookSignalDiagnosticsLocked() const;
  Json::Value buildLiveTabProducerJson(bool credentials_configured) const;
  Json::Value tradeToJson(const TradeRecord &trade) const;
  Json::Value signalToJson(const SignalRecord &signal) const;
  Json::Value positionToJson(const PositionState &position) const;
  void trimHistoryLocked();

  mutable std::mutex mutex_;
  mutable std::mutex lifecycle_mutex_;
  std::thread worker_;
  bool active_ = false;
  bool stop_requested_ = false;
  bool shutdown_requested_ = false;
  bool worker_finished_ = true;
  std::string session_id_;

  std::string strategy_ = "orderbook";
  std::vector<std::string> symbols_;
  Json::Value parameters_ = Json::objectValue;
  std::string started_at_;
  std::string updated_at_;
  long long start_epoch_seconds_ = 0;
  long long tick_ = 0;
  std::size_t live_quote_cursor_ = 0;
  int last_live_quote_requested_symbols_ = 0;
  int last_live_quote_attempted_symbols_ = 0;
  int last_live_quote_succeeded_symbols_ = 0;
  int last_live_quote_skipped_symbols_ = 0;
  std::vector<std::string> last_live_quote_batch_symbols_;

  int max_positions_ = 100;
  int position_update_interval_ = 5;
  double initial_capital_ = 0.0;
  double cash_ = 0.0;
  double cash_hold_ = 0.0;
  double realized_pnl_ = 0.0;
  double unrealized_pnl_ = 0.0;
  double total_fees_ = 0.0;
  double total_positions_value_ = 0.0;
  std::map<std::string, SymbolMarketState> market_state_;
  std::map<std::string, PositionState> positions_;
  std::deque<TradeRecord> recent_trades_;
  std::deque<SignalRecord> recent_signals_;
  // Full per-session trade inputs so status stats never rescan the database
  // while a session is running (recent_trades_ is capped and insufficient).
  std::vector<TradePerformanceInput> session_trade_inputs_;

  std::vector<SignalRecord> pending_signal_writes_;
  std::vector<TradeRecord> pending_trade_writes_;
  std::vector<OrderIntent> pending_orders_;
  std::vector<PendingLiveOrder> pending_live_orders_;
  std::set<std::string> pending_order_symbols_;
  std::set<std::string> account_managed_symbols_;
  std::map<std::string, double> account_available_quantities_;
  std::map<std::string, std::pair<double, int>> managed_quantity_floors_;
  double pending_reserved_cash_ = 0.0;
  CoinbasePortfolioSnapshot last_account_snapshot_;
  bool last_account_snapshot_loaded_ = false;
  std::string last_account_snapshot_error_;
  std::string last_account_snapshot_at_;
  std::unique_ptr<exchange::CoinbaseAdvancedClient> exchange_client_;
};

} // namespace trading
} // namespace trade
