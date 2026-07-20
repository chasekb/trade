#include "trading/LiveTradingService.hpp"

#include "api/PredictController.hpp"
#include "config/Config.hpp"
#include "db/DatabaseManager.hpp"
#include "ml/Types.hpp"
#include <pqxx/pqxx>
#include "trading/TradingStatsCalculator.hpp"
#include "trading/TradingStatsService.hpp"
#include "trading/PortfolioAccounting.hpp"
#include "trading/PositionSizingPolicy.hpp"
#include "trading/StrategySignal.hpp"
#include "ml/Metrics.hpp"
#include "cache/CacheManager.hpp"
#include "utils/Logger.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cctype>
#include <functional>
#include <iomanip>
#include <limits>
#include <memory>
#include <random>

#include <sstream>
#include <stdexcept>
#include <ctime>

namespace trade {
namespace trading {

namespace {
constexpr double kFeeRate = 0.0005;
constexpr std::size_t kMaxRecentTrades = 100;
constexpr std::size_t kMaxRecentSignals = 250;

std::string randomClientOrderId() {
  static thread_local std::mt19937_64 rng(std::random_device{}());
  static constexpr char kHex[] = "0123456789abcdef";
  std::string id = "trade-";
  id.reserve(30);
  for (std::size_t i = 0; i < 24; ++i) {
    id.push_back(kHex[rng() & 0x0f]);
  }
  return id;
}


std::string formatNowIsoUtc() {
  const auto now = std::chrono::system_clock::now();
  const auto t = std::chrono::system_clock::to_time_t(now);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  std::ostringstream oss;
  oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
  return oss.str();
}

std::string epochSecondsToIso(long long epoch_seconds) {
  std::time_t t = static_cast<std::time_t>(epoch_seconds);
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &t);
#else
  gmtime_r(&t, &tm);
#endif
  std::ostringstream oss;
  oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
  return oss.str();
}

long long currentEpochSeconds() {
  return std::chrono::duration_cast<std::chrono::seconds>(
             std::chrono::system_clock::now().time_since_epoch())
      .count();
}

std::string joinStrings(const std::vector<std::string> &items, const char *sep = ",") {
  std::ostringstream oss;
  for (std::size_t i = 0; i < items.size(); ++i) {
    if (i > 0) {
      oss << sep;
    }
    oss << items[i];
  }
  return oss.str();
}

std::vector<std::string> defaultSymbols() {
  return {"BTC-USD", "ETH-USD", "SOL-USD"};
}

Json::Value parseJsonString(const std::string &text) {
  Json::Value root;
  if (text.empty()) {
    return root;
  }

  Json::CharReaderBuilder builder;
  builder["collectComments"] = false;
  std::string errs;
  std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
  const char *begin = text.data();
  const char *end = text.data() + text.size();
  if (reader->parse(begin, end, &root, &errs)) {
    return root;
  }
  return Json::Value();
}

std::string makeSessionId() {
  return "live_" + std::to_string(currentEpochSeconds());
}

constexpr std::size_t kMaxPriceHistory = 512;
// Live quotes are fetched sequentially over HTTPS each tick; cap the universe
// so one tick stays within the cadence budget.
constexpr std::size_t kMaxLiveQuoteSymbols = 10;

bool isOrderBookStrategy(const std::string &strategy) {
  return strategy == "orderbook" || strategy == "ml_enhanced_orderbook";
}

// Form inputs may deliver numbers as strings; read either representation.
double paramNumber(const Json::Value &params, const char *key, double fallback) {
  if (!params.isMember(key)) {
    return fallback;
  }
  const Json::Value &value = params[key];
  if (value.isNumeric()) {
    return value.asDouble();
  }
  if (value.isString()) {
    try {
      return std::stod(value.asString());
    } catch (...) {
    }
  }
  return fallback;
}

StrategyParams buildStrategyParams(const Json::Value &p, const std::string &strategy) {
  StrategyParams sp;
  if (strategy == "sma" || strategy == "ema") {
    sp.short_window = paramNumber(p, "short_window", sp.short_window);
    sp.long_window = paramNumber(p, "long_window", sp.long_window);
  } else if (strategy == "rsi") {
    sp.rsi_window = paramNumber(p, "window", sp.rsi_window);
    sp.rsi_overbought = paramNumber(p, "overbought", sp.rsi_overbought);
    sp.rsi_oversold = paramNumber(p, "oversold", sp.rsi_oversold);
  } else if (strategy == "bollinger") {
    sp.bb_window = paramNumber(p, "window", sp.bb_window);
    sp.bb_std_dev = paramNumber(p, "std_dev", sp.bb_std_dev);
  } else if (strategy == "macd") {
    sp.macd_fast = paramNumber(p, "fast_window", sp.macd_fast);
    sp.macd_slow = paramNumber(p, "slow_window", sp.macd_slow);
    sp.macd_signal = paramNumber(p, "signal_window", sp.macd_signal);
  } else if (strategy == "stochastic") {
    sp.stoch_k = paramNumber(p, "k_window", sp.stoch_k);
    sp.stoch_d = paramNumber(p, "d_window", sp.stoch_d);
    sp.stoch_overbought = paramNumber(p, "overbought", sp.stoch_overbought);
    sp.stoch_oversold = paramNumber(p, "oversold", sp.stoch_oversold);
  } else if (strategy == "fibonacci") {
    sp.fib_lookback = paramNumber(p, "fib_lookback_period", sp.fib_lookback);
    if (p.isMember("fib_levels") && p["fib_levels"].isString()) {
      std::vector<double> levels;
      std::stringstream stream(p["fib_levels"].asString());
      std::string item;
      while (std::getline(stream, item, ',')) {
        try {
          levels.push_back(std::stod(item));
        } catch (...) {
        }
      }
      if (!levels.empty()) {
        sp.fib_levels = levels;
      }
    }
  } else if (strategy == "dca") {
    // One configured hour maps to one minute of worker ticks so DCA cadences
    // remain practical for an actively running session.
    const double interval_hours = paramNumber(p, "interval_hours", 24.0);
    sp.dca_interval_ticks =
        std::max<long long>(1, static_cast<long long>(std::llround(interval_hours * 60.0)));
  }
  return sp;
}

std::string sanitizeSide(const std::string &side) {
  if (side == "sell") {
    return "sell";
  }
  return "buy";
}

TradePerformanceInput toTradePerformanceInput(const pqxx::row &row) {
  TradePerformanceInput input;
  try {
    input.pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
    input.fees = row["fees"].is_null() ? 0.0 : row["fees"].as<double>();
    input.quantity = row["size"].is_null() ? 0.0 : row["size"].as<double>();
    input.price = row["price"].is_null() ? 0.0 : row["price"].as<double>();
    const long long timestamp_epoch = row["timestamp"].is_null() ? 0 : row["timestamp"].as<long long>();
    input.timestamp_iso = epochSecondsToIso(timestamp_epoch);
  } catch (...) {
    input = {};
  }
  return input;
}

} // namespace

LiveTradingService &LiveTradingService::getInstance() {
  static LiveTradingService instance;
  return instance;
}

LiveTradingService::LiveTradingService() = default;

LiveTradingService::~LiveTradingService() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    active_ = false;
    stop_requested_ = true;
    shutdown_requested_ = true;
  }
  if (worker_.joinable()) {
    worker_.join();
  }
}

std::string LiveTradingService::escapeSql(const std::string &value) const {
  std::string escaped;
  escaped.reserve(value.size() + 8);
  for (char c : value) {
    if (c == '\'') {
      escaped += "''";
    } else {
      escaped += c;
    }
  }
  return escaped;
}

std::string LiveTradingService::jsonToString(const Json::Value &value) const {
  Json::StreamWriterBuilder builder;
  builder["indentation"] = "";
  builder["precision"] = 17;
  return Json::writeString(builder, value);
}

std::string LiveTradingService::nowIsoUtc() const { return formatNowIsoUtc(); }

long long LiveTradingService::nowEpochSeconds() const { return currentEpochSeconds(); }

std::string LiveTradingService::makeId(const std::string &prefix, long long ts,
                                           const std::string &symbol,
                                           std::size_t sequence) const {
  std::ostringstream oss;
  oss << prefix << '_' << ts << '_' << sequence << '_';
  for (char c : symbol) {
    if (std::isalnum(static_cast<unsigned char>(c))) {
      oss << c;
    }
  }
  return oss.str();
}

void LiveTradingService::ensureSchema() {
  try {
    DatabaseManager::getInstance().query(R"SQL(
      CREATE TABLE IF NOT EXISTS order_book_signals (
        signal_id TEXT PRIMARY KEY,
        session_id TEXT,
        symbol TEXT,
        signal_type TEXT,
        strength REAL,
        price REAL,
        timestamp BIGINT,
        signal_data TEXT,
        spread REAL,
        imbalance REAL,
        mid_price REAL,
        best_bid REAL,
        best_ask REAL,
        order_book_depth INTEGER,
        volume REAL,
        total_signals INTEGER
      )
    )SQL");

    DatabaseManager::getInstance().query(R"SQL(
      CREATE TABLE IF NOT EXISTS individual_trades (
        trade_id TEXT PRIMARY KEY,
        session_id TEXT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        size DOUBLE PRECISION,
        price DOUBLE PRECISION NOT NULL,
        timestamp BIGINT NOT NULL,
        strategy_type TEXT,
        signal_reason TEXT,
        pnl DOUBLE PRECISION,
        fees DOUBLE PRECISION,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        win_probability DOUBLE PRECISION,
        expected_return DOUBLE PRECISION,
        model_confidence DOUBLE PRECISION,
        trade_type TEXT DEFAULT 'live'
      )
    )SQL");

    DatabaseManager::getInstance().query(R"SQL(
      CREATE TABLE IF NOT EXISTS live_coinbase_orders (
        client_order_id TEXT PRIMARY KEY,
        order_id TEXT UNIQUE,
        session_id TEXT,
        product_id TEXT NOT NULL,
        side TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        amount_is_quote BOOLEAN NOT NULL,
        reason TEXT,
        action TEXT NOT NULL,
        reserved_cash DOUBLE PRECISION NOT NULL,
        signal_json TEXT NOT NULL,
        position_json TEXT NOT NULL,
        status TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    )SQL");
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to ensure live trading schema: {}", e.what());
  }
}


double LiveTradingService::positionSizeUsdForSignal(const SignalRecord &signal) const {
  const double pct = parameters_.isMember("position_size_percent")
                         ? parameters_["position_size_percent"].asDouble()
                         : 1.0;
  const std::string size_mode = parameters_.isMember("position_size_mode")
                                    ? parameters_["position_size_mode"].asString()
                                    : "percent";
  const double position_value = parameters_.isMember("position_size_value")
                                    ? parameters_["position_size_value"].asDouble()
                                    : 1.0;

  // Percent sizing compounds: percent of the current total value, not the
  // session's starting capital.
  const double capital = percentSizingCapital(
      cash_, total_positions_value_, initial_capital_);
  PositionSizingInputs inputs;
  inputs.base_usd = size_mode == "dollar" ? std::max(0.0, position_value)
                                            : capital * std::max(0.0, pct) / 100.0;
  if (strategy_ == "dca" || strategy_ == "buyandhold") {
    const double strategy_amount =
        std::max(0.0, paramNumber(parameters_, "amount", inputs.base_usd));
    inputs.base_usd = std::min(inputs.base_usd, strategy_amount);
  }
  inputs.signal_strength = signal.strength;
  inputs.win_probability = signal.payload.get("ml_analysis", Json::Value(Json::objectValue))
                               .get("win_probability", Json::Value(0.5))
                               .asDouble();
  inputs.expected_return = signal.payload.get("ml_analysis", Json::Value(Json::objectValue))
                               .get("expected_return", Json::Value(0.0))
                               .asDouble();
  inputs.model_confidence = signal.payload.get("ml_analysis", Json::Value(Json::objectValue))
                                 .get("confidence", Json::Value(0.0))
                                 .asDouble();
  inputs.spread_percent = signal.mid_price > 0.0 ? signal.spread / signal.mid_price : 0.0;

  // Scoped to this service's trade mode so cross-mode history cannot skew
  // sizing; served from the stats service's short-TTL cache.
  const auto live_stats =
      TradingStatsService::getInstance().getTradingStats(TradingStatsFilter{"live", std::string()});
  inputs.live_profit_factor = live_stats.profit_factor;
  inputs.live_sharpe_ratio = live_stats.sharpe_ratio;
  inputs.live_max_drawdown = live_stats.max_drawdown;
  inputs.live_total_fees = live_stats.total_fees;
  inputs.live_net_pnl = live_stats.net_pnl;

  const auto recent_metrics = CacheManager::getInstance().get_last_metrics();
  if (!recent_metrics.cohort_metrics.empty()) {
    double weighted_profit_factor = 0.0;
    double weighted_sharpe_ratio = 0.0;
    double weighted_drawdown = 0.0;
    std::size_t total_samples = 0;
    for (const auto &cohort : recent_metrics.cohort_metrics) {
      if (cohort.sample_count <= 0) {
        continue;
      }
      const double weight = static_cast<double>(cohort.sample_count);
      total_samples += static_cast<std::size_t>(cohort.sample_count);
      weighted_profit_factor += cohort.profit_factor * weight;
      weighted_sharpe_ratio += cohort.sharpe_ratio * weight;
      weighted_drawdown += cohort.max_drawdown * weight;
    }
    if (total_samples > 0) {
      const double denominator = static_cast<double>(total_samples);
      inputs.cohort_sample_count = total_samples;
      inputs.cohort_profit_factor = weighted_profit_factor / denominator;
      inputs.cohort_sharpe_ratio = weighted_sharpe_ratio / denominator;
      inputs.cohort_avg_drawdown = weighted_drawdown / denominator;
    }
  }

  return calculate_position_size_usd(inputs);
}

std::size_t LiveTradingService::managedPositionCountLocked() const {
  return static_cast<std::size_t>(std::count_if(
      positions_.begin(), positions_.end(),
      [](const auto &entry) { return entry.second.session_managed; }));
}

Json::Value LiveTradingService::signalToJson(const SignalRecord &signal) const {
  Json::Value out;
  out["signal_id"] = signal.signal_id;
  out["session_id"] = signal.session_id;
  out["symbol"] = signal.symbol;
  out["signal_type"] = signal.signal_type;
  out["signal"] = signal.signal_type;
  out["signal_generated"] = signal.signal_type != "hold";
  out["strength"] = signal.strength;
  out["signal_strength"] = signal.strength;
  out["price"] = signal.price;
  out["timestamp"] = signal.timestamp_iso;
  const Json::Value signal_reason = signal.payload.get("signal_reason", Json::Value(""));
  out["signal_reason"] = signal_reason.asString();
  out["data_status"] = signal.signal_type == "hold" ? "insufficient" : "sufficient";
  out["spread"] = signal.spread;
  out["volume"] = signal.volume;
  out["buy_volume"] = signal.payload.get("buy_volume", Json::Value(0.0)).asDouble();
  out["sell_volume"] = signal.payload.get("sell_volume", Json::Value(0.0)).asDouble();
  out["imbalance_ratio"] = signal.payload.get("imbalance_ratio", Json::Value(0.0)).asDouble();
  out["prediction"] = signal.payload.get("prediction", Json::Value("HOLD")).asString();
  out["criteria_analysis"] = signal.payload.get("criteria_analysis", Json::Value(Json::objectValue));
  out["ml_analysis"] = signal.payload.get("ml_analysis", Json::Value(Json::objectValue));
  out["strength_composition"] = signal.payload.get("strength_composition", Json::Value(Json::objectValue));
  return out;
}

Json::Value LiveTradingService::tradeToJson(const TradeRecord &trade) const {
  Json::Value out;
  out["id"] = trade.trade_id;
  out["trade_id"] = trade.trade_id;
  out["session_id"] = trade.session_id;
  out["symbol"] = trade.symbol;
  out["side"] = trade.side;
  out["quantity"] = trade.quantity;
  out["size"] = trade.quantity;
  out["price"] = trade.price;
  out["pnl"] = trade.pnl;
  out["fees"] = trade.fees;
  out["timestamp"] = trade.timestamp_iso;
  out["strategy_type"] = trade.strategy_type;
  out["signal_reason"] = trade.signal_reason;
  out["win_probability"] = trade.win_probability;
  out["expected_return"] = trade.expected_return;
  out["model_confidence"] = trade.model_confidence;
  out["trade_type"] = trade.trade_type;
  return out;
}

Json::Value LiveTradingService::positionToJson(const PositionState &position) const {
  Json::Value out;
  out["symbol"] = position.symbol;
  out["quantity"] = position.quantity;
  out["managed_quantity"] = position.managed_quantity;
  out["entry_price"] = position.entry_price;
  out["managed_entry_price"] = position.managed_entry_price;
  out["current_price"] = position.current_price;
  out["unrealized_pnl"] = position.unrealized_pnl;
  out["pnl_percentage"] = position.pnl_percentage;
  out["entry_time"] = position.entry_time;
  out["status"] = position.status;
  out["side"] = position.side;
  out["session_managed"] = position.session_managed;
  return out;
}

void LiveTradingService::queueSignalWriteLocked(const SignalRecord &signal) {
  pending_signal_writes_.push_back(signal);
}

void LiveTradingService::queueTradeWriteLocked(const TradeRecord &trade) {
  pending_trade_writes_.push_back(trade);
  session_trade_inputs_.push_back(TradePerformanceInput{
      trade.pnl, trade.fees, trade.quantity, trade.price, trade.timestamp_iso});
}

LiveTradingService::PendingWrites LiveTradingService::takePendingWritesLocked() {
  PendingWrites writes;
  writes.signals.swap(pending_signal_writes_);
  writes.trades.swap(pending_trade_writes_);
  return writes;
}

bool LiveTradingService::liveOrderExecutionEnabledLocked() const {
  if (!exchange_client_ || !exchange_client_->configured()) {
    return false;
  }
  const Json::Value flag = parameters_.get("live_order_execution", Json::Value(false));
  return flag.isString() ? flag.asString() == "true" : flag.asBool();
}

void LiveTradingService::queueOrderIntentLocked(OrderIntent intent) {
  if (intent.session_id.empty()) {
    intent.session_id = session_id_;
  }
  pending_order_symbols_.insert(intent.product_id);
  pending_reserved_cash_ += intent.reserved_cash;
  pending_orders_.push_back(std::move(intent));
}

std::vector<LiveTradingService::OrderIntent>
LiveTradingService::takePendingOrdersLocked() {
  std::vector<OrderIntent> orders;
  orders.swap(pending_orders_);
  return orders;
}

void LiveTradingService::applyLiveFillLocked(const OrderIntent &intent,
                                             const exchange::OrderFill &fill,
                                             bool account_snapshot_reflects_fill) {
  pending_order_symbols_.erase(intent.product_id);
  pending_reserved_cash_ = std::max(0.0, pending_reserved_cash_ - intent.reserved_cash);
  if (fill.filled_size <= 0.0) {
    TR_LOG_WARN("Coinbase order {} completed without a fill for {}", fill.order_id,
                intent.product_id);
    return;
  }

  const double quantity = fill.filled_size;
  const double price = fill.average_filled_price > 0.0
                           ? fill.average_filled_price
                           : fill.filled_value / quantity;
  const double notional = fill.filled_value > 0.0 ? fill.filled_value : price * quantity;

  TradeRecord trade;
  const long long ts = intent.action == "close" ? nowEpochSeconds() : intent.signal.timestamp;
  trade.trade_id = fill.order_id.empty()
                       ? makeId("trade", ts, intent.product_id, recent_trades_.size() + 1)
                       : makeId("coinbase", 0, fill.order_id, 0);
  trade.session_id = intent.session_id.empty() ? session_id_ : intent.session_id;
  trade.symbol = intent.product_id;
  trade.side = intent.side;
  trade.quantity = quantity;
  trade.price = price;
  trade.timestamp = ts;
  trade.timestamp_iso = intent.action == "close" ? nowIsoUtc() : intent.signal.timestamp_iso;
  trade.strategy_type = strategy_;
  trade.signal_reason = intent.reason;
  trade.fees = fill.total_fees;
  trade.trade_type = "live";

  if (intent.action == "close") {
    auto position_it = positions_.find(intent.product_id);
    if (position_it == positions_.end() && intent.position.quantity > 0.0) {
      position_it = positions_.emplace(intent.product_id, intent.position).first;
      if (account_snapshot_reflects_fill) {
        position_it->second.quantity = 0.0;
      }
    }
    if (position_it == positions_.end()) {
      TR_LOG_ERROR("Received Coinbase close fill for missing position {}", intent.product_id);
      return;
    }
    PositionState &position = position_it->second;
    if ((account_snapshot_reflects_fill || position.managed_quantity <= 1e-12) &&
        intent.position.managed_quantity > 0.0) {
      position.managed_quantity = account_snapshot_reflects_fill
                                      ? intent.position.managed_quantity
                                      : std::min(position.quantity,
                                                 intent.position.managed_quantity);
      position.managed_entry_price = intent.position.managed_entry_price;
      position.session_managed = position.managed_quantity > 1e-12;
    }
    const double closed_quantity = account_snapshot_reflects_fill
                                       ? quantity
                                       : std::min(quantity, position.quantity);
    const double direction = position.side == "buy" ? 1.0 : -1.0;
    const double managed_closed_quantity = std::min(closed_quantity, position.managed_quantity);
    const double gross_pnl =
        (price - position.managed_entry_price) * managed_closed_quantity * direction;
    trade.quantity = closed_quantity;
    trade.pnl = gross_pnl;
    trade.win_probability = position.entry_win_probability;
    trade.expected_return = position.entry_expected_return;
    trade.model_confidence = position.entry_model_confidence;
    realized_pnl_ += gross_pnl;
    if (!account_snapshot_reflects_fill) {
      position.quantity -= closed_quantity;
    }
    position.managed_quantity = account_snapshot_reflects_fill
                                    ? std::max(0.0, intent.position.managed_quantity -
                                                        managed_closed_quantity)
                                    : std::max(0.0, position.managed_quantity -
                                                        managed_closed_quantity);
    position.managed_quantity = std::min(position.managed_quantity, position.quantity);
    position.session_managed = position.managed_quantity > 1e-12;
    if (position.quantity <= 1e-12) {
      positions_.erase(position_it);
    }
  } else {
    auto position_it = positions_.find(intent.product_id);
    if (position_it == positions_.end()) {
      PositionState position;
      position.symbol = intent.product_id;
      position.side = intent.side;
      position.quantity = quantity;
      position.managed_quantity = quantity;
      position.entry_price = price;
      position.managed_entry_price = price;
      position.current_price = price;
      position.entry_timestamp = intent.signal.timestamp;
      position.entry_time = intent.signal.timestamp_iso;
      position.entry_signal_id = intent.signal.signal_id;
      position.session_managed = true;
      position.entry_win_probability = intent.signal.payload["ml_analysis"]
                                           .get("win_probability", Json::Value(0.5))
                                           .asDouble();
      position.entry_expected_return = intent.signal.payload["ml_analysis"]
                                           .get("expected_return", Json::Value(0.0))
                                           .asDouble();
      position.entry_model_confidence = intent.signal.payload["ml_analysis"]
                                            .get("confidence", Json::Value(0.0))
                                            .asDouble();
      positions_[intent.product_id] = position;
    } else {
      PositionState &position = position_it->second;
      if (account_snapshot_reflects_fill && intent.action == "add" &&
          intent.position.managed_quantity > 0.0) {
        position.managed_quantity = intent.position.managed_quantity;
        position.managed_entry_price = intent.position.managed_entry_price;
      }
      const double previous_managed_notional =
          position.managed_entry_price * position.managed_quantity;
      if (!account_snapshot_reflects_fill) {
        position.quantity += quantity;
      }
      position.managed_quantity += quantity;
      if (account_snapshot_reflects_fill) {
        position.quantity = std::max(position.quantity,
                                     position.managed_quantity);
      }
      position.managed_quantity =
          std::min(position.managed_quantity, position.quantity);
      position.managed_entry_price =
          (previous_managed_notional + notional) / position.managed_quantity;
      position.entry_price = position.managed_entry_price;
      position.current_price = price;
      position.session_managed = position.managed_quantity > 1e-12;
    }
    trade.pnl = 0.0;
    trade.win_probability = intent.signal.payload["ml_analysis"]
                                .get("win_probability", Json::Value(0.5))
                                .asDouble();
    trade.expected_return = intent.signal.payload["ml_analysis"]
                                .get("expected_return", Json::Value(0.0))
                                .asDouble();
    trade.model_confidence = intent.signal.payload["ml_analysis"]
                                 .get("confidence", Json::Value(0.0))
                                 .asDouble();
    const auto managed_position = positions_.find(intent.product_id);
    if (managed_position != positions_.end() &&
        managed_position->second.managed_quantity > 0.0) {
      managed_quantity_floors_[intent.product_id] =
          {managed_position->second.managed_quantity, 30};
    }
    market_state_[intent.product_id].last_entry_tick = tick_;
  }

  total_fees_ += fill.total_fees;
  queueTradeWriteLocked(trade);
  recent_trades_.push_back(trade);
  updated_at_ = nowIsoUtc();
  trimHistoryLocked();
}

bool LiveTradingService::persistSubmittedOrder(const std::string &client_order_id,
                                               const OrderIntent &intent) {
  try {
    Json::Value signal;
    signal["signal_id"] = intent.signal.signal_id;
    signal["session_id"] = intent.signal.session_id;
    signal["symbol"] = intent.signal.symbol;
    signal["signal_type"] = intent.signal.signal_type;
    signal["strength"] = intent.signal.strength;
    signal["price"] = intent.signal.price;
    signal["timestamp"] = Json::Int64(intent.signal.timestamp);
    signal["timestamp_iso"] = intent.signal.timestamp_iso;
    signal["spread"] = intent.signal.spread;
    signal["volume"] = intent.signal.volume;
    signal["mid_price"] = intent.signal.mid_price;
    signal["best_bid"] = intent.signal.best_bid;
    signal["best_ask"] = intent.signal.best_ask;
    signal["order_book_depth"] = intent.signal.order_book_depth;
    signal["payload"] = intent.signal.payload;

    Json::Value position;
    position["symbol"] = intent.position.symbol;
    position["side"] = intent.position.side;
    position["quantity"] = intent.position.quantity;
    position["managed_quantity"] = intent.position.managed_quantity;
    position["entry_price"] = intent.position.entry_price;
    position["managed_entry_price"] = intent.position.managed_entry_price;
    position["current_price"] = intent.position.current_price;
    position["session_managed"] = intent.position.session_managed;
    position["entry_timestamp"] = Json::Int64(intent.position.entry_timestamp);
    position["entry_time"] = intent.position.entry_time;
    position["entry_signal_id"] = intent.position.entry_signal_id;
    position["entry_win_probability"] = intent.position.entry_win_probability;
    position["entry_expected_return"] = intent.position.entry_expected_return;
    position["entry_model_confidence"] = intent.position.entry_model_confidence;

    std::ostringstream sql;
    sql << std::setprecision(17)
        << "INSERT INTO live_coinbase_orders "
           "(client_order_id,session_id,product_id,side,amount,amount_is_quote,"
           "reason,action,reserved_cash,signal_json,position_json,status,updated_at) VALUES ('"
        << escapeSql(client_order_id) << "','" << escapeSql(intent.session_id) << "','"
        << escapeSql(intent.product_id) << "','"
        << escapeSql(intent.side) << "'," << intent.amount << ','
        << (intent.amount_is_quote ? "TRUE" : "FALSE") << ",'" << escapeSql(intent.reason)
        << "','" << escapeSql(intent.action) << "'," << intent.reserved_cash << ",'"
        << escapeSql(jsonToString(signal)) << "','" << escapeSql(jsonToString(position))
        << "','submitting',NOW()) ON CONFLICT (client_order_id) DO NOTHING "
           "RETURNING client_order_id";
    const auto rows = DatabaseManager::getInstance().query(sql.str());
    if (rows.empty()) {
      TR_LOG_ERROR("Refusing to submit duplicate Coinbase client order id {}",
                   client_order_id);
      return false;
    }
    return true;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to persist Coinbase order intent {}: {}", client_order_id, e.what());
    return false;
  }
}

bool LiveTradingService::persistAcceptedOrder(const std::string &order_id,
                                              const std::string &client_order_id) {
  try {
    DatabaseManager::getInstance().query(
        "UPDATE live_coinbase_orders SET order_id='" + escapeSql(order_id) +
        "', status='pending', updated_at=NOW() WHERE client_order_id='" +
        escapeSql(client_order_id) + "'");
    return true;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to persist accepted Coinbase order {}: {}", order_id, e.what());
    return false;
  }
}

bool LiveTradingService::markPersistedOrderByClientId(
    const std::string &client_order_id, const std::string &status) {
  try {
    DatabaseManager::getInstance().query(
        "UPDATE live_coinbase_orders SET status='" + escapeSql(status) +
        "', updated_at=NOW() WHERE client_order_id='" +
        escapeSql(client_order_id) + "'");
    return true;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to update Coinbase client order {}: {}", client_order_id,
                 e.what());
    return false;
  }
}

bool LiveTradingService::markPersistedOrderTerminal(const std::string &order_id,
                                                     const std::string &status) {
  try {
    DatabaseManager::getInstance().query(
        "UPDATE live_coinbase_orders SET status='" + escapeSql(status) +
        "', updated_at=NOW() WHERE order_id='" + escapeSql(order_id) + "'");
    return true;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to mark Coinbase order {} terminal: {}", order_id, e.what());
    return false;
  }
}

bool LiveTradingService::recoverPendingOrders() {
  try {
    const auto rows = DatabaseManager::getInstance().query(
        "SELECT order_id,client_order_id,session_id,product_id,side,amount,amount_is_quote,reason,action,"
        "reserved_cash,signal_json,position_json FROM live_coinbase_orders "
        "WHERE status IN ('submitting','pending') ORDER BY updated_at");
    for (const auto &row : rows) {
      OrderIntent intent;
      intent.session_id = row["session_id"].is_null() ? "" : row["session_id"].as<std::string>();
      intent.product_id = row["product_id"].as<std::string>();
      intent.side = row["side"].as<std::string>();
      intent.amount = row["amount"].as<double>();
      intent.amount_is_quote = row["amount_is_quote"].as<bool>();
      intent.reason = row["reason"].is_null() ? "Recovered Coinbase order"
                                               : row["reason"].as<std::string>();
      intent.action = row["action"].as<std::string>();
      intent.reserved_cash = row["reserved_cash"].as<double>();
      const Json::Value signal = parseJsonString(row["signal_json"].as<std::string>());
      const Json::Value position = parseJsonString(row["position_json"].as<std::string>());
      if (!signal.isObject() || !position.isObject() ||
          (intent.side != "buy" && intent.side != "sell") ||
          !std::isfinite(intent.amount) || intent.amount <= 0.0 ||
          !std::isfinite(intent.reserved_cash) || intent.reserved_cash < 0.0) {
        throw std::runtime_error("invalid persisted Coinbase order state");
      }
      intent.signal.signal_id = signal.get("signal_id", "").asString();
      intent.signal.session_id = signal.get("session_id", "").asString();
      intent.signal.symbol = signal.get("symbol", intent.product_id).asString();
      intent.signal.signal_type = signal.get("signal_type", intent.side).asString();
      intent.signal.strength = signal.get("strength", 0.0).asDouble();
      intent.signal.price = signal.get("price", 0.0).asDouble();
      intent.signal.timestamp = signal.get("timestamp", Json::Int64(0)).asInt64();
      intent.signal.timestamp_iso = signal.get("timestamp_iso", "").asString();
      intent.signal.spread = signal.get("spread", 0.0).asDouble();
      intent.signal.volume = signal.get("volume", 0.0).asDouble();
      intent.signal.mid_price = signal.get("mid_price", 0.0).asDouble();
      intent.signal.best_bid = signal.get("best_bid", 0.0).asDouble();
      intent.signal.best_ask = signal.get("best_ask", 0.0).asDouble();
      intent.signal.order_book_depth = signal.get("order_book_depth", 0).asInt();
      intent.signal.payload = signal.get("payload", Json::Value(Json::objectValue));
      intent.position.symbol = position.get("symbol", intent.product_id).asString();
      intent.position.side = position.get("side", "buy").asString();
      intent.position.quantity = position.get("quantity", 0.0).asDouble();
      intent.position.managed_quantity = position.get("managed_quantity", 0.0).asDouble();
      intent.position.entry_price = position.get("entry_price", 0.0).asDouble();
      intent.position.managed_entry_price =
          position.get("managed_entry_price", 0.0).asDouble();
      intent.position.current_price = position.get("current_price", 0.0).asDouble();
      intent.position.session_managed = position.get("session_managed", false).asBool();
      intent.position.entry_timestamp =
          position.get("entry_timestamp", Json::Int64(0)).asInt64();
      intent.position.entry_time = position.get("entry_time", "").asString();
      intent.position.entry_signal_id = position.get("entry_signal_id", "").asString();
      intent.position.entry_win_probability =
          position.get("entry_win_probability", 0.5).asDouble();
      intent.position.entry_expected_return =
          position.get("entry_expected_return", 0.0).asDouble();
      intent.position.entry_model_confidence =
          position.get("entry_model_confidence", 0.0).asDouble();
      pending_live_orders_.push_back(
          PendingLiveOrder{row["order_id"].is_null() ? "" : row["order_id"].as<std::string>(),
                           row["client_order_id"].as<std::string>(), intent, true, false, true, 0});
      pending_order_symbols_.insert(intent.product_id);
      pending_reserved_cash_ += intent.reserved_cash;
    }
    return true;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to recover pending Coinbase orders: {}", e.what());
    return false;
  }
}

LiveTradingService::OrderDispatchResult
LiveTradingService::dispatchOrders(std::vector<OrderIntent> &&orders) {
  OrderDispatchResult dispatch_result;
  if (orders.empty() || !exchange_client_) {
    return dispatch_result;
  }
  const auto cancel_requested = [this]() {
    std::lock_guard<std::mutex> lock(mutex_);
    return shutdown_requested_;
  };
  for (std::size_t index = 0; index < orders.size(); ++index) {
    const OrderIntent &intent = orders[index];
    bool stop_dispatch = false;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      stop_dispatch = stop_requested_ || shutdown_requested_;
      if (stop_dispatch) {
        for (std::size_t remaining = index; remaining < orders.size(); ++remaining) {
          pending_order_symbols_.erase(orders[remaining].product_id);
          pending_reserved_cash_ =
              std::max(0.0, pending_reserved_cash_ - orders[remaining].reserved_cash);
        }
      }
    }
    if (stop_dispatch) {
      break;
    }
    const std::string client_order_id = randomClientOrderId();
    if (!persistSubmittedOrder(client_order_id, intent)) {
      std::lock_guard<std::mutex> lock(mutex_);
      pending_order_symbols_.erase(intent.product_id);
      pending_reserved_cash_ =
          std::max(0.0, pending_reserved_cash_ - intent.reserved_cash);
      dispatch_result.error = "Coinbase order intent could not be persisted";
      continue;
    }
    const auto result = exchange_client_->placeMarketOrder(intent.product_id, intent.side,
                                                           intent.amount, intent.amount_is_quote,
                                                           cancel_requested, client_order_id);
    dispatch_result.attempted = true;
    if (!result.accepted) {
      if (result.definitive_rejection) {
        markPersistedOrderByClientId(client_order_id, "rejected");
        std::lock_guard<std::mutex> lock(mutex_);
        pending_order_symbols_.erase(intent.product_id);
        pending_reserved_cash_ = std::max(0.0, pending_reserved_cash_ - intent.reserved_cash);
      } else {
        std::lock_guard<std::mutex> lock(mutex_);
        pending_live_orders_.push_back(
            PendingLiveOrder{"", client_order_id, intent, true, false, false});
      }
      TR_LOG_ERROR("Coinbase order FAILED: {} {} {} ({}): {} [{}]", intent.side, intent.amount,
                   intent.product_id, intent.amount_is_quote ? "quote" : "base", result.error,
                   intent.reason);
      dispatch_result.error = result.error;
      continue;
    }
    dispatch_result.accepted = true;
    const bool persisted =
        persistAcceptedOrder(result.order_id, client_order_id);
    {
      std::lock_guard<std::mutex> lock(mutex_);
      pending_live_orders_.push_back(
          PendingLiveOrder{result.order_id, client_order_id, intent, persisted, false, false});
    }
    TR_LOG_INFO("Coinbase order accepted; fill pending: {} {} {} order_id={} [{}]", intent.side,
                intent.amount, intent.product_id, result.order_id, intent.reason);
  }
  return dispatch_result;
}

void LiveTradingService::resolvePendingLiveOrders() {
  if (!exchange_client_) {
    return;
  }
  std::vector<PendingLiveOrder> pending_orders;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_orders.swap(pending_live_orders_);
  }
  if (pending_orders.empty()) {
    return;
  }
  std::vector<PendingLiveOrder> still_pending;
  bool settled_any = false;
  for (std::size_t index = 0; index < pending_orders.size(); ++index) {
    PendingLiveOrder pending = pending_orders[index];
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (shutdown_requested_) {
        pending_live_orders_.insert(pending_live_orders_.end(), still_pending.begin(),
                                    still_pending.end());
        pending_live_orders_.insert(pending_live_orders_.end(), pending_orders.begin() + index,
                                    pending_orders.end());
        return;
      }
    }
    if (pending.order_id.empty()) {
      std::string lookup_error;
      const auto lookup_status = exchange_client_->findOrderIdByClientOrderId(
          pending.client_order_id, pending.order_id, &lookup_error);
      if (lookup_status != exchange::ClientOrderLookupStatus::Found) {
        if (lookup_status == exchange::ClientOrderLookupStatus::CompleteNotFound) {
          ++pending.client_lookup_attempts;
        }
        if (lookup_status == exchange::ClientOrderLookupStatus::CompleteNotFound &&
            pending.client_lookup_attempts >= 30) {
          markPersistedOrderByClientId(pending.client_order_id, "not_found");
          std::lock_guard<std::mutex> lock(mutex_);
          pending_order_symbols_.erase(pending.intent.product_id);
          pending_reserved_cash_ = std::max(
              0.0, pending_reserved_cash_ - pending.intent.reserved_cash);
          continue;
        }
        still_pending.push_back(std::move(pending));
        continue;
      }
      pending.persisted = false;
    }
    if (!pending.persisted) {
      pending.persisted =
          persistAcceptedOrder(pending.order_id, pending.client_order_id);
      if (!pending.persisted) {
        still_pending.push_back(std::move(pending));
        continue;
      }
    }
    exchange::OrderFill fill;
    std::string error;
    if (!exchange_client_->getOrderFill(pending.order_id, fill, &error)) {
      still_pending.push_back(pending);
      continue;
    }
    PendingWrites settlement_writes;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (!pending.fill_applied) {
        applyLiveFillLocked(pending.intent, fill,
                            pending.account_snapshot_reflects_fill);
        pending.fill_applied = true;
      }
      settlement_writes = takePendingWritesLocked();
    }
    if (!flushWrites(std::move(settlement_writes))) {
      still_pending.push_back(std::move(pending));
      continue;
    }
    if (!markPersistedOrderTerminal(
            pending.order_id,
            fill.status.empty() ? "terminal" : fill.status)) {
      still_pending.push_back(std::move(pending));
      continue;
    }
    settled_any = true;
  }
  if (!still_pending.empty()) {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_live_orders_.insert(pending_live_orders_.end(), still_pending.begin(),
                                still_pending.end());
  }
  if (settled_any) {
    CoinbasePortfolioSnapshot snapshot;
    std::string snapshot_error;
    if (fetchLiveAccountSnapshot(snapshot, &snapshot_error)) {
      std::lock_guard<std::mutex> lock(mutex_);
      applyLiveAccountSnapshotLocked(snapshot, false);
    } else {
      TR_LOG_WARN("Unable to refresh Coinbase account after settlement: {}",
                  snapshot_error);
    }
  }
}

std::map<std::string, LiveTradingService::MarketQuote>
LiveTradingService::fetchLiveQuotes(const std::vector<std::string> &symbols) {
  std::map<std::string, MarketQuote> quotes;
  if (!exchange_client_) {
    return quotes;
  }

  std::size_t fetched = 0;
  for (const auto &symbol : symbols) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (stop_requested_ || shutdown_requested_) {
        break;
      }
    }
    if (fetched >= kMaxLiveQuoteSymbols) {
      TR_LOG_WARN("Live quote universe capped at {} symbols; {} requested",
                  kMaxLiveQuoteSymbols, symbols.size());
      break;
    }
    ++fetched;

    exchange::OrderBookSummary book;
    std::string error;
    if (!exchange_client_->getOrderBook(symbol, book, &error)) {
      TR_LOG_WARN("Failed to fetch order book for {}: {}", symbol, error);
      continue;
    }

    MarketQuote quote;
    quote.valid = true;
    quote.mid = book.mid;
    quote.spread = book.spread;
    quote.best_bid = book.best_bid;
    quote.best_ask = book.best_ask;
    quote.imbalance = book.imbalance;
    quote.volume = book.bid_volume + book.ask_volume;
    quote.depth = book.depth;
    quotes[symbol] = quote;
  }
  return quotes;
}

bool LiveTradingService::fetchLiveAccountSnapshot(CoinbasePortfolioSnapshot &snapshot,
                                                      std::string *error) {
  if (!exchange_client_ || !exchange_client_->configured()) {
    if (error != nullptr) {
      *error = "Coinbase credentials are not configured";
    }
    return false;
  }
  std::vector<exchange::AccountBalance> accounts;
  if (!exchange_client_->listAccounts(accounts, error)) {
    return false;
  }
  std::map<std::string, double> prices;
  for (const auto &account : accounts) {
    if (account.currency.empty() || account.currency == "USD" || account.currency == "USDC" ||
        account.available + account.hold <= 1e-12) {
      continue;
    }
    exchange::ProductTicker ticker;
    std::string ticker_error;
    if (exchange_client_->getTicker(account.currency + "-USD", ticker, &ticker_error) &&
        std::isfinite(ticker.price) && ticker.price > 0.0) {
      prices[account.currency] = ticker.price;
    } else {
      if (error != nullptr) {
        *error = "Unable to value Coinbase holding " + account.currency + ": " + ticker_error;
      }
      return false;
    }
  }
  snapshot = buildCoinbasePortfolioSnapshot(accounts, prices);
  return true;
}

void LiveTradingService::applyLiveAccountSnapshotLocked(
    const CoinbasePortfolioSnapshot &snapshot, bool establish_baseline) {
  cash_ = snapshot.cash_available;
  cash_hold_ = snapshot.cash_hold;
  total_positions_value_ = snapshot.positions_value;
  if (establish_baseline) {
    initial_capital_ = snapshot.total_value;
  }

  std::set<std::string> account_symbols;
  account_available_quantities_.clear();
  unrealized_pnl_ = 0.0;
  for (const auto &holding : snapshot.holdings) {
    const std::string symbol = holding.asset + "-USD";
    double quantity = holding.available + holding.hold;
    auto floor_it = managed_quantity_floors_.find(symbol);
    if (floor_it != managed_quantity_floors_.end()) {
      if (quantity + 1e-12 >= floor_it->second.first ||
          floor_it->second.second <= 0) {
        managed_quantity_floors_.erase(floor_it);
      } else {
        quantity = std::max(quantity, floor_it->second.first);
        --floor_it->second.second;
      }
    }
    account_symbols.insert(symbol);
    account_available_quantities_[symbol] = holding.available;
    auto position_it = positions_.find(symbol);
    if (position_it == positions_.end()) {
      PositionState position;
      position.symbol = symbol;
      position.side = "buy";
      position.quantity = quantity;
      position.entry_price = holding.price_usd;
      position.current_price = holding.price_usd;
      position.entry_timestamp = nowEpochSeconds();
      position.entry_time = nowIsoUtc();
      position.status = "coinbase";
      positions_[symbol] = position;
      continue;
    }
    PositionState &position = position_it->second;
    position.quantity = quantity;
    position.managed_quantity = std::min(position.managed_quantity, quantity);
    position.session_managed = position.managed_quantity > 1e-12;
    position.current_price = holding.price_usd;
    if (position.session_managed && position.managed_entry_price <= 0.0) {
      position.managed_entry_price = holding.price_usd;
    }
    position.entry_price = position.session_managed ? position.managed_entry_price
                                                    : holding.price_usd;
    position.unrealized_pnl = position.session_managed
                                  ? (position.current_price - position.managed_entry_price) *
                                        position.managed_quantity
                                  : 0.0;
    position.pnl_percentage = position.managed_entry_price > 0.0 &&
                                      position.managed_quantity > 0.0
                                  ? position.unrealized_pnl /
                                        (position.managed_entry_price * position.managed_quantity) * 100.0
                                  : 0.0;
    unrealized_pnl_ += position.unrealized_pnl;
  }
  for (auto it = positions_.begin(); it != positions_.end();) {
    if (account_symbols.count(it->first) == 0 && pending_order_symbols_.count(it->first) == 0) {
      auto floor_it = managed_quantity_floors_.find(it->first);
      if (floor_it != managed_quantity_floors_.end() &&
          floor_it->second.second > 0) {
        --floor_it->second.second;
        ++it;
      } else {
        managed_quantity_floors_.erase(it->first);
        it = positions_.erase(it);
      }
    } else {
      ++it;
    }
  }
}

bool LiveTradingService::flushWrites(PendingWrites &&writes) {
  try {
  if (!writes.signals.empty()) {
    // Dedupe by id (keeping the latest) so a multi-row upsert never touches
    // the same row twice, then persist the whole tick in one statement.
    std::map<std::string, const SignalRecord *> unique_signals;
    for (const auto &signal : writes.signals) {
      unique_signals[signal.signal_id] = &signal;
    }

    std::ostringstream sql;
    sql << "INSERT INTO order_book_signals ("
        << "signal_id, session_id, symbol, signal_type, strength, price, timestamp, signal_data, "
        << "spread, imbalance, mid_price, best_bid, best_ask, order_book_depth, volume, total_signals"
        << ") VALUES ";
    bool first = true;
    for (const auto &[signal_id, signal] : unique_signals) {
      if (!first) {
        sql << ",";
      }
      first = false;
      sql << "("
          << "'" << escapeSql(signal->signal_id) << "',"
          << "'" << escapeSql(signal->session_id) << "',"
          << "'" << escapeSql(signal->symbol) << "',"
          << "'" << escapeSql(signal->signal_type) << "',"
          << signal->strength << ","
          << signal->price << ","
          << signal->timestamp << ","
          << "'" << escapeSql(jsonToString(signal->payload)) << "',"
          << signal->spread << ","
          << signal->imbalance << ","
          << signal->mid_price << ","
          << signal->best_bid << ","
          << signal->best_ask << ","
          << signal->order_book_depth << ","
          << signal->volume << ","
          << signal->total_signals
          << ")";
    }
    sql << " ON CONFLICT (signal_id) DO UPDATE SET "
        << "signal_type = EXCLUDED.signal_type, strength = EXCLUDED.strength, price = EXCLUDED.price, "
        << "timestamp = EXCLUDED.timestamp, signal_data = EXCLUDED.signal_data, spread = EXCLUDED.spread, "
        << "imbalance = EXCLUDED.imbalance, mid_price = EXCLUDED.mid_price, best_bid = EXCLUDED.best_bid, "
        << "best_ask = EXCLUDED.best_ask, order_book_depth = EXCLUDED.order_book_depth, volume = EXCLUDED.volume, "
        << "total_signals = EXCLUDED.total_signals";

    DatabaseManager::getInstance().query(sql.str());
  }

  if (!writes.trades.empty()) {
    std::map<std::string, const TradeRecord *> unique_trades;
    for (const auto &trade : writes.trades) {
      unique_trades[trade.trade_id] = &trade;
    }

    std::ostringstream sql;
    sql << "INSERT INTO individual_trades ("
        << "trade_id, session_id, symbol, side, size, price, timestamp, strategy_type, signal_reason, pnl, fees, "
        << "win_probability, expected_return, model_confidence, trade_type"
        << ") VALUES ";
    bool first = true;
    for (const auto &[trade_id, trade] : unique_trades) {
      if (!first) {
        sql << ",";
      }
      first = false;
      sql << "("
          << "'" << escapeSql(trade->trade_id) << "',"
          << "'" << escapeSql(trade->session_id) << "',"
          << "'" << escapeSql(trade->symbol) << "',"
          << "'" << escapeSql(trade->side) << "',"
          << trade->quantity << ","
          << trade->price << ","
          << trade->timestamp << ","
          << "'" << escapeSql(trade->strategy_type) << "',"
          << "'" << escapeSql(trade->signal_reason) << "',"
          << trade->pnl << ","
          << trade->fees << ","
          << trade->win_probability << ","
          << trade->expected_return << ","
          << trade->model_confidence << ","
          << "'" << escapeSql(trade->trade_type) << "'"
          << ")";
    }
    sql << " ON CONFLICT (trade_id) DO UPDATE SET "
        << "symbol = EXCLUDED.symbol, side = EXCLUDED.side, size = EXCLUDED.size, price = EXCLUDED.price, "
        << "timestamp = EXCLUDED.timestamp, strategy_type = EXCLUDED.strategy_type, signal_reason = EXCLUDED.signal_reason, "
        << "pnl = EXCLUDED.pnl, fees = EXCLUDED.fees, win_probability = EXCLUDED.win_probability, "
        << "expected_return = EXCLUDED.expected_return, model_confidence = EXCLUDED.model_confidence, "
        << "trade_type = EXCLUDED.trade_type";

    DatabaseManager::getInstance().query(sql.str());
  }
  return true;
  } catch (const std::exception &e) {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_signal_writes_.insert(pending_signal_writes_.end(), writes.signals.begin(),
                                  writes.signals.end());
    pending_trade_writes_.insert(pending_trade_writes_.end(), writes.trades.begin(),
                                 writes.trades.end());
    TR_LOG_WARN("Failed to persist trading writes; queued for retry: {}", e.what());
    return false;
  }
}

LiveTradingService::SignalRecord
LiveTradingService::buildSignalRecordLocked(const std::string &symbol,
                                                 std::size_t symbol_index,
                                                 const MarketQuote &quote) {
  SignalRecord signal;
  signal.session_id = session_id_;
  signal.symbol = symbol;
  signal.timestamp = nowEpochSeconds();
  signal.timestamp_iso = nowIsoUtc();
  signal.signal_id = makeId("sig", signal.timestamp, symbol, static_cast<std::size_t>(tick_));

  auto [state_it, state_inserted] = market_state_.try_emplace(symbol);
  SymbolMarketState &state = state_it->second;
  if (state_inserted) {
    state.price = quote.mid;
  }

  const double previous_price = state.price > 0.0 ? state.price : quote.mid;
    state.last_return =
        previous_price > 0.0 ? (quote.mid - previous_price) / previous_price : 0.0;
  state.price = quote.mid;
  state.imbalance = quote.imbalance;
  const double mid = quote.mid;
  const double imbalance = quote.imbalance;
  const double spread = std::max(0.0001, quote.spread);

  state.price_history.push_back(mid);
  while (state.price_history.size() > kMaxPriceHistory) {
    state.price_history.pop_front();
  }

  // Order-book strategies signal from the live imbalance; every other strategy
  // evaluates its own indicator rule over the rolling price history.
  double strength = 0.0;
  bool generated = false;
  std::string signal_type = "hold";
  std::string strategy_reason;
  if (isOrderBookStrategy(strategy_)) {
    strength = std::min(1.0, std::abs(imbalance) * 1.15);
    generated = strength >= 0.22;
    signal_type = !generated ? "hold" : (imbalance >= 0.0 ? "buy" : "sell");
  } else {
    const bool has_position = positions_.find(symbol) != positions_.end();
    const long long ticks_since_entry =
        state.last_entry_tick < 0 ? std::numeric_limits<long long>::max() / 2
                                  : tick_ - state.last_entry_tick;
    const StrategySignalOutcome outcome = evaluateStrategySignal(
        strategy_, state.price_history, buildStrategyParams(parameters_, strategy_),
        has_position, ticks_since_entry);
    signal_type = outcome.signal_type;
    strength = outcome.strength;
    generated = signal_type != "hold";
    strategy_reason = outcome.reason;
  }

  signal.signal_type = signal_type;
  signal.strength = strength;
  signal.price = mid;
  signal.spread = spread;
  signal.imbalance = imbalance;
  signal.mid_price = mid;
  signal.best_bid = quote.best_bid;
  signal.best_ask = quote.best_ask;
  signal.order_book_depth = quote.depth;
  signal.volume = quote.volume;
  signal.total_signals = static_cast<int>(tick_ * std::max<std::size_t>(1, symbols_.size()) + symbol_index + 1);

  Json::Value payload(Json::objectValue);
  payload["signal_id"] = signal.signal_id;
  payload["session_id"] = signal.session_id;
  payload["symbol"] = signal.symbol;
  payload["signal_type"] = signal.signal_type;
  payload["signal"] = signal.signal_type;
  payload["signal_generated"] = generated;
  payload["signal_strength"] = signal.strength;
  payload["price"] = signal.price;
  payload["timestamp"] = signal.timestamp_iso;
  payload["signal_reason"] =
      !strategy_reason.empty()
          ? strategy_reason
          : (generated ? (signal.signal_type == "buy" ? "Order book imbalance favors upside"
                                                      : "Order book imbalance favors downside")
                       : "Signal below activity threshold");
  payload["data_status"] = generated ? "sufficient" : "insufficient";
  payload["spread"] = signal.spread;
  payload["volume"] = signal.volume;
  payload["buy_volume"] = signal_type == "buy" ? signal.volume * (0.55 + strength * 0.25) : signal.volume * 0.4;
  payload["sell_volume"] = signal_type == "sell" ? signal.volume * (0.55 + strength * 0.25) : signal.volume * 0.4;
  payload["imbalance_ratio"] = imbalance;
  payload["prediction"] = signal_type == "hold" ? "HOLD" : (signal_type == "buy" ? "BUY" : "SELL");

  Json::Value criteria(Json::objectValue);
  Json::Value squeeze(Json::objectValue);
  squeeze["enabled"] = true;
  squeeze["meets_criteria"] = generated && std::abs(imbalance) > 0.2;
  squeeze["delta_to_threshold"] = std::abs(imbalance) - 0.2;
  squeeze["threshold_spread"] = 0.0025;
  squeeze["analysis"] = generated ? "Spread and imbalance support a trade" : "Spread/imbalance below threshold";
  criteria["bid_ask_squeeze"] = squeeze;

  Json::Value imbalance_buy(Json::objectValue);
  imbalance_buy["enabled"] = true;
  imbalance_buy["meets_criteria"] = signal_type == "buy";
  imbalance_buy["delta_to_threshold"] = imbalance - 0.15;
  imbalance_buy["threshold"] = 0.15;
  imbalance_buy["analysis"] = signal_type == "buy" ? "Buy imbalance detected" : "No buy imbalance";
  criteria["volume_imbalance_buy"] = imbalance_buy;

  Json::Value imbalance_sell(Json::objectValue);
  imbalance_sell["enabled"] = true;
  imbalance_sell["meets_criteria"] = signal_type == "sell";
  imbalance_sell["delta_to_threshold"] = (-imbalance) - 0.15;
  imbalance_sell["threshold"] = 0.15;
  imbalance_sell["analysis"] = signal_type == "sell" ? "Sell imbalance detected" : "No sell imbalance";
  criteria["volume_imbalance_sell"] = imbalance_sell;

  // Real model inference drives ml_analysis whenever the ONNX pack is loaded;
  // the heuristic path only remains as an honestly-labeled fallback.
  Json::Value ml_analysis(Json::objectValue);
  bool used_model = false;
  if (strategy_ == "ml_enhanced_orderbook") {
    auto *engineer = api::PredictController::featureEngineer();
    auto *models = api::PredictController::modelManager();
    if (engineer != nullptr && models != nullptr && models->is_ready()) {
      try {
        ::ml::OrderBookFeatures features;
        features.timestamp = signal.timestamp;
        features.symbol = symbol;
        features.bid_ask_imbalance = imbalance;
        features.spread_percent = mid > 0.0 ? spread / mid : 0.0;
        features.mid_price = mid;
        features.bid_volume = signal.volume * (imbalance >= 0.0 ? 0.55 + strength * 0.25 : 0.4);
        features.ask_volume = signal.volume * (imbalance < 0.0 ? 0.55 + strength * 0.25 : 0.4);
        features.order_book_depth = signal.order_book_depth;
        features.large_bid_wall = false;
        features.large_ask_wall = false;
        features.wall_size = 0.0;
        features.volume_weighted_price = mid;
        features.price_momentum = state.last_return;
        features.volatility = std::abs(state.last_return);

        const auto pca_features = engineer->preprocess(features);
        const double win_prob =
            models->has_classifier() ? models->predict_win_prob(pca_features) : 0.5;
        const double expected_pnl =
            models->has_regressor() ? models->predict_pnl(pca_features) : 0.0;
        double transformer_pnl = 0.0;
        if (models->has_transformer()) {
          transformer_pnl = models->predict_transformer(engineer->get_transformer_sequence());
        }

        ml_analysis["ml_enabled"] = true;
        ml_analysis["win_probability"] = std::clamp(win_prob, 0.0, 1.0);
        ml_analysis["expected_return"] = expected_pnl;
        ml_analysis["transformer_expected_pnl"] = transformer_pnl;
        ml_analysis["confidence"] = std::clamp(std::abs(win_prob - 0.5) * 2.0, 0.0, 1.0);
        ml_analysis["model_version"] =
            CacheManager::getInstance().get("ml_active_model_id").value_or("onnx-pack");
        used_model = true;
      } catch (const std::exception &e) {
        TR_LOG_WARN("ML inference failed for {}; using heuristic fallback: {}", symbol, e.what());
      }
    }
  }

  if (!used_model) {
    ml_analysis["ml_enabled"] = strategy_ == "ml_enhanced_orderbook";
    ml_analysis["win_probability"] = std::clamp(0.5 + (generated ? (imbalance * 0.2) : 0.0), 0.0, 1.0);
    ml_analysis["expected_return"] = generated ? (imbalance * 0.012) : 0.0;
    ml_analysis["confidence"] = generated ? strength : 0.0;
    ml_analysis["model_version"] = "heuristic-fallback";
  }
  ml_analysis["features_used"] = Json::arrayValue;
  ml_analysis["features_used"].append("bid_ask_imbalance");
  ml_analysis["features_used"].append("spread_percent");
  ml_analysis["features_used"].append("momentum");
  ml_analysis["prediction_timestamp"] = signal.timestamp_iso;

  Json::Value composition(Json::objectValue);
  Json::Value comp_strength(Json::objectValue);
  comp_strength["value"] = std::abs(imbalance);
  comp_strength["importance_percent"] = 60.0;
  composition["order_book_imbalance"] = comp_strength;
  Json::Value comp_spread(Json::objectValue);
  comp_spread["value"] = signal.spread;
  comp_spread["importance_percent"] = 25.0;
  composition["spread"] = comp_spread;
  Json::Value comp_volume(Json::objectValue);
  comp_volume["value"] = signal.volume;
  comp_volume["importance_percent"] = 15.0;
  composition["volume"] = comp_volume;

  payload["criteria_analysis"] = criteria;
  payload["ml_analysis"] = ml_analysis;
  payload["strength_composition"] = composition;

  signal.payload = payload;
  return signal;
}

bool LiveTradingService::signalPassesMlGateLocked(const SignalRecord &signal) const {
  if (strategy_ != "ml_enhanced_orderbook") {
    return true;
  }

  const Json::Value ml_analysis =
      signal.payload.get("ml_analysis", Json::Value(Json::objectValue));
  const std::string model_version = ml_analysis.get("model_version", Json::Value("")).asString();
  if (model_version == "heuristic-fallback") {
    // Models unavailable: honor the fallback_to_baseline strategy parameter.
    const Json::Value fallback = parameters_.get("fallback_to_baseline", Json::Value(true));
    return fallback.isString() ? fallback.asString() != "false" : fallback.asBool();
  }

  const double threshold = std::clamp(
      parameters_.get("confidence_threshold", Json::Value(0.6)).asDouble(), 0.0, 1.0);
  const double win_probability =
      ml_analysis.get("win_probability", Json::Value(0.5)).asDouble();

  // win_probability is trained as the probability of a favorable (upward)
  // outcome, so buys need it high and sells need it correspondingly low.
  if (signal.signal_type == "buy") {
    return win_probability >= threshold;
  }
  if (signal.signal_type == "sell") {
    return win_probability <= 1.0 - threshold;
  }
  return false;
}

void LiveTradingService::trimHistoryLocked() {
  while (recent_trades_.size() > kMaxRecentTrades) {
    recent_trades_.pop_front();
  }
  while (recent_signals_.size() > kMaxRecentSignals) {
    recent_signals_.pop_front();
  }
}

void LiveTradingService::updateMarkToMarketLocked(
    const std::map<std::string, double> &prices) {
  // Stop-loss / take-profit thresholds in percent of entry notional; zero or
  // absent disables the rule.
  const double stop_loss = paramNumber(
      parameters_, "stop_loss_percent", paramNumber(parameters_, "stop_loss", 0.0));
  const double take_profit = paramNumber(
      parameters_, "take_profit_percent", paramNumber(parameters_, "take_profit", 0.0));

  std::vector<std::pair<std::string, const char *>> exits;
  for (auto &[symbol, position] : positions_) {
    const auto it = prices.find(symbol);
    if (it != prices.end()) {
      position.current_price = it->second;
    }
    const double direction = position.side == "buy" ? 1.0 : -1.0;
    position.unrealized_pnl = position.session_managed
                                  ? (position.current_price - position.managed_entry_price) *
                                        position.managed_quantity * direction
                                  : 0.0;
    position.pnl_percentage = position.session_managed && position.managed_entry_price > 0.0 &&
                                      position.managed_quantity > 0.0
                                  ? (position.unrealized_pnl /
                                     (position.managed_entry_price * position.managed_quantity)) * 100.0
                                  : 0.0;
    position.age_ticks += 1;

    if (position.session_managed) {
      if (const char *reason = exitReasonForPnl(position.pnl_percentage, stop_loss, take_profit)) {
      exits.emplace_back(symbol, reason);
      }
    }
  }

  for (const auto &[symbol, reason] : exits) {
    closePositionLocked(symbol, reason);
  }

  unrealized_pnl_ = 0.0;
  total_positions_value_ = 0.0;
  for (const auto &[symbol, position] : positions_) {
    unrealized_pnl_ += position.unrealized_pnl;
    total_positions_value_ +=
        signedPositionValue(position.side, position.quantity, position.current_price);
  }
}

void LiveTradingService::openPositionLocked(const SignalRecord &signal,
                                                 const std::string &reason) {
  if (positions_.find(signal.symbol) != positions_.end() ||
      pending_order_symbols_.count(signal.symbol) > 0) {
    return;
  }
  const std::size_t pending_entries = std::count_if(
      pending_order_symbols_.begin(), pending_order_symbols_.end(),
      [this](const std::string &symbol) {
        const auto it = positions_.find(symbol);
        return it == positions_.end() || !it->second.session_managed;
      });
  if (managedPositionCountLocked() + pending_entries >=
      static_cast<std::size_t>(max_positions_)) {
    return;
  }

  const double allocated_usd = positionSizeUsdForSignal(signal);
  if (allocated_usd <= 0.0 || signal.price <= 0.0) {
    return;
  }
  const double quantity = allocated_usd / signal.price;
  const double fee = signal.price * quantity * kFeeRate;
  const std::string side = sanitizeSide(signal.signal_type);
  if (side != "buy") {
    // Coinbase spot accounts cannot open synthetic shorts.
    return;
  }

  const double available_cash = std::max(0.0, cash_ - pending_reserved_cash_);
  if (!hasSufficientCash(side, available_cash, allocated_usd, fee)) {
    TR_LOG_DEBUG("Skipping {} entry for {}: insufficient cash ({} < {})", side, signal.symbol,
                 available_cash, allocated_usd + fee);
    return;
  }

  if (!liveOrderExecutionEnabledLocked()) {
    return;
  }
  OrderIntent intent;
  intent.product_id = signal.symbol;
  intent.side = side;
  intent.amount = allocated_usd;
  intent.amount_is_quote = true;
  intent.reason = reason;
  intent.action = "open";
  intent.signal = signal;
  intent.reserved_cash = allocated_usd + fee;
  queueOrderIntentLocked(std::move(intent));
}

// DCA accumulation: grow an existing position and average the entry price.
void LiveTradingService::addToPositionLocked(const SignalRecord &signal,
                                                  const std::string &reason) {
  if (pending_order_symbols_.count(signal.symbol) > 0) {
    return;
  }
  auto it = positions_.find(signal.symbol);
  if (it == positions_.end()) {
    openPositionLocked(signal, reason);
    return;
  }

  PositionState &position = it->second;
  const double allocated_usd = positionSizeUsdForSignal(signal);
  if (allocated_usd <= 0.0 || signal.price <= 0.0) {
    return;
  }
  const double quantity = allocated_usd / signal.price;
  const double fee = signal.price * quantity * kFeeRate;

  const double available_cash = std::max(0.0, cash_ - pending_reserved_cash_);
  if (!hasSufficientCash(position.side, available_cash, allocated_usd, fee)) {
    TR_LOG_DEBUG("Skipping DCA add for {}: insufficient cash ({} < {})", signal.symbol,
                 available_cash,
                 allocated_usd + fee);
    return;
  }

  if (!liveOrderExecutionEnabledLocked() || position.side != "buy") {
    return;
  }
  OrderIntent intent;
  intent.product_id = signal.symbol;
  intent.side = "buy";
  intent.amount = allocated_usd;
  intent.amount_is_quote = true;
  intent.reason = reason;
  intent.action = "add";
  intent.signal = signal;
  intent.position = position;
  intent.reserved_cash = allocated_usd + fee;
  queueOrderIntentLocked(std::move(intent));
}

Json::Value LiveTradingService::closePositionLocked(const std::string &symbol,
                                                         const std::string &reason) {
  Json::Value result(Json::objectValue);
  auto it = positions_.find(symbol);
  if (it == positions_.end()) {
    result["status"] = "error";
    result["error"] = "No open position for symbol";
    return result;
  }

  PositionState position = it->second;
  if (!position.session_managed) {
    result["status"] = "error";
    result["error"] = "Coinbase holding was not opened by this session";
    return result;
  }
  if (pending_order_symbols_.count(symbol) > 0) {
    result["status"] = "pending";
    result["message"] = "An exchange order is already pending for this symbol";
    return result;
  }
  if (!liveOrderExecutionEnabledLocked()) {
    result["status"] = "error";
    result["error"] = "Live order execution is disabled";
    return result;
  }
  OrderIntent intent;
  intent.product_id = symbol;
  intent.side = "sell";
  const auto available_it = account_available_quantities_.find(symbol);
  intent.amount = available_it == account_available_quantities_.end()
                      ? 0.0
                      : managedSellQuantity(position.quantity, position.managed_quantity,
                                            available_it->second);
  if (intent.amount <= 0.0) {
    result["status"] = "error";
    result["error"] = "Coinbase reports no available quantity to sell";
    return result;
  }
  intent.amount_is_quote = false;
  intent.reason = reason;
  intent.action = "close";
  intent.position = position;
  queueOrderIntentLocked(std::move(intent));
  result["status"] = "pending";
  result["message"] = "Position close submitted to Coinbase";
  result["symbol"] = symbol;
  return result;
}

void LiveTradingService::generateTickLocked(const std::map<std::string, MarketQuote> &quotes) {
  if (!active_) {
    return;
  }

  tick_ += 1;
  std::map<std::string, double> prices;

  for (std::size_t index = 0; index < symbols_.size(); ++index) {
    const std::string &symbol = symbols_[index];
    const MarketQuote *quote = nullptr;
    const auto quote_it = quotes.find(symbol);
    if (quote_it != quotes.end() && quote_it->second.valid) {
      quote = &quote_it->second;
    }
    // Live mode never trades on synthetic data: no quote, no tick action.
    if (quote == nullptr) {
      continue;
    }
    auto signal = buildSignalRecordLocked(symbol, index, *quote);
    prices[symbol] = signal.price;
    recent_signals_.push_back(signal);
    queueSignalWriteLocked(signal);

    auto position_it = positions_.find(symbol);
    const bool signal_generated = signal.signal_type != "hold";
    const std::size_t hold_ticks = std::max(3, position_update_interval_ * 2);

    if (position_it == positions_.end()) {
      if (signal_generated && static_cast<int>(managedPositionCountLocked()) < max_positions_ &&
          signalPassesMlGateLocked(signal)) {
        openPositionLocked(signal, "Opened on generated signal");
      }
      continue;
    }

    PositionState &position = position_it->second;
    position.current_price = signal.price;

    if (!position.session_managed) {
      // Existing Coinbase holdings are visible but never auto-liquidated by a
      // session that did not open them.
      continue;
    }

    // Accumulation strategies never auto-close: buy-and-hold keeps its
    // position for the session, DCA adds on each scheduled buy signal.
    if (strategy_ == "buyandhold") {
      continue;
    }
    if (strategy_ == "dca") {
      if (signal_generated && signal.signal_type == "buy") {
        addToPositionLocked(signal, "DCA scheduled purchase");
      }
      continue;
    }

    const bool opposite_signal = signal_generated && sanitizeSide(signal.signal_type) != position.side;
    const bool age_out = position.age_ticks >= static_cast<std::size_t>(hold_ticks);

    if (opposite_signal || age_out) {
      closePositionLocked(symbol, opposite_signal ? "Closed on opposite signal" : "Closed after holding period");
      if (signal_generated && static_cast<int>(managedPositionCountLocked()) < max_positions_ &&
          signalPassesMlGateLocked(signal)) {
        openPositionLocked(signal, "Re-opened after close");
      }
    }
  }

  updateMarkToMarketLocked(prices);
  // Cash is maintained transactionally by open/close deltas; recomputing it
  // here from realized PnL would erase the debits for still-open positions.
  updated_at_ = nowIsoUtc();
  trimHistoryLocked();
}

void LiveTradingService::workerLoop() {
  TR_LOG_INFO("Live trading worker started for session {}", session_id_);
  while (true) {
    try {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (shutdown_requested_) {
          break;
        }
      }
      // Accepted orders remain pending until Coinbase reports a terminal fill;
      // never invent a zero fee or abandon an exchange order on session stop.
      resolvePendingLiveOrders();
      PendingWrites settled_writes;
      {
        std::lock_guard<std::mutex> lock(mutex_);
        settled_writes = takePendingWritesLocked();
      }
      flushWrites(std::move(settled_writes));
      // Live market data is fetched over HTTPS before taking the mutex so API
      // handlers never wait behind network I/O.
      std::vector<std::string> symbols_snapshot;
      bool settling = false;
      {
        std::lock_guard<std::mutex> lock(mutex_);
        const bool writes_pending =
            !pending_signal_writes_.empty() || !pending_trade_writes_.empty();
        if (shutdown_requested_ ||
            (stop_requested_ && pending_order_symbols_.empty() &&
             pending_live_orders_.empty() && !writes_pending)) {
          break;
        }
        if (stop_requested_) {
          settling = true;
        } else {
          symbols_snapshot = symbols_;

        }
      }
      if (settling) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        continue;
      }

      std::map<std::string, MarketQuote> quotes;
      CoinbasePortfolioSnapshot account_snapshot;
      bool account_snapshot_loaded = false;
      quotes = fetchLiveQuotes(symbols_snapshot);
      std::string account_error;
      account_snapshot_loaded = fetchLiveAccountSnapshot(account_snapshot, &account_error);
      if (!account_snapshot_loaded) {
        TR_LOG_WARN("Unable to refresh Coinbase account state: {}", account_error);
      }

      PendingWrites writes;
      std::vector<OrderIntent> orders;
      bool stop_after_quotes = false;
      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (stop_requested_) {
          stop_after_quotes = true;
        } else {
          if (account_snapshot_loaded) {
            applyLiveAccountSnapshotLocked(account_snapshot, false);
          }
          generateTickLocked(quotes);
          writes = takePendingWritesLocked();
          orders = takePendingOrdersLocked();
        }
      }
      if (stop_after_quotes) {
        continue;
      }
      // Database I/O and exchange orders happen outside the mutex so API
      // handlers never block behind tick persistence.
      dispatchOrders(std::move(orders));
      flushWrites(std::move(writes));
    } catch (const std::exception &e) {
      TR_LOG_ERROR("Live trading worker tick failed for session {}: {}", session_id_, e.what());
    } catch (...) {
      TR_LOG_ERROR("Live trading worker tick failed for session {}: unknown exception", session_id_);
    }

    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  {
    std::lock_guard<std::mutex> lock(mutex_);
    active_ = false;
    stop_requested_ = false;
    updated_at_ = nowIsoUtc();
  }
  for (int attempt = 0; attempt < 3; ++attempt) {
    PendingWrites final_writes;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      final_writes = takePendingWritesLocked();
    }
    if (final_writes.signals.empty() && final_writes.trades.empty()) {
      break;
    }
    flushWrites(std::move(final_writes));
    if (attempt < 2) {
      std::this_thread::sleep_for(std::chrono::milliseconds(250 * (attempt + 1)));
    }
  }
  {
    std::lock_guard<std::mutex> lock(mutex_);
    worker_finished_ = true;
  }
  TR_LOG_INFO("Live trading worker stopped for session {}", session_id_);
}

void LiveTradingService::startWorkerLocked() {
  stop_requested_ = false;
  shutdown_requested_ = false;
  worker_finished_ = false;
  worker_ = std::thread([this]() { workerLoop(); });
}

Json::Value LiveTradingService::buildPortfolioJson() const {
  Json::Value portfolio(Json::objectValue);
  portfolio["is_active"] = active_;
  portfolio["is_trading"] = active_;
  portfolio["status"] = active_ ? "active" : "stopped";
  portfolio["session_id"] = session_id_;
  portfolio["mode"] = "live";
  portfolio["strategy_type"] = strategy_;
  portfolio["started_at"] = started_at_;
  portfolio["updated_at"] = updated_at_;
  portfolio["symbols"] = Json::arrayValue;
  for (const auto &symbol : symbols_) {
    portfolio["symbols"].append(symbol);
  }
  Json::Value positions(Json::objectValue);
  double directional_positions_value = 0.0;
  double absolute_positions_value = 0.0;
  for (const auto &[symbol, position] : positions_) {
    positions[symbol] = positionToJson(position);
    const double market_value =
        signedPositionValue(position.side, position.quantity, position.current_price);
    absolute_positions_value += std::abs(market_value);
    directional_positions_value += market_value;
  }
  const double total_value = cash_ + cash_hold_ + directional_positions_value;
  const double available_cash = std::max(0.0, cash_ - pending_reserved_cash_);

  portfolio["cash_balance"] = cash_;
  portfolio["cash_hold"] = cash_hold_;
  portfolio["available_balance_usd"] = available_cash;
  portfolio["pending_reserved_cash"] = pending_reserved_cash_;
  portfolio["pending_order_count"] = static_cast<Json::UInt64>(pending_order_symbols_.size());
  portfolio["total_balance_usd"] = total_value;
  portfolio["current_capital"] = total_value;
  portfolio["total_value"] = total_value;
  portfolio["initial_capital"] = initial_capital_;
  // Signed so that total_value == cash_balance + total_positions_value holds
  // with shorts; the absolute exposure is reported separately.
  portfolio["total_positions_value"] = directional_positions_value;
  portfolio["total_positions_exposure"] = absolute_positions_value;
  portfolio["unrealized_pnl"] = unrealized_pnl_;
  portfolio["realized_pnl"] = realized_pnl_;
  portfolio["net_pnl"] = total_value - initial_capital_;
  portfolio["total_fees"] = total_fees_;
  portfolio["open_positions_count"] = static_cast<int>(positions_.size());
  portfolio["tick"] = static_cast<Json::Int64>(tick_);
  portfolio["positions"] = positions;

  Json::Value recent_trades(Json::arrayValue);
  for (const auto &trade : recent_trades_) {
    recent_trades.append(tradeToJson(trade));
  }
  portfolio["recent_trades"] = recent_trades;
  portfolio["trades"] = recent_trades;

  Json::Value recent_signals(Json::arrayValue);
  for (const auto &signal : recent_signals_) {
    recent_signals.append(signalToJson(signal));
  }
  portfolio["recent_signals"] = recent_signals;

  return portfolio;
}

Json::Value LiveTradingService::buildStatusJson() const {
  Json::Value status = buildPortfolioJson();
  status["isActive"] = active_;
  status["is_active"] = active_;
  status["is_trading"] = active_;
  status["mode"] = "live";
  status["strategy_type"] = strategy_;
  status["session_id"] = session_id_;
  status["symbols"] = Json::arrayValue;
  for (const auto &symbol : symbols_) {
    status["symbols"].append(symbol);
  }

  // Persisted session rows are authoritative and include fills recovered after
  // restart. Fall back to in-memory rows only while persistence is unavailable.
  std::vector<TradePerformanceInput> trades;
  const std::string today = formatNowIsoUtc().substr(0, 10);

  try {
    if (!session_id_.empty()) {
      auto exists = DatabaseManager::getInstance().query(
          "SELECT to_regclass('public.individual_trades') AS relname");
      if (!exists.empty() && !exists[0]["relname"].is_null()) {
        std::ostringstream sql;
        sql << "SELECT size, price, timestamp, pnl, fees "
            << "FROM individual_trades WHERE session_id='" << escapeSql(session_id_)
            << "' ORDER BY timestamp ASC";
        auto rows = DatabaseManager::getInstance().query(sql.str());
        trades.reserve(rows.size());
        for (const auto &row : rows) {
          trades.push_back(toTradePerformanceInput(row));
        }
      }
    }
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to load persisted live trade stats for session {}: {}", session_id_, e.what());
  }

  if (trades.empty()) {
    trades = session_trade_inputs_;
  }

  const TradingStats summary = calculateTradingStats(trades, today);
  Json::Value stats_json(Json::objectValue);
  stats_json["total_pnl"] = summary.total_pnl;
  stats_json["total_fees"] = summary.total_fees;
  stats_json["net_pnl"] = summary.net_pnl;
  stats_json["win_rate"] = summary.win_rate;
  stats_json["total_trades"] = summary.total_trades;
  stats_json["winning_trades"] = summary.winning_trades;
  stats_json["losing_trades"] = summary.losing_trades;
  stats_json["avg_win"] = summary.avg_win;
  stats_json["avg_loss"] = summary.avg_loss;
  stats_json["best_trade"] = summary.best_trade;
  stats_json["worst_trade"] = summary.worst_trade;
  stats_json["profit_factor"] = summary.profit_factor;
  stats_json["sharpe_ratio"] = summary.sharpe_ratio;
  stats_json["max_drawdown"] = summary.max_drawdown;
  stats_json["total_volume"] = summary.total_volume;
  stats_json["avg_trade_size"] = summary.avg_trade_size;
  stats_json["trades_today"] = summary.trades_today;
  stats_json["last_trade_time"] = summary.last_trade_time;

  status["stats"] = stats_json;
  return status;
}

Json::Value LiveTradingService::startSession(const Json::Value &payload) {
  std::lock_guard<std::mutex> lifecycle_lock(lifecycle_mutex_);
  std::unique_lock<std::mutex> lock(mutex_);
  ensureSchema();

  if (active_) {
    Json::Value resp = buildStatusJson();
    resp["message"] = "Trading session already running";
    return resp;
  }

  if (worker_.joinable()) {
    if (!worker_finished_) {
      Json::Value resp = buildStatusJson();
      resp["status"] = "settling";
      resp["error"] = "The previous session is still settling orders or persistence writes";
      return resp;
    }
    lock.unlock();
    worker_.join();
    lock.lock();
  }

  session_id_ = payload.isMember("session_id") ? payload["session_id"].asString() : makeSessionId();
  CoinbasePortfolioSnapshot live_account_snapshot;
  auto &cfg = Config::getInstance();
  exchange::CoinbaseCredentials credentials;
  credentials.api_key = cfg.get("COINBASE_API_KEY", "");
  credentials.api_secret = cfg.get("COINBASE_API_SECRET", "");
  exchange_client_ =
      std::make_unique<exchange::CoinbaseAdvancedClient>(std::move(credentials));
  std::string account_error;
  lock.unlock();
  const bool account_loaded = fetchLiveAccountSnapshot(live_account_snapshot, &account_error);
  lock.lock();
  if (!account_loaded) {
    exchange_client_.reset();
    Json::Value resp;
    resp["status"] = "error";
    resp["error"] = "Unable to initialize live trading from Coinbase: " + account_error;
    resp["is_active"] = false;
    return resp;
  }
  strategy_ = payload.isMember("strategy") ? payload["strategy"].asString() : "orderbook";
  symbols_.clear();
  if (payload.isMember("symbols") && payload["symbols"].isArray()) {
    for (const auto &symbol : payload["symbols"]) {
      if (symbol.isString()) {
        symbols_.push_back(symbol.asString());
      }
    }
  }
  if (symbols_.empty()) {
    symbols_ = defaultSymbols();
  }

  // Canonical key is `parameters`; older frontends sent the same object as
  // `strategy_params`, so accept that alias too.
  if (payload.isMember("parameters") && payload["parameters"].isObject()) {
    parameters_ = payload["parameters"];
  } else if (payload.isMember("strategy_params") && payload["strategy_params"].isObject()) {
    parameters_ = payload["strategy_params"];
  } else {
    parameters_ = Json::Value(Json::objectValue);
  }
  for (const char *forbidden : {"initial_portfolio_size", "initial_balance", "capital"}) {
    if (parameters_.isMember(forbidden) || payload.isMember(forbidden)) {
      exchange_client_.reset();
      Json::Value resp;
      resp["status"] = "error";
      resp["error"] = "Synthetic capital parameters are not valid for live trading";
      resp["is_active"] = false;
      return resp;
    }
  }

  // Top-level settings override/backfill the parameters object.
  for (const char *key : {"position_size_percent", "max_positions",
                          "position_update_interval", "confidence_threshold",
                          "fallback_to_baseline", "stop_loss", "take_profit"}) {
    if (payload.isMember(key) && !payload[key].isNull()) {
      parameters_[key] = payload[key];
    }
  }
  const Json::Value live_execution =
      parameters_.get("live_order_execution", payload.get("live_order_execution", false));
  const bool live_execution_confirmed = live_execution.isString()
                                            ? live_execution.asString() == "true"
                                            : live_execution.asBool();
  if (!live_execution_confirmed) {
    exchange_client_.reset();
    Json::Value resp;
    resp["status"] = "error";
    resp["error"] = "Live order execution must be explicitly confirmed";
    resp["is_active"] = false;
    return resp;
  }
  parameters_["live_order_execution"] = true;

  max_positions_ = payload.isMember("max_positions")
                       ? payload["max_positions"].asInt()
                       : (parameters_.isMember("max_positions_per_session")
                              ? parameters_["max_positions_per_session"].asInt()
                              : 100);
  max_positions_ = std::max(1, max_positions_);
  position_update_interval_ = payload.isMember("position_update_interval")
                                  ? payload["position_update_interval"].asInt()
                                  : (parameters_.isMember("position_update_interval")
                                         ? parameters_["position_update_interval"].asInt()
                                         : 5);
  position_update_interval_ = std::max(1, position_update_interval_);

  realized_pnl_ = 0.0;
  unrealized_pnl_ = 0.0;
  total_fees_ = 0.0;
  total_positions_value_ = 0.0;
  positions_.clear();
  market_state_.clear();
  recent_trades_.clear();
  recent_signals_.clear();
  session_trade_inputs_.clear();
  pending_orders_.clear();
  pending_live_orders_.clear();
  pending_order_symbols_.clear();
  account_available_quantities_.clear();
  managed_quantity_floors_.clear();
  pending_reserved_cash_ = 0.0;
  applyLiveAccountSnapshotLocked(live_account_snapshot, true);
  if (!recoverPendingOrders()) {
    exchange_client_.reset();
    Json::Value resp;
    resp["status"] = "error";
    resp["error"] = "Unable to recover pending Coinbase orders";
    resp["is_active"] = false;
    return resp;
  }
  tick_ = 0;
  started_at_ = nowIsoUtc();
  updated_at_ = started_at_;
  start_epoch_seconds_ = nowEpochSeconds();
  active_ = true;
  stop_requested_ = false;

  startWorkerLocked();

  Json::Value resp = buildStatusJson();
  resp["status"] = "started";
  resp["is_active"] = true;
  resp["is_trading"] = true;
  resp["message"] = "Live trading started from Coinbase account state";
  return resp;
}

Json::Value LiveTradingService::stopSession() {
  std::lock_guard<std::mutex> lifecycle_lock(lifecycle_mutex_);
  std::lock_guard<std::mutex> lock(mutex_);
  if (!active_ && !worker_.joinable()) {
    Json::Value resp = buildStatusJson();
    resp["message"] = "Live trading already stopped";
    return resp;
  }
  stop_requested_ = true;
  active_ = false;
  for (const auto &intent : pending_orders_) {
    pending_order_symbols_.erase(intent.product_id);
    pending_reserved_cash_ =
        std::max(0.0, pending_reserved_cash_ - intent.reserved_cash);
  }
  pending_orders_.clear();
  updated_at_ = nowIsoUtc();
  Json::Value resp = buildStatusJson();
  const bool settling = !pending_live_orders_.empty();
  resp["status"] = settling ? "settling" : "success";
  resp["is_active"] = false;
  resp["is_trading"] = false;
  resp["message"] = settling ? "Trading stopped; accepted Coinbase orders are still settling"
                              : "Live trading stopped";
  return resp;
}

Json::Value LiveTradingService::getStatus(const std::string &session_id) {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value resp = buildStatusJson();
  if (!session_id.empty()) {
    resp["requested_session_id"] = session_id;
  }
  return resp;
}

Json::Value LiveTradingService::updateStrategyParameters(const Json::Value &payload) {
  std::lock_guard<std::mutex> lock(mutex_);

  Json::Value params = payload.isMember("parameters") && payload["parameters"].isObject()
                           ? payload["parameters"]
                           : payload;
  if (!params.isObject()) {
    Json::Value resp;
    resp["status"] = "error";
    resp["error"] = "parameters object is required";
    return resp;
  }

  const Json::Value::Members members = params.getMemberNames();
  for (const char *forbidden : {"initial_portfolio_size", "initial_balance", "capital"}) {
    if (params.isMember(forbidden)) {
      Json::Value resp;
      resp["status"] = "error";
      resp["error"] = "Synthetic capital parameters are not valid for live trading";
      return resp;
    }
  }
  for (const auto &member : members) {
    parameters_[member] = params[member];
  }

  if (parameters_.isMember("max_positions_per_session")) {
    max_positions_ = std::max(1, parameters_["max_positions_per_session"].asInt());
  }
  if (parameters_.isMember("max_positions")) {
    max_positions_ = std::max(1, parameters_["max_positions"].asInt());
  }
  if (parameters_.isMember("position_update_interval")) {
    position_update_interval_ = std::max(1, parameters_["position_update_interval"].asInt());
  }

  Json::Value resp;
  resp["status"] = "success";
  resp["message"] = "Strategy parameters updated";
  resp["parameters"] = parameters_;
  resp["max_positions"] = max_positions_;
  resp["position_update_interval"] = position_update_interval_;
  return resp;
}

Json::Value LiveTradingService::getOpenPositions() {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value positions(Json::arrayValue);
  for (const auto &[symbol, position] : positions_) {
    positions.append(positionToJson(position));
  }
  return positions;
}

Json::Value LiveTradingService::getLivePortfolioStatus() {
  std::lock_guard<std::mutex> lock(mutex_);
  return buildStatusJson();
}

Json::Value LiveTradingService::refreshLivePortfolioStatus() {
  std::lock_guard<std::mutex> lifecycle_lock(lifecycle_mutex_);
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!exchange_client_) {
      auto &cfg = Config::getInstance();
      exchange::CoinbaseCredentials credentials;
      credentials.api_key = cfg.get("COINBASE_API_KEY", "");
      credentials.api_secret = cfg.get("COINBASE_API_SECRET", "");
      exchange_client_ =
          std::make_unique<exchange::CoinbaseAdvancedClient>(std::move(credentials));
    }
  }
  CoinbasePortfolioSnapshot snapshot;
  std::string error;
  if (!fetchLiveAccountSnapshot(snapshot, &error)) {
    Json::Value result;
    result["status"] = "error";
    result["error"] = "Unable to refresh Coinbase portfolio: " + error;
    return result;
  }
  std::lock_guard<std::mutex> lock(mutex_);
  applyLiveAccountSnapshotLocked(snapshot, !active_);
  Json::Value result = buildStatusJson();
  result["source"] = "coinbase";
  return result;
}

Json::Value LiveTradingService::submitLiveOrder(const Json::Value &payload) {
  std::lock_guard<std::mutex> lifecycle_lock(lifecycle_mutex_);
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value result;
  if (!active_ || worker_finished_) {
    result["status"] = "error";
    result["error"] = "An active live session is required";
    return result;
  }
  if (!liveOrderExecutionEnabledLocked()) {
    result["status"] = "error";
    result["error"] = "Live order execution is disabled";
    return result;
  }
  const std::string symbol = payload.get("symbol", "").asString();
  const std::string requested_side = payload.get("side", "").asString();
  const std::string side = sanitizeSide(requested_side);
  const std::string amount_type = payload.get("amount_type", "").asString();
  const double amount = payload.get("amount", 0.0).asDouble();
  if (symbol.empty() || (requested_side != "buy" && requested_side != "sell") ||
      !std::isfinite(amount) ||
      amount <= 0.0) {
    result["status"] = "error";
    result["error"] = "symbol, buy/sell side, and a positive finite amount are required";
    return result;
  }
  if (pending_order_symbols_.count(symbol) > 0) {
    result["status"] = "pending";
    result["message"] = "An exchange order is already pending for this symbol";
    return result;
  }

  OrderIntent intent;
  intent.product_id = symbol;
  intent.side = side;
  intent.amount = amount;
  intent.reason = "manual_live_order";
  if (side == "buy") {
    if (amount_type != "quote") {
      result["status"] = "error";
      result["error"] = "Live buy amount_type must be quote";
      return result;
    }
    const double estimated_fee = amount * kFeeRate;
    if (!hasSufficientCash("buy", std::max(0.0, cash_ - pending_reserved_cash_), amount,
                           estimated_fee)) {
      result["status"] = "error";
      result["error"] = "Insufficient Coinbase spendable cash";
      return result;
    }
    intent.amount_is_quote = true;
    intent.reserved_cash = amount + estimated_fee;
    intent.action = positions_.count(symbol) > 0 ? "add" : "open";
    intent.signal.symbol = symbol;
    intent.signal.signal_type = "buy";
    intent.signal.timestamp = nowEpochSeconds();
    intent.signal.timestamp_iso = nowIsoUtc();
  } else {
    if (amount_type != "base") {
      result["status"] = "error";
      result["error"] = "Live sell amount_type must be base";
      return result;
    }
    const auto available_it = account_available_quantities_.find(symbol);
    if (available_it == account_available_quantities_.end() || amount > available_it->second) {
      result["status"] = "error";
      result["error"] = "Sell amount exceeds Coinbase available holdings";
      return result;
    }
    const auto position_it = positions_.find(symbol);
    if (position_it == positions_.end()) {
      result["status"] = "error";
      result["error"] = "No Coinbase holding exists for this symbol";
      return result;
    }
    intent.amount_is_quote = false;
    intent.action = "close";
    intent.position = position_it->second;
  }
  queueOrderIntentLocked(std::move(intent));
  result["status"] = "pending";
  result["message"] = "Order queued for Coinbase submission";
  result["symbol"] = symbol;
  result["side"] = side;
  return result;
}

Json::Value LiveTradingService::getOrderBookSignals(const std::vector<std::string> &symbols,
                                                         int page,
                                                         int per_page) {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value result;
  result["signals"] = Json::arrayValue;
  result["total_analyzed"] = 0;
  result["active_signals"] = 0;
  result["average_strength"] = 0.0;
  result["last_updated"] = "";
  result["pagination"]["page"] = std::max(1, page);
  result["pagination"]["per_page"] = std::max(1, per_page);
  result["pagination"]["total_signals"] = 0;
  result["pagination"]["total_pages"] = 0;
  result["pagination"]["has_next"] = false;
  result["pagination"]["has_prev"] = false;

  try {
    if (active_ || !recent_signals_.empty()) {
      std::map<std::string, SignalRecord> latest_by_symbol;
      for (const auto &signal : recent_signals_) {
        if (!symbols.empty() && std::find(symbols.begin(), symbols.end(), signal.symbol) == symbols.end()) {
          continue;
        }

        auto it = latest_by_symbol.find(signal.symbol);
        if (it == latest_by_symbol.end() || signal.timestamp > it->second.timestamp) {
          latest_by_symbol[signal.symbol] = signal;
        }
      }

      std::vector<SignalRecord> filtered;
      filtered.reserve(latest_by_symbol.size());
      for (const auto &entry : latest_by_symbol) {
        filtered.push_back(entry.second);
      }

      std::sort(filtered.begin(), filtered.end(), [](const SignalRecord &left, const SignalRecord &right) {
        if (left.strength != right.strength) {
          return left.strength > right.strength;
        }
        if (left.timestamp != right.timestamp) {
          return left.timestamp > right.timestamp;
        }
        return left.symbol < right.symbol;
      });

      const int total = static_cast<int>(filtered.size());
      const int safe_page = std::max(1, page);
      const int safe_per_page = std::max(1, per_page);
      const int offset = (safe_page - 1) * safe_per_page;
      const int total_pages = safe_per_page > 0 ? static_cast<int>(std::ceil(static_cast<double>(total) / safe_per_page)) : 0;

      result["pagination"]["page"] = safe_page;
      result["pagination"]["per_page"] = safe_per_page;
      result["pagination"]["total_signals"] = total;
      result["pagination"]["total_pages"] = total_pages;
      result["pagination"]["has_next"] = safe_page < total_pages;
      result["pagination"]["has_prev"] = safe_page > 1;

      double strength_sum = 0.0;
      int active_count = 0;
      long long latest_ts = 0;

      for (int i = offset; i < std::min(offset + safe_per_page, total); ++i) {
        const auto &signal = filtered[static_cast<std::size_t>(i)];
        Json::Value signal_json = signalToJson(signal);
        result["signals"].append(signal_json);
        strength_sum += signal_json["signal_strength"].asDouble();
        if (signal_json["signal_generated"].asBool()) {
          ++active_count;
        }
        latest_ts = std::max(latest_ts, signal.timestamp);
      }

      result["total_analyzed"] = total;
      result["active_signals"] = active_count;
      result["average_strength"] = result["signals"].size() > 0 ? strength_sum / static_cast<double>(result["signals"].size()) : 0.0;
      if (latest_ts > 0) {
        result["last_updated"] = epochSecondsToIso(latest_ts);
      }
      return result;
    }

    auto exists = DatabaseManager::getInstance().query(
        "SELECT to_regclass('public.order_book_signals') AS relname");
    if (exists.empty() || exists[0]["relname"].is_null()) {
      return result;
    }

    // Symbols arrive from the request; bind them as parameters, never inline.
    std::ostringstream where;
    std::vector<std::string> bound_symbols;
    if (!symbols.empty()) {
      where << " WHERE symbol IN (";
      for (std::size_t i = 0; i < symbols.size(); ++i) {
        bound_symbols.push_back(symbols[i]);
        if (i > 0) {
          where << ",";
        }
        where << "$" << bound_symbols.size();
      }
      where << ")";
    }

    auto count_res = DatabaseManager::getInstance().execParams(
        "SELECT COUNT(DISTINCT symbol) AS total_count FROM order_book_signals" + where.str(),
        bound_symbols);
    const int total = (!count_res.empty() && !count_res[0]["total_count"].is_null())
                          ? count_res[0]["total_count"].as<int>()
                          : 0;

    const int safe_page = std::max(1, page);
    const int safe_per_page = std::max(1, per_page);
    const int offset = (safe_page - 1) * safe_per_page;
    const int total_pages = safe_per_page > 0 ? static_cast<int>(std::ceil(static_cast<double>(total) / safe_per_page)) : 0;

    std::ostringstream sql;
    sql << "WITH latest_signals AS ("
        << "SELECT DISTINCT ON (symbol) signal_id, session_id, symbol, signal_type, strength, price, timestamp, signal_data, "
        << "spread, imbalance, mid_price, best_bid, best_ask, order_book_depth, volume, total_signals "
        << "FROM order_book_signals" << where.str() << " ORDER BY symbol, timestamp DESC) "
        << "SELECT signal_id, session_id, symbol, signal_type, strength, price, timestamp, signal_data, "
        << "spread, imbalance, mid_price, best_bid, best_ask, order_book_depth, volume, total_signals "
        << "FROM latest_signals "
        << "ORDER BY strength DESC, COALESCE((signal_data::jsonb -> 'ml_analysis' ->> 'win_probability')::double precision, 0.5) DESC, timestamp DESC "
        << "LIMIT " << safe_per_page << " OFFSET " << offset;

    auto rows = DatabaseManager::getInstance().execParams(sql.str(), bound_symbols);
    double strength_sum = 0.0;
    int active_count = 0;
    long long latest_ts = 0;

    for (const auto &row : rows) {
      Json::Value signal = parseJsonString(row["signal_data"].is_null() ? "" : row["signal_data"].c_str());
      if (!signal.isObject()) {
        signal = Json::Value(Json::objectValue);
      }
      signal["signal_id"] = row["signal_id"].is_null() ? "" : row["signal_id"].c_str();
      signal["session_id"] = row["session_id"].is_null() ? "" : row["session_id"].c_str();
      signal["symbol"] = row["symbol"].is_null() ? "" : row["symbol"].c_str();
      signal["signal_type"] = row["signal_type"].is_null() ? "hold" : row["signal_type"].c_str();
      signal["signal"] = signal["signal_type"];
      signal["signal_generated"] = signal["signal_type"].asString() != "hold";
      signal["signal_strength"] = row["strength"].is_null() ? 0.0 : std::stod(row["strength"].c_str());
      signal["strength"] = signal["signal_strength"];
      signal["price"] = row["price"].is_null() ? 0.0 : std::stod(row["price"].c_str());
      signal["timestamp"] = row["timestamp"].is_null() ? "" : epochSecondsToIso(row["timestamp"].as<long long>());
      signal["data_status"] = signal["signal_generated"].asBool() ? "sufficient" : "insufficient";
      signal["spread"] = row["spread"].is_null() ? 0.0 : std::stod(row["spread"].c_str());
      signal["volume"] = row["volume"].is_null() ? 0.0 : std::stod(row["volume"].c_str());
      signal["active_signals"] = signal["signal_generated"].asBool() ? 1 : 0;
      result["signals"].append(signal);

      strength_sum += signal["signal_strength"].asDouble();
      if (signal["signal_generated"].asBool()) {
        active_count += 1;
      }
      if (!row["timestamp"].is_null()) {
        latest_ts = std::max(latest_ts, row["timestamp"].as<long long>());
      }
    }

    result["total_analyzed"] = total;
    result["active_signals"] = active_count;
    result["average_strength"] = rows.empty() ? 0.0 : strength_sum / static_cast<double>(rows.size());
    if (latest_ts > 0) {
      result["last_updated"] = epochSecondsToIso(latest_ts);
    }
    result["pagination"]["page"] = safe_page;
    result["pagination"]["per_page"] = safe_per_page;
    result["pagination"]["total_signals"] = total;
    result["pagination"]["total_pages"] = total_pages;
    result["pagination"]["has_next"] = safe_page < total_pages;
    result["pagination"]["has_prev"] = safe_page > 1;
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to fetch order book signals: {}", e.what());
  }

  return result;
}

Json::Value LiveTradingService::closePosition(const std::string &symbol) {
  Json::Value result;
  PendingWrites writes;
  std::vector<OrderIntent> orders;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!active_) {
      result["status"] = "error";
      result["error"] = "Trading session is not active";
      return result;
    }
    result = closePositionLocked(symbol, "Manual close request");
    writes = takePendingWritesLocked();
    orders = takePendingOrdersLocked();
  }
  flushWrites(std::move(writes));
  const bool created_close_intent = !orders.empty();
  const OrderDispatchResult dispatch_result = dispatchOrders(std::move(orders));
  if (created_close_intent && result.get("status", Json::Value("")).asString() == "pending" &&
      !dispatch_result.accepted) {
    result["status"] = "error";
    result["error"] = dispatch_result.attempted
                          ? dispatch_result.error
                          : "Position close was not submitted because trading stopped";
    result["message"] = result["error"];
  }
  {
    std::lock_guard<std::mutex> lock(mutex_);
    writes = takePendingWritesLocked();
  }
  flushWrites(std::move(writes));
  return result;
}

} // namespace trading
} // namespace trade
