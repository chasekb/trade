#include "trading/SimulatedTradingService.hpp"

#include "api/PredictController.hpp"
#include "db/DatabaseManager.hpp"
#include "ml/Types.hpp"
#include <pqxx/pqxx>
#include "trading/TradingStatsCalculator.hpp"
#include "trading/TradingStatsService.hpp"
#include "trading/PortfolioAccounting.hpp"
#include "trading/PositionSizingPolicy.hpp"
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

  auto [state_it, state_inserted] = market_state_.try_emplace(symbol);
  SymbolMarketState &state = state_it->second;
  if (state_inserted) {
    state.price = basePriceForSymbol(symbol);
    state.rng.seed(static_cast<std::uint32_t>(
        std::hash<std::string>{}(symbol) ^
        static_cast<std::size_t>(start_epoch_seconds_)));
  }

  std::uniform_real_distribution<double> unit(-1.0, 1.0);
  std::uniform_real_distribution<double> unit01(0.0, 1.0);

  // Imbalance is persistent (AR(1)) and *leads* price: the current tick's
  // return contains a component proportional to the prior imbalance. Acting on
  // strong imbalance therefore has genuine positive expectancy while the
  // imbalance persists, unlike the old sine wave where strong signals marked
  // reverting extremes.
  constexpr double kImbalancePersistence = 0.85;
  constexpr double kImbalanceImpact = 0.0015;
  constexpr double kNoiseVol = 0.002;

  const double prior_imbalance = state.imbalance;
  const double tick_return = kImbalanceImpact * prior_imbalance + kNoiseVol * unit(state.rng);
  state.price = std::max(0.0001, state.price * (1.0 + tick_return));
  state.last_return = tick_return;
  state.imbalance = std::clamp(
      kImbalancePersistence * prior_imbalance + 0.35 * unit(state.rng), -1.0, 1.0);

  const double mid = state.price;
  const double imbalance = state.imbalance;
  const double spread = std::max(0.0001, mid * (0.0004 + 0.0003 * unit01(state.rng)));
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
  signal.volume = 10000.0 + std::abs(imbalance) * 5000.0 + static_cast<double>(symbol_index) * 1200.0;
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

bool SimulatedTradingService::signalPassesMlGateLocked(const SignalRecord &signal) const {
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
    total_positions_value_ +=
        signedPositionValue(position.side, position.quantity, position.current_price);
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
  position.entry_win_probability =
      signal.payload["ml_analysis"].get("win_probability", Json::Value(0.5)).asDouble();
  position.entry_expected_return =
      signal.payload["ml_analysis"].get("expected_return", Json::Value(0.0)).asDouble();
  position.entry_model_confidence =
      signal.payload["ml_analysis"].get("confidence", Json::Value(0.0)).asDouble();
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
  cash_ += openCashDelta(position.side, allocated_usd, fee);
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
  cash_ += closeCashDelta(position.side, exit_price * position.quantity, fee);

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
  // Persist the prediction-time values captured at entry; deriving them from
  // the realized outcome would poison calibration and training data.
  trade.win_probability = position.entry_win_probability;
  trade.expected_return = position.entry_expected_return;
  trade.model_confidence = position.entry_model_confidence;
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
      if (signal_generated && static_cast<int>(positions_.size()) < max_positions_ &&
          signalPassesMlGateLocked(signal)) {
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
      if (signal_generated && static_cast<int>(positions_.size()) < max_positions_ &&
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
  const double total_value = cash_ + directional_positions_value;

  portfolio["cash_balance"] = cash_;
  portfolio["available_balance_usd"] = cash_;
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
    TR_LOG_WARN("Failed to load persisted simulated trade stats for session {}: {}", session_id_, e.what());
  }

  if (trades.empty()) {
    trades.reserve(recent_trades_.size());
    for (const auto &trade : recent_trades_) {
      trades.push_back(TradePerformanceInput{trade.pnl, trade.fees, trade.quantity, trade.price, trade.timestamp_iso});
    }
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
  market_state_.clear();
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
    const double previous_capital = initial_capital_;
    initial_capital_ = std::max(100.0, parameters_["initial_portfolio_size"].asDouble());
    // Adjust cash by the capital delta only; a full reset would erase the
    // debits/credits of currently open positions.
    cash_ += initial_capital_ - previous_capital;
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
