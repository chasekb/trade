#include "trading/SimulatedTradingService.hpp"

#include "db/DatabaseManager.hpp"
#include "trading/TradingStatsService.hpp"
#include "trading/PositionSizingPolicy.hpp"
#include "ml/Metrics.hpp"
#include "cache/CacheManager.hpp"
#include "utils/Logger.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cctype>
#include <functional>
#include <iomanip>
#include <limits>
#include <memory>
#include <random>
#include <sstream>
#include <ctime>

namespace trade {
namespace trading {

namespace {
constexpr double kFeeRate = 0.0005;
constexpr std::size_t kMaxRecentTrades = 100;
constexpr std::size_t kMaxRecentSignals = 250;
constexpr double kDefaultInitialCapital = 10000.0;

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
  return "sim_" + std::to_string(currentEpochSeconds());
}

std::string sanitizeSide(const std::string &side) {
  if (side == "sell") {
    return "sell";
  }
  return "buy";
}

} // namespace

SimulatedTradingService &SimulatedTradingService::getInstance() {
  static SimulatedTradingService instance;
  return instance;
}

SimulatedTradingService::~SimulatedTradingService() {
  stopSession();
}

std::string SimulatedTradingService::escapeSql(const std::string &value) const {
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

std::string SimulatedTradingService::jsonToString(const Json::Value &value) const {
  Json::StreamWriterBuilder builder;
  builder["indentation"] = "";
  builder["precision"] = 17;
  return Json::writeString(builder, value);
}

std::string SimulatedTradingService::nowIsoUtc() const { return formatNowIsoUtc(); }

long long SimulatedTradingService::nowEpochSeconds() const { return currentEpochSeconds(); }

std::string SimulatedTradingService::makeId(const std::string &prefix, long long ts,
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

void SimulatedTradingService::ensureSchema() {
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
        trade_type TEXT DEFAULT 'simulated'
      )
    )SQL");
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to ensure simulated trading schema: {}", e.what());
  }
}

double SimulatedTradingService::basePriceForSymbol(const std::string &symbol) const {
  if (symbol == "BTC-USD") {
    return 65000.0;
  }
  if (symbol == "ETH-USD") {
    return 3500.0;
  }
  if (symbol == "SOL-USD") {
    return 150.0;
  }
  if (symbol == "AVAX-USD") {
    return 40.0;
  }
  if (symbol == "XRP-USD") {
    return 0.55;
  }
  if (symbol == "DOGE-USD") {
    return 0.12;
  }
  if (symbol == "ADA-USD") {
    return 0.42;
  }
  return 100.0 + (static_cast<double>(std::hash<std::string>{}(symbol) % 5000) / 10.0);
}

double SimulatedTradingService::positionSizeUsdForSignal(const SignalRecord &signal) const {
  const double pct = parameters_.isMember("position_size_percent")
                         ? parameters_["position_size_percent"].asDouble()
                         : 1.0;
  const std::string size_mode = parameters_.isMember("position_size_mode")
                                    ? parameters_["position_size_mode"].asString()
                                    : "percent";
  const double position_value = parameters_.isMember("position_size_value")
                                    ? parameters_["position_size_value"].asDouble()
                                    : 1.0;

  const double capital = initial_capital_ > 0.0 ? initial_capital_ : kDefaultInitialCapital;
  PositionSizingInputs inputs;
  inputs.base_usd = size_mode == "dollar" ? std::max(25.0, position_value)
                                            : capital * std::max(0.01, pct) / 100.0;
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

  const auto live_stats = TradingStatsService::getInstance().getTradingStats();
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

Json::Value SimulatedTradingService::signalToJson(const SignalRecord &signal) const {
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

Json::Value SimulatedTradingService::tradeToJson(const TradeRecord &trade) const {
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

Json::Value SimulatedTradingService::positionToJson(const PositionState &position) const {
  Json::Value out;
  out["symbol"] = position.symbol;
  out["quantity"] = position.quantity;
  out["entry_price"] = position.entry_price;
  out["current_price"] = position.current_price;
  out["unrealized_pnl"] = position.unrealized_pnl;
  out["pnl_percentage"] = position.pnl_percentage;
  out["entry_time"] = position.entry_time;
  out["status"] = position.status;
  out["side"] = position.side;
  return out;
}

void SimulatedTradingService::persistSignalLocked(const SignalRecord &signal) {
  std::ostringstream sql;
  sql << "INSERT INTO order_book_signals ("
      << "signal_id, session_id, symbol, signal_type, strength, price, timestamp, signal_data, "
      << "spread, imbalance, mid_price, best_bid, best_ask, order_book_depth, volume, total_signals"
      << ") VALUES ("
      << "'" << escapeSql(signal.signal_id) << "',"
      << "'" << escapeSql(signal.session_id) << "',"
      << "'" << escapeSql(signal.symbol) << "',"
      << "'" << escapeSql(signal.signal_type) << "',"
      << signal.strength << ","
      << signal.price << ","
      << signal.timestamp << ","
      << "'" << escapeSql(jsonToString(signal.payload)) << "',"
      << signal.spread << ","
      << signal.imbalance << ","
      << signal.mid_price << ","
      << signal.best_bid << ","
      << signal.best_ask << ","
      << signal.order_book_depth << ","
      << signal.volume << ","
      << signal.total_signals
      << ") ON CONFLICT (signal_id) DO UPDATE SET "
      << "signal_type = EXCLUDED.signal_type, strength = EXCLUDED.strength, price = EXCLUDED.price, "
      << "timestamp = EXCLUDED.timestamp, signal_data = EXCLUDED.signal_data, spread = EXCLUDED.spread, "
      << "imbalance = EXCLUDED.imbalance, mid_price = EXCLUDED.mid_price, best_bid = EXCLUDED.best_bid, "
      << "best_ask = EXCLUDED.best_ask, order_book_depth = EXCLUDED.order_book_depth, volume = EXCLUDED.volume, "
      << "total_signals = EXCLUDED.total_signals";

  DatabaseManager::getInstance().query(sql.str());
}

void SimulatedTradingService::persistTradeLocked(const TradeRecord &trade) {
  std::ostringstream sql;
  sql << "INSERT INTO individual_trades ("
      << "trade_id, session_id, symbol, side, size, price, timestamp, strategy_type, signal_reason, pnl, fees, "
      << "win_probability, expected_return, model_confidence, trade_type"
      << ") VALUES ("
      << "'" << escapeSql(trade.trade_id) << "',"
      << "'" << escapeSql(trade.session_id) << "',"
      << "'" << escapeSql(trade.symbol) << "',"
      << "'" << escapeSql(trade.side) << "',"
      << trade.quantity << ","
      << trade.price << ","
      << trade.timestamp << ","
      << "'" << escapeSql(trade.strategy_type) << "',"
      << "'" << escapeSql(trade.signal_reason) << "',"
      << trade.pnl << ","
      << trade.fees << ","
      << trade.win_probability << ","
      << trade.expected_return << ","
      << trade.model_confidence << ","
      << "'" << escapeSql(trade.trade_type) << "'"
      << ") ON CONFLICT (trade_id) DO UPDATE SET "
      << "symbol = EXCLUDED.symbol, side = EXCLUDED.side, size = EXCLUDED.size, price = EXCLUDED.price, "
      << "timestamp = EXCLUDED.timestamp, strategy_type = EXCLUDED.strategy_type, signal_reason = EXCLUDED.signal_reason, "
      << "pnl = EXCLUDED.pnl, fees = EXCLUDED.fees, win_probability = EXCLUDED.win_probability, "
      << "expected_return = EXCLUDED.expected_return, model_confidence = EXCLUDED.model_confidence, "
      << "trade_type = EXCLUDED.trade_type";

  DatabaseManager::getInstance().query(sql.str());
}

SimulatedTradingService::SignalRecord
SimulatedTradingService::buildSignalRecordLocked(const std::string &symbol,
                                                 std::size_t symbol_index) {
  SignalRecord signal;
  signal.session_id = session_id_;
  signal.symbol = symbol;
  signal.timestamp = nowEpochSeconds();
  signal.timestamp_iso = nowIsoUtc();
  signal.signal_id = makeId("sig", signal.timestamp, symbol, static_cast<std::size_t>(tick_));

  const double base = basePriceForSymbol(symbol);
  const double phase = (static_cast<double>(tick_) / 3.5) + static_cast<double>(symbol_index) * 0.73;
  const double wave = std::sin(phase);
  const double drift = std::cos(phase / 4.0) * base * 0.0025;
  const double noise = std::sin(phase * 3.0) * base * 0.0008;
  const double mid = std::max(0.0001, base + drift + wave * base * 0.008 + noise);
  const double spread = std::max(0.0001, mid * (0.0004 + (0.0003 * (1.0 + std::cos(phase * 0.7)))));
  const double imbalance = std::tanh(wave * 1.4);
  const double strength = std::min(1.0, std::abs(imbalance) * 1.15);
  const bool generated = strength >= 0.22;
  const std::string signal_type = !generated ? "hold" : (imbalance >= 0.0 ? "buy" : "sell");

  signal.signal_type = signal_type;
  signal.strength = strength;
  signal.price = mid;
  signal.spread = spread;
  signal.imbalance = imbalance;
  signal.mid_price = mid;
  signal.best_bid = mid - spread / 2.0;
  signal.best_ask = mid + spread / 2.0;
  signal.order_book_depth = 20 + static_cast<int>((symbol_index + tick_) % 12);
  signal.volume = 10000.0 + std::abs(wave) * 5000.0 + static_cast<double>(symbol_index) * 1200.0;
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
  payload["signal_reason"] = generated ? (signal.signal_type == "buy" ? "Order book imbalance favors upside" : "Order book imbalance favors downside")
                                          : "Signal below activity threshold";
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

  Json::Value ml_analysis(Json::objectValue);
  ml_analysis["ml_enabled"] = true;
  ml_analysis["win_probability"] = std::clamp(0.5 + (generated ? (imbalance * 0.2) : 0.0), 0.0, 1.0);
  ml_analysis["expected_return"] = generated ? (imbalance * 0.012) : 0.0;
  ml_analysis["confidence"] = generated ? strength : 0.0;
  ml_analysis["model_version"] = "simulated-v1";
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

void SimulatedTradingService::trimHistoryLocked() {
  while (recent_trades_.size() > kMaxRecentTrades) {
    recent_trades_.pop_front();
  }
  while (recent_signals_.size() > kMaxRecentSignals) {
    recent_signals_.pop_front();
  }
}

void SimulatedTradingService::updateMarkToMarketLocked(
    const std::map<std::string, double> &prices) {
  unrealized_pnl_ = 0.0;
  total_positions_value_ = 0.0;

  for (auto &[symbol, position] : positions_) {
    const auto it = prices.find(symbol);
    if (it != prices.end()) {
      position.current_price = it->second;
    }
    const double direction = position.side == "buy" ? 1.0 : -1.0;
    position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity * direction;
    position.pnl_percentage = position.entry_price != 0.0
                                  ? (position.unrealized_pnl / (position.entry_price * position.quantity)) * 100.0
                                  : 0.0;
    position.age_ticks += 1;
    unrealized_pnl_ += position.unrealized_pnl;
    total_positions_value_ += std::abs(position.quantity * position.current_price);
  }
}

void SimulatedTradingService::openPositionLocked(const SignalRecord &signal,
                                                 const std::string &reason) {
  if (positions_.find(signal.symbol) != positions_.end()) {
    return;
  }

  const double allocated_usd = positionSizeUsdForSignal(signal);
  const double quantity = std::max(0.000001, allocated_usd / std::max(0.000001, signal.price));
  const double fee = signal.price * quantity * kFeeRate;

  PositionState position;
  position.symbol = signal.symbol;
  position.side = sanitizeSide(signal.signal_type);
  position.quantity = quantity;
  position.entry_price = signal.price;
  position.current_price = signal.price;
  position.unrealized_pnl = 0.0;
  position.pnl_percentage = 0.0;
  position.entry_timestamp = signal.timestamp;
  position.entry_time = signal.timestamp_iso;
  position.status = "open";
  position.age_ticks = 0;
  positions_[signal.symbol] = position;

  TradeRecord trade;
  trade.trade_id = makeId("trade", signal.timestamp, signal.symbol, recent_trades_.size() + 1);
  trade.session_id = session_id_;
  trade.symbol = signal.symbol;
  trade.side = position.side;
  trade.quantity = quantity;
  trade.price = signal.price;
  trade.timestamp = signal.timestamp;
  trade.timestamp_iso = signal.timestamp_iso;
  trade.strategy_type = strategy_;
  trade.signal_reason = reason;
  trade.pnl = 0.0;
  trade.fees = fee;
  trade.win_probability = signal.payload["ml_analysis"].get("win_probability", Json::Value(0.5)).asDouble();
  trade.expected_return = signal.payload["ml_analysis"].get("expected_return", Json::Value(0.0)).asDouble();
  trade.model_confidence = signal.payload["ml_analysis"].get("confidence", Json::Value(0.0)).asDouble();
  trade.trade_type = mode_;

  total_fees_ += fee;
  persistTradeLocked(trade);
  recent_trades_.push_back(trade);
  updated_at_ = nowIsoUtc();
  trimHistoryLocked();
}

Json::Value SimulatedTradingService::closePositionLocked(const std::string &symbol,
                                                         const std::string &reason) {
  Json::Value result(Json::objectValue);
  auto it = positions_.find(symbol);
  if (it == positions_.end()) {
    result["status"] = "error";
    result["error"] = "No open position for symbol";
    return result;
  }

  PositionState position = it->second;
  const double exit_price = position.current_price > 0.0 ? position.current_price : position.entry_price;
  const double direction = position.side == "buy" ? 1.0 : -1.0;
  const double gross_pnl = (exit_price - position.entry_price) * position.quantity * direction;
  const double fee = exit_price * position.quantity * kFeeRate;
  const double net_pnl = gross_pnl - fee;

  realized_pnl_ += gross_pnl;
  total_fees_ += fee;
  cash_ = initial_capital_ + realized_pnl_ - total_fees_;

  TradeRecord trade;
  const long long ts = nowEpochSeconds();
  trade.trade_id = makeId("trade", ts, symbol, recent_trades_.size() + 1);
  trade.session_id = session_id_;
  trade.symbol = symbol;
  trade.side = position.side == "buy" ? "sell" : "buy";
  trade.quantity = position.quantity;
  trade.price = exit_price;
  trade.timestamp = ts;
  trade.timestamp_iso = nowIsoUtc();
  trade.strategy_type = strategy_;
  trade.signal_reason = reason;
  trade.pnl = gross_pnl;
  trade.fees = fee;
  trade.win_probability = gross_pnl >= 0.0 ? 0.65 : 0.35;
  trade.expected_return = gross_pnl / std::max(1.0, position.entry_price * position.quantity);
  trade.model_confidence = std::min(1.0, std::abs(gross_pnl) / std::max(1.0, position.entry_price * position.quantity));
  trade.trade_type = mode_;

  persistTradeLocked(trade);
  recent_trades_.push_back(trade);
  positions_.erase(it);
  updated_at_ = nowIsoUtc();
  trimHistoryLocked();

  result["status"] = "success";
  result["message"] = "Position closed";
  result["symbol"] = symbol;
  result["trade_id"] = trade.trade_id;
  result["pnl"] = gross_pnl;
  result["fees"] = fee;
  result["net_pnl"] = net_pnl;
  return result;
}

void SimulatedTradingService::generateTickLocked() {
  if (!active_) {
    return;
  }

  tick_ += 1;
  std::map<std::string, double> prices;

  for (std::size_t index = 0; index < symbols_.size(); ++index) {
    const std::string &symbol = symbols_[index];
    auto signal = buildSignalRecordLocked(symbol, index);
    prices[symbol] = signal.price;
    recent_signals_.push_back(signal);
    persistSignalLocked(signal);

    auto position_it = positions_.find(symbol);
    const bool signal_generated = signal.signal_type != "hold";
    const std::size_t hold_ticks = std::max(3, position_update_interval_ * 2);

    if (position_it == positions_.end()) {
      if (signal_generated && static_cast<int>(positions_.size()) < max_positions_) {
        openPositionLocked(signal, "Opened on generated signal");
      }
      continue;
    }

    PositionState &position = position_it->second;
    position.current_price = signal.price;
    const bool opposite_signal = signal_generated && sanitizeSide(signal.signal_type) != position.side;
    const bool age_out = position.age_ticks >= static_cast<std::size_t>(hold_ticks);

    if (opposite_signal || age_out) {
      closePositionLocked(symbol, opposite_signal ? "Closed on opposite signal" : "Closed after holding period");
      if (signal_generated && static_cast<int>(positions_.size()) < max_positions_) {
        openPositionLocked(signal, "Re-opened after close");
      }
    }
  }

  updateMarkToMarketLocked(prices);
  total_fees_ = std::max(total_fees_, 0.0);
  cash_ = initial_capital_ + realized_pnl_ - total_fees_;
  updated_at_ = nowIsoUtc();
  trimHistoryLocked();
}

void SimulatedTradingService::workerLoop() {
  TR_LOG_INFO("Simulated trading worker started for session {}", session_id_);
  while (true) {
    try {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        if (stop_requested_) {
          break;
        }
        generateTickLocked();
      }
    } catch (const std::exception &e) {
      TR_LOG_ERROR("Simulated trading worker tick failed for session {}: {}", session_id_, e.what());
    } catch (...) {
      TR_LOG_ERROR("Simulated trading worker tick failed for session {}: unknown exception", session_id_);
    }

    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  std::lock_guard<std::mutex> lock(mutex_);
  active_ = false;
  stop_requested_ = false;
  updated_at_ = nowIsoUtc();
  TR_LOG_INFO("Simulated trading worker stopped for session {}", session_id_);
}

void SimulatedTradingService::startWorkerLocked() {
  if (worker_.joinable()) {
    worker_.join();
  }
  stop_requested_ = false;
  worker_ = std::thread([this]() { workerLoop(); });
}

Json::Value SimulatedTradingService::buildPortfolioJson() const {
  Json::Value portfolio(Json::objectValue);
  portfolio["is_active"] = active_;
  portfolio["is_trading"] = active_;
  portfolio["status"] = active_ ? "active" : "stopped";
  portfolio["session_id"] = session_id_;
  portfolio["mode"] = mode_;
  portfolio["strategy_type"] = strategy_;
  portfolio["started_at"] = started_at_;
  portfolio["updated_at"] = updated_at_;
  portfolio["symbols"] = Json::arrayValue;
  for (const auto &symbol : symbols_) {
    portfolio["symbols"].append(symbol);
  }
  portfolio["current_capital"] = initial_capital_ + realized_pnl_ + unrealized_pnl_ - total_fees_;
  portfolio["initial_capital"] = initial_capital_;
  portfolio["total_positions_value"] = total_positions_value_;
  portfolio["unrealized_pnl"] = unrealized_pnl_;
  portfolio["realized_pnl"] = realized_pnl_;
  portfolio["net_pnl"] = unrealized_pnl_ + realized_pnl_ - total_fees_;
  portfolio["total_fees"] = total_fees_;
  portfolio["open_positions_count"] = static_cast<int>(positions_.size());
  portfolio["tick"] = static_cast<Json::Int64>(tick_);

  Json::Value positions(Json::objectValue);
  for (const auto &[symbol, position] : positions_) {
    positions[symbol] = positionToJson(position);
  }
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

Json::Value SimulatedTradingService::buildStatusJson() const {
  Json::Value status = buildPortfolioJson();
  status["isActive"] = active_;
  status["is_active"] = active_;
  status["is_trading"] = active_;
  status["mode"] = mode_;
  status["strategy_type"] = strategy_;
  status["session_id"] = session_id_;
  status["symbols"] = Json::arrayValue;
  for (const auto &symbol : symbols_) {
    status["symbols"].append(symbol);
  }

  Json::Value stats_json(Json::objectValue);
  stats_json["total_pnl"] = 0.0;
  stats_json["total_fees"] = 0.0;
  stats_json["net_pnl"] = 0.0;
  stats_json["win_rate"] = 0.0;
  stats_json["total_trades"] = 0;
  stats_json["winning_trades"] = 0;
  stats_json["losing_trades"] = 0;
  stats_json["avg_win"] = 0.0;
  stats_json["avg_loss"] = 0.0;
  stats_json["best_trade"] = 0.0;
  stats_json["worst_trade"] = 0.0;
  stats_json["profit_factor"] = 0.0;
  stats_json["sharpe_ratio"] = 0.0;
  stats_json["max_drawdown"] = 0.0;
  stats_json["total_volume"] = 0.0;
  stats_json["avg_trade_size"] = 0.0;
  stats_json["trades_today"] = 0;
  stats_json["last_trade_time"] = "";

  const std::string today = formatNowIsoUtc().substr(0, 10);
  std::vector<double> pnl_values;
  std::vector<double> positive_pnls;
  std::vector<double> negative_pnls;
  double cumulative_pnl = 0.0;
  double peak_pnl = 0.0;

  stats_json["best_trade"] = std::numeric_limits<double>::lowest();
  stats_json["worst_trade"] = std::numeric_limits<double>::max();

  for (const auto &trade : recent_trades_) {
    const double pnl = trade.pnl;
    const double fees = trade.fees;
    const double volume = trade.quantity * trade.price;

    stats_json["total_pnl"] = stats_json["total_pnl"].asDouble() + pnl;
    stats_json["total_fees"] = stats_json["total_fees"].asDouble() + fees;
    stats_json["total_volume"] = stats_json["total_volume"].asDouble() + volume;
    stats_json["total_trades"] = stats_json["total_trades"].asInt() + 1;
    stats_json["last_trade_time"] = trade.timestamp_iso;

    pnl_values.push_back(pnl);

    if (pnl > 0.0) {
      stats_json["winning_trades"] = stats_json["winning_trades"].asInt() + 1;
      positive_pnls.push_back(pnl);
    } else if (pnl < 0.0) {
      stats_json["losing_trades"] = stats_json["losing_trades"].asInt() + 1;
      negative_pnls.push_back(pnl);
    }

    stats_json["best_trade"] = std::max(stats_json["best_trade"].asDouble(), pnl);
    stats_json["worst_trade"] = std::min(stats_json["worst_trade"].asDouble(), pnl);

    cumulative_pnl += pnl;
    peak_pnl = std::max(peak_pnl, cumulative_pnl);
    stats_json["max_drawdown"] = std::max(stats_json["max_drawdown"].asDouble(), peak_pnl - cumulative_pnl);

    if (!trade.timestamp_iso.empty() && trade.timestamp_iso.rfind(today, 0) == 0) {
      stats_json["trades_today"] = stats_json["trades_today"].asInt() + 1;
    }
  }

  if (stats_json["total_trades"].asInt() > 0) {
    const double total_trades = static_cast<double>(stats_json["total_trades"].asInt());
    stats_json["win_rate"] = static_cast<double>(stats_json["winning_trades"].asInt()) / total_trades * 100.0;
    stats_json["avg_trade_size"] = stats_json["total_volume"].asDouble() / total_trades;
    stats_json["net_pnl"] = stats_json["total_pnl"].asDouble() - stats_json["total_fees"].asDouble();

    if (!positive_pnls.empty()) {
      double gross_wins = 0.0;
      for (double value : positive_pnls) {
        gross_wins += value;
      }
      stats_json["avg_win"] = gross_wins / static_cast<double>(positive_pnls.size());
    }

    if (!negative_pnls.empty()) {
      double gross_losses = 0.0;
      for (double value : negative_pnls) {
        gross_losses += value;
      }
      stats_json["avg_loss"] = gross_losses / static_cast<double>(negative_pnls.size());
    }

    stats_json["profit_factor"] = trade::ml::Metrics::calculate_profit_factor(pnl_values);
    stats_json["sharpe_ratio"] = trade::ml::Metrics::calculate_sharpe_ratio(pnl_values);
  }

  if (stats_json["best_trade"].asDouble() == std::numeric_limits<double>::lowest()) {
    stats_json["best_trade"] = 0.0;
  }
  if (stats_json["worst_trade"].asDouble() == std::numeric_limits<double>::max()) {
    stats_json["worst_trade"] = 0.0;
  }

  status["stats"] = stats_json;
  return status;
}

Json::Value SimulatedTradingService::startSession(const Json::Value &payload,
                                                  const std::string &mode) {
  std::lock_guard<std::mutex> lock(mutex_);
  ensureSchema();

  if (active_) {
    Json::Value resp = buildStatusJson();
    resp["message"] = "Simulated trading already running";
    return resp;
  }

  session_id_ = payload.isMember("session_id") ? payload["session_id"].asString() : makeSessionId();
  mode_ = mode;
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

  parameters_ = payload.isMember("parameters") && payload["parameters"].isObject()
                    ? payload["parameters"]
                    : Json::Value(Json::objectValue);

  if (payload.isMember("position_size_percent")) {
    parameters_["position_size_percent"] = payload["position_size_percent"];
  }
  if (payload.isMember("max_positions")) {
    parameters_["max_positions"] = payload["max_positions"];
  }
  if (payload.isMember("position_update_interval")) {
    parameters_["position_update_interval"] = payload["position_update_interval"];
  }

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
  initial_capital_ = parameters_.isMember("initial_portfolio_size")
                         ? parameters_["initial_portfolio_size"].asDouble()
                         : (payload.isMember("initial_portfolio_size")
                                ? payload["initial_portfolio_size"].asDouble()
                                : kDefaultInitialCapital);
  initial_capital_ = std::max(100.0, initial_capital_);
  cash_ = initial_capital_;
  realized_pnl_ = 0.0;
  unrealized_pnl_ = 0.0;
  total_fees_ = 0.0;
  total_positions_value_ = 0.0;
  positions_.clear();
  recent_trades_.clear();
  recent_signals_.clear();
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
  resp["message"] = "Simulated trading started";
  return resp;
}

Json::Value SimulatedTradingService::stopSession() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!active_ && !worker_.joinable()) {
      Json::Value resp = buildStatusJson();
      resp["message"] = "Simulated trading already stopped";
      return resp;
    }
    stop_requested_ = true;
  }

  if (worker_.joinable()) {
    worker_.join();
  }

  std::lock_guard<std::mutex> lock(mutex_);
  active_ = false;
  stop_requested_ = false;
  updated_at_ = nowIsoUtc();

  Json::Value resp = buildStatusJson();
  resp["status"] = "success";
  resp["is_active"] = false;
  resp["is_trading"] = false;
  resp["message"] = "Simulated trading stopped";
  return resp;
}

Json::Value SimulatedTradingService::getStatus(const std::string &session_id) {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value resp = buildStatusJson();
  if (!session_id.empty()) {
    resp["requested_session_id"] = session_id;
  }
  return resp;
}

Json::Value SimulatedTradingService::updateStrategyParameters(const Json::Value &payload) {
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
  if (parameters_.isMember("initial_portfolio_size")) {
    initial_capital_ = std::max(100.0, parameters_["initial_portfolio_size"].asDouble());
    cash_ = initial_capital_ + realized_pnl_ - total_fees_;
  }

  Json::Value resp;
  resp["status"] = "success";
  resp["message"] = "Strategy parameters updated";
  resp["parameters"] = parameters_;
  resp["max_positions"] = max_positions_;
  resp["position_update_interval"] = position_update_interval_;
  return resp;
}

Json::Value SimulatedTradingService::getOpenPositions() {
  std::lock_guard<std::mutex> lock(mutex_);
  Json::Value positions(Json::arrayValue);
  for (const auto &[symbol, position] : positions_) {
    positions.append(positionToJson(position));
  }
  return positions;
}

Json::Value SimulatedTradingService::getLivePortfolioStatus() {
  std::lock_guard<std::mutex> lock(mutex_);
  return buildPortfolioJson();
}

Json::Value SimulatedTradingService::getOrderBookSignals(const std::vector<std::string> &symbols,
                                                         int page,
                                                         int per_page) {
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

    std::ostringstream where;
    bool has_where = false;
    if (!symbols.empty()) {
      where << " WHERE symbol IN (";
      for (std::size_t i = 0; i < symbols.size(); ++i) {
        if (i > 0) {
          where << ",";
        }
        where << "'" << escapeSql(symbols[i]) << "'";
      }
      where << ")";
      has_where = true;
    }

    auto count_res = DatabaseManager::getInstance().query(
        "SELECT COUNT(DISTINCT symbol) AS total_count FROM order_book_signals" + where.str());
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

    auto rows = DatabaseManager::getInstance().query(sql.str());
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

Json::Value SimulatedTradingService::closePosition(const std::string &symbol) {
  std::lock_guard<std::mutex> lock(mutex_);
  return closePositionLocked(symbol, "Manual close request");
}

} // namespace trading
} // namespace trade
