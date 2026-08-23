
#include "api/PredictController.hpp"
#include "cache/CacheManager.hpp"
#include "config/Config.hpp"
#include "db/DatabaseManager.hpp"

#include "ml/ModelTrainer.hpp"
#include "ml/Types.hpp"
#include "trading/ExecutionReconciliation.hpp"
#include "trading/LiveTradingService.hpp"
#include "trading/TradingStatsService.hpp"
#include "trading/SimulatedTradingService.hpp"
#include "utils/Logger.hpp"
#include <atomic>
#include <array>
#include <chrono>
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>
#include <nlohmann/json.hpp>
#include <thread>

namespace api {

namespace {
bool parse_bool_param(const std::string &raw, bool default_value) {
  if (raw.empty()) {
    return default_value;
  }

  std::string value = raw;
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

  if (value == "1" || value == "true" || value == "yes" || value == "on") {
    return true;
  }
  if (value == "0" || value == "false" || value == "no" || value == "off") {
    return false;
  }
  return default_value;
}

int parse_int_param(const std::string &raw, int default_value) {
  if (raw.empty()) {
    return default_value;
  }
  try {
    return std::stoi(raw);
  } catch (const std::exception &) {
    return default_value;
  }
}

int clamp_int(int value, int low, int high) {
  return std::max(low, std::min(high, value));
}

// Query parameters are interpolated into diagnostic SQL, so restrict them to
// the identifier characters the trading services actually emit.
std::string sanitize_sql_literal(const std::string &raw) {
  std::string out;
  out.reserve(raw.size());
  for (const char c : raw) {
    const unsigned char uc = static_cast<unsigned char>(c);
    if (std::isalnum(uc) || c == '-' || c == '_' || c == '.') {
      out.push_back(c);
    }
  }
  return out;
}

Json::Value parse_json_object(const std::string &text) {
  Json::Value parsed;
  if (text.empty()) {
    return Json::Value(Json::objectValue);
  }
  Json::CharReaderBuilder builder;
  std::string errs;
  std::istringstream stream(text);
  if (!Json::parseFromStream(builder, stream, &parsed, &errs) || !parsed.isObject()) {
    return Json::Value(Json::objectValue);
  }
  return parsed;
}

Json::Value reconciliation_to_json(const trade::trading::StrategyReconciliation &metrics) {
  Json::Value out(Json::objectValue);
  out["strategy"] = metrics.strategy;
  out["signals_evaluated"] = static_cast<Json::UInt64>(metrics.signals_evaluated);
  out["signals_generated"] = static_cast<Json::UInt64>(metrics.signals_generated);
  out["executable_intents"] = static_cast<Json::UInt64>(metrics.executable_intents);
  out["blocked_intents"] = static_cast<Json::UInt64>(metrics.blocked_intents);
  out["closing_legs"] = static_cast<Json::UInt64>(metrics.closing_legs);
  out["winners"] = static_cast<Json::UInt64>(metrics.winners);
  out["losers"] = static_cast<Json::UInt64>(metrics.losers);
  out["win_rate"] = metrics.win_rate;
  out["average_win"] = metrics.average_win;
  out["average_loss"] = metrics.average_loss;
  out["expectancy"] = metrics.expectancy;
  // jsoncpp cannot serialize a non-finite double; an all-winners window is
  // reported as an explicit flag instead of a bogus number.
  out["profit_factor"] = std::isfinite(metrics.profit_factor) ? metrics.profit_factor : 0.0;
  out["profit_factor_undefined"] = !std::isfinite(metrics.profit_factor);
  out["total_pnl"] = metrics.total_pnl;
  out["total_fees"] = metrics.total_fees;
  out["intent_conversion_rate"] = metrics.intent_conversion_rate;
  out["outcome_coverage"] = metrics.outcome_coverage;
  out["outcomes_unexplained"] = metrics.outcomes_unexplained;
  out["negative_expectancy_flag"] = metrics.negative_expectancy_flag;
  out["dominant_blocker"] = metrics.dominant_blocker;
  out["blockers"] = Json::arrayValue;
  for (const auto &bucket : metrics.blockers) {
    Json::Value row(Json::objectValue);
    row["reason"] = bucket.reason;
    row["count"] = static_cast<Json::UInt64>(bucket.count);
    row["share"] = bucket.share;
    row["blocked_expected_return_sum"] = bucket.blocked_expected_return_sum;
    out["blockers"].append(row);
  }
  return out;
}

std::string model_type_to_string(const trade::ml::ModelType type) {
  switch (type) {
  case trade::ml::ModelType::RANDOM_FOREST:
    return "regression";
  case trade::ml::ModelType::GRADIENT_BOOSTING:
    return "classification";
  case trade::ml::ModelType::TRANSFORMER:
    return "sequence";
  default:
    return "unknown";
  }
}

trade::ml::ModelType model_type_from_string(const std::string &raw_type) {
  std::string value = raw_type;
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

  if (value == "regression" || value == "random_forest") {
    return trade::ml::ModelType::RANDOM_FOREST;
  }
  if (value == "classification" || value == "gradient_boosting" ||
      value == "xgboost") {
    return trade::ml::ModelType::GRADIENT_BOOSTING;
  }
  if (value == "sequence" || value == "transformer") {
    return trade::ml::ModelType::TRANSFORMER;
  }
  return trade::ml::ModelType::RANDOM_FOREST;
}

std::vector<std::string> required_artifacts_for(const trade::ml::ModelType type) {
  switch (type) {
  case trade::ml::ModelType::RANDOM_FOREST:
    return {"regressor.onnx"};
  case trade::ml::ModelType::GRADIENT_BOOSTING:
    return {"classifier.onnx"};
  case trade::ml::ModelType::TRANSFORMER:
    return {"transformer.onnx"};
  default:
    return {};
  }
}

std::vector<std::string> optional_artifacts_for(const trade::ml::ModelType type) {
  switch (type) {
  case trade::ml::ModelType::TRANSFORMER:
    return {"transformer_config.json"};
  default:
    return {};
  }
}

// Model ids become path components under the trained-models directory; only
// simple names are allowed so request input can never traverse out of it.
bool is_safe_model_id(const std::string &model_id) {
  if (model_id.empty() || model_id.size() > 128) {
    return false;
  }
  for (unsigned char c : model_id) {
    if (!(std::isalnum(c) || c == '_' || c == '-' || c == '.')) {
      return false;
    }
  }
  return model_id.find("..") == std::string::npos;
}

std::string now_iso_utc() {
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

std::uintmax_t validated_file_size(const std::filesystem::path &path) {
  std::error_code ec;
  if (!std::filesystem::exists(path, ec) || ec) {
    return 0;
  }
  if (!std::filesystem::is_regular_file(path, ec) || ec) {
    return 0;
  }
  const auto size = std::filesystem::file_size(path, ec);
  if (ec) {
    return 0;
  }
  return size;
}

std::uintmax_t copy_required_artifact(const std::filesystem::path &src,
                                      const std::filesystem::path &dst) {
  std::error_code ec;
  const auto src_size = validated_file_size(src);
  if (src_size == 0) {
    throw std::runtime_error("Required model artifact is missing or empty: " +
                             src.string());
  }

  std::filesystem::create_directories(dst.parent_path(), ec);
  if (ec) {
    throw std::runtime_error("Failed to create artifact directory '" +
                             dst.parent_path().string() + "': " + ec.message());
  }

  std::filesystem::remove(dst, ec);
  ec.clear();
  std::filesystem::copy_file(src, dst, std::filesystem::copy_options::overwrite_existing, ec);
  if (ec) {
    throw std::runtime_error("Failed to copy artifact from '" + src.string() +
                             "' to '" + dst.string() + "': " + ec.message());
  }

  std::filesystem::permissions(
      dst,
      std::filesystem::perms::owner_read |
          std::filesystem::perms::owner_write |
          std::filesystem::perms::group_read |
          std::filesystem::perms::others_read,
      std::filesystem::perm_options::replace, ec);
  if (ec) {
    TR_LOG_WARN("Failed to normalize permissions on '{}': {}", dst.string(),
                ec.message());
  }

  const auto dst_size = validated_file_size(dst);
  if (dst_size == 0) {
    throw std::runtime_error("Copied artifact is empty: " + dst.string());
  }

  TR_LOG_INFO("Packaged model artifact '{}' -> '{}' ({} bytes)", src.string(),
              dst.string(), dst_size);
  return dst_size;
}

bool directory_is_writable(const std::filesystem::path &dir) {
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  if (ec) {
    return false;
  }

  const auto probe = dir / ".trade_write_probe";
  {
    std::ofstream out(probe, std::ios::binary | std::ios::trunc);
    if (!out.is_open()) {
      std::filesystem::remove(probe, ec);
      return false;
    }
    out << 'x';
    if (!out.good()) {
      std::filesystem::remove(probe, ec);
      return false;
    }
  }

  std::filesystem::remove(probe, ec);
  return !ec;
}

std::filesystem::path writable_package_dir_for_model(
    const std::filesystem::path &base_dir, const std::string &model_id) {
  const auto candidate = base_dir / model_id;
  if (directory_is_writable(candidate)) {
    return candidate;
  }

  const auto fallback_root = std::filesystem::temp_directory_path() /
                             "trade_trained_models";
  const auto fallback = fallback_root / model_id;
  if (directory_is_writable(fallback)) {
    TR_LOG_WARN(
        "Configured trained-model package directory '{}' unavailable or unwritable; using '{}' instead",
        candidate.string(), fallback.string());
    return fallback;
  }

  throw std::runtime_error("Unable to create a writable package directory at '" +
                           candidate.string() + "' or fallback '" +
                           fallback.string() + "'");
}

std::filesystem::path unique_temp_artifact_path(
    const std::filesystem::path &dst) {
  static std::atomic<std::uint64_t> sequence{0};
  const auto now = std::chrono::steady_clock::now().time_since_epoch().count();
  return std::filesystem::path(dst.string() + ".tmp." +
                               std::to_string(now) + "." +
                               std::to_string(
                                   sequence.fetch_add(1, std::memory_order_relaxed)));
}

std::uintmax_t copy_file_streaming(const std::filesystem::path &src,
                                   const std::filesystem::path &dst) {
  std::ifstream in(src, std::ios::binary);
  if (!in.is_open()) {
    throw std::runtime_error("Failed to open source artifact '" + src.string() +
                             "'");
  }

  std::ofstream out(dst, std::ios::binary | std::ios::trunc);
  if (!out.is_open()) {
    throw std::runtime_error("Failed to open destination artifact '" +
                             dst.string() + "'");
  }

  std::array<char, 1 << 20> buffer{};
  std::uintmax_t total = 0;
  while (in) {
    in.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const auto bytes_read = in.gcount();
    if (bytes_read <= 0) {
      break;
    }
    out.write(buffer.data(), bytes_read);
    if (!out) {
      throw std::runtime_error("Failed to write artifact chunk from '" +
                               src.string() + "' to '" + dst.string() + "'");
    }
    total += static_cast<std::uintmax_t>(bytes_read);
  }

  out.flush();
  if (!out.good()) {
    throw std::runtime_error("Failed to flush artifact to '" + dst.string() +
                             "'");
  }

  return total;
}

std::uintmax_t copy_artifact_via_temp_file(const std::filesystem::path &src,
                                          const std::filesystem::path &dst,
                                          bool required) {
  const auto src_size = validated_file_size(src);
  if (src_size == 0) {
    if (required) {
      throw std::runtime_error("Required model artifact is missing or empty: " +
                               src.string());
    }
    return 0;
  }

  const std::filesystem::path legacy_tmp_path(dst.string() + ".tmp");
  const std::filesystem::path tmp_path = unique_temp_artifact_path(dst);
  std::error_code ec;
  std::filesystem::create_directories(dst.parent_path(), ec);
  if (ec) {
    throw std::runtime_error("Failed to create artifact directory '" +
                             dst.parent_path().string() + "': " + ec.message());
  }

  auto copy_directly = [&]() -> std::uintmax_t {
    std::filesystem::remove(dst, ec);
    ec.clear();
    const auto copied = copy_file_streaming(src, dst);
    if (copied == 0) {
      throw std::runtime_error("Failed to copy artifact from '" + src.string() +
                               "' to '" + dst.string() + "': empty copy");
    }

    std::filesystem::permissions(
        dst,
        std::filesystem::perms::owner_read |
            std::filesystem::perms::owner_write |
            std::filesystem::perms::group_read |
            std::filesystem::perms::others_read,
        std::filesystem::perm_options::replace, ec);
    if (ec) {
      TR_LOG_WARN("Failed to normalize permissions on '{}': {}", dst.string(),
                  ec.message());
    }

    const auto dst_size = validated_file_size(dst);
    if (dst_size == 0) {
      throw std::runtime_error("Final artifact is empty: " + dst.string());
    }

    TR_LOG_INFO("Packaged model artifact '{}' -> '{}' ({} bytes)", src.string(),
                dst.string(), dst_size);
    return dst_size;
  };


  std::filesystem::remove(legacy_tmp_path, ec);
  ec.clear();
  std::filesystem::remove(tmp_path, ec);
  ec.clear();
  try {
    copy_file_streaming(src, tmp_path);
  } catch (const std::exception &e) {
    TR_LOG_WARN(
        "Failed to copy artifact from '{}' to temp path '{}': {}; retrying direct copy to '{}'",
        src.string(), tmp_path.string(), e.what(), dst.string());
    return copy_directly();
  }

  const auto tmp_size = validated_file_size(tmp_path);
  if (tmp_size == 0) {
    std::filesystem::remove(tmp_path, ec);
    TR_LOG_WARN("Copied temp artifact was empty at '{}'; retrying direct copy to '{}'",
                tmp_path.string(), dst.string());
    return copy_directly();
  }

  std::filesystem::remove(dst, ec);
  ec.clear();
  std::filesystem::rename(tmp_path, dst, ec);
  if (ec) {
    std::filesystem::remove(tmp_path, ec);
    TR_LOG_WARN(
        "Failed to promote temp artifact from '{}' to '{}': {}; retrying direct copy",
        tmp_path.string(), dst.string(), ec.message());
    return copy_directly();
  }

  std::filesystem::permissions(
      dst,
      std::filesystem::perms::owner_read |
          std::filesystem::perms::owner_write |
          std::filesystem::perms::group_read |
          std::filesystem::perms::others_read,
      std::filesystem::perm_options::replace, ec);
  if (ec) {
    TR_LOG_WARN("Failed to normalize permissions on '{}': {}", dst.string(),
                ec.message());
  }

  const auto dst_size = validated_file_size(dst);
  if (dst_size == 0) {
    throw std::runtime_error("Final artifact is empty: " + dst.string());
  }

  TR_LOG_INFO("Packaged model artifact '{}' -> '{}' ({} bytes)", src.string(),
              dst.string(), dst_size);
  return dst_size;
}

bool optional_artifact_available(const std::filesystem::path &path) {
  return validated_file_size(path) > 0;
}

void remove_directory_tree(const std::filesystem::path &path,
                           const std::string &reason) {
  std::error_code ec;
  const auto removed = std::filesystem::remove_all(path, ec);
  if (ec) {
    TR_LOG_WARN("Failed to remove {} '{}': {}", reason, path.string(),
                ec.message());
    return;
  }
  if (removed > 0) {
    TR_LOG_INFO("Removed {} '{}' ({} entries)", reason, path.string(),
                removed);
  }
}
} // namespace

std::unique_ptr<ml::FeatureEngineer> PredictController::feature_engineer_ =
    nullptr;
std::unique_ptr<ml::ONNXModelManager> PredictController::model_manager_ =
    nullptr;
std::string PredictController::model_dir_;
std::string PredictController::trained_models_dir_;

void PredictController::init(const std::string &param_path,
                             const std::string &model_dir) {
  model_dir_ = model_dir;
  {
    namespace fs = std::filesystem;
    auto &cfg = Config::getInstance();
    trained_models_dir_ = cfg.get("TRAINED_MODELS_DIR", "");

    if (trained_models_dir_.empty()) {
      trained_models_dir_ = (fs::path(model_dir_) / "trained").string();
    }

    const fs::path configured_dir(trained_models_dir_);
    if (!directory_is_writable(configured_dir)) {
      const fs::path fallback("/tmp/trade_trained_models");
      if (directory_is_writable(fallback)) {
        trained_models_dir_ = fallback.string();
        TR_LOG_WARN(
            "Configured trained-model path unavailable or unwritable; falling back to {}",
            trained_models_dir_);
      } else {
        TR_LOG_ERROR(
            "Unable to create a writable trained model directory at '{}' or fallback '{}'",
            configured_dir.string(), fallback.string());
      }
    }
  }

  feature_engineer_ = std::make_unique<ml::FeatureEngineer>();
  if (!feature_engineer_->load_parameters(param_path)) {
    TR_LOG_WARN("Feature engineer parameters from {} unavailable; continuing with built-in fallback parameters",
                param_path);
  }

  model_manager_ = std::make_unique<ml::ONNXModelManager>();
  if (!model_manager_->load_models(model_dir)) {
    TR_LOG_WARN("No usable ONNX models loaded from {}; continuing with neutral prediction fallbacks",
                model_dir);
  }
}

void PredictController::predict(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  if (!json_req) {
    auto resp = HttpResponse::newHttpJsonResponse(Json::Value());
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  try {
    // Convert Json::Value to nlohmann::json for my types
    // (Drogon uses JsonCpp, I use nlohmann for consistency with my internal
    // logic)
    Json::StreamWriterBuilder builder;
    std::string req_body = Json::writeString(builder, *json_req);
    auto j = nlohmann::json::parse(req_body);

    ml::OrderBookFeatures features;
    ml::from_json(j, features);

    if (!feature_engineer_) {
      Json::Value err;
      err["error"] = "ML feature engineering is not initialized";
      auto resp = HttpResponse::newHttpJsonResponse(err);
      resp->setStatusCode(k503ServiceUnavailable);
      callback(resp);
      return;
    }

    // Run Preprocessing
    auto pca_features = feature_engineer_->preprocess(features);

    const bool models_ready = model_manager_ && model_manager_->is_ready();
    if (!models_ready) {
      TR_LOG_WARN(
          "ML model sessions are not ready; returning fallback prediction values instead of failing the request");
    }

    // Run Inference (or fall back to neutral defaults when the model pack is unavailable)
    double pnl = models_ready ? model_manager_->predict_pnl(pca_features) : 0.0;
    double win_prob = models_ready ? model_manager_->predict_win_prob(pca_features) : 0.5;

    // Phase 6: Transformer Prediction
    auto sequence = feature_engineer_->get_transformer_sequence(features.symbol);
    double transformer_pnl = models_ready ? model_manager_->predict_transformer(sequence) : 0.0;

    Json::Value result;
    result["expected_pnl"] = pnl;
    result["transformer_pnl"] = transformer_pnl;
    result["win_probability"] = win_prob;
    result["confidence"] = std::abs(win_prob - 0.5) * 2.0;
    result["timestamp"] = (Json::Int64)features.timestamp;
    result["models_ready"] = models_ready;
    if (!models_ready) {
      result["warning"] = "ML models are unavailable; returned fallback prediction values";
    }

    callback(HttpResponse::newHttpJsonResponse(result));

  } catch (const std::exception &e) {
    TR_LOG_ERROR("Prediction error: {}", e.what());
    Json::Value err;
    err["error"] = e.what();
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k500InternalServerError);
    callback(resp);
  }
}

void PredictController::tradingStats(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  // Optional scoping: ?trade_type=simulated|live (alias: mode) and ?session_id=.
  trade::trading::TradingStatsFilter filter;
  filter.trade_type = req->getParameter("trade_type");
  if (filter.trade_type.empty()) {
    filter.trade_type = req->getParameter("mode");
  }
  filter.session_id = req->getParameter("session_id");

  const auto stats = trade::trading::TradingStatsService::getInstance().getTradingStats(filter);

  Json::Value result;
  result["total_pnl"] = stats.total_pnl;
  result["total_fees"] = stats.total_fees;
  result["net_pnl"] = stats.net_pnl;
  result["win_rate"] = stats.win_rate;
  result["total_trades"] = stats.total_trades;
  result["winning_trades"] = stats.winning_trades;
  result["losing_trades"] = stats.losing_trades;
  result["avg_win"] = stats.avg_win;
  result["avg_loss"] = stats.avg_loss;
  result["best_trade"] = stats.best_trade;
  result["worst_trade"] = stats.worst_trade;
  result["profit_factor"] = stats.profit_factor;
  result["sharpe_ratio"] = stats.sharpe_ratio;
  result["max_drawdown"] = stats.max_drawdown;
  result["total_volume"] = stats.total_volume;
  result["avg_trade_size"] = stats.avg_trade_size;
  result["trades_today"] = stats.trades_today;
  if (!stats.last_trade_time.empty()) {
    result["last_trade_time"] = stats.last_trade_time;
  }

  callback(HttpResponse::newHttpJsonResponse(result));
}

void PredictController::train(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();

  nlohmann::json payload = nlohmann::json::object();
  if (json_req) {
    try {
      Json::StreamWriterBuilder builder;
      payload = nlohmann::json::parse(Json::writeString(builder, *json_req));
    } catch (const std::exception &) {
      Json::Value err;
      err["error"] = "Invalid JSON payload";
      auto resp = HttpResponse::newHttpJsonResponse(err);
      resp->setStatusCode(k400BadRequest);
      callback(resp);
      return;
    }
  }

  auto &cfg = Config::getInstance();

  trade::ml::TrainingConfig config;
  config.batch_size =
      cfg.getInt("ML_TRAINING_BATCH_SIZE", config.batch_size);
  config.epochs = payload.value("epochs", config.epochs);
  config.learning_rate = payload.value("learning_rate", config.learning_rate);
  config.batch_size = payload.value("batch_size", config.batch_size);
  config.batch_training = payload.value("batch_training", config.batch_training);
  config.test_split = payload.value("test_split", config.test_split);
  config.days_back = payload.value("days_back", config.days_back);
  config.max_training_rows =
      payload.value("max_training_rows", config.max_training_rows);
  const bool auto_set_active =
      parse_bool_param(req->getParameter("auto_set_active"),
                       payload.value("auto_set_active", false));

  // Support frontend query-parameter contract: /api/ml/train?batch_training=true
  config.batch_training = parse_bool_param(req->getParameter("batch_training"),
                                           config.batch_training);
  config.batch_size =
      parse_int_param(req->getParameter("batch_size"), config.batch_size);
  config.max_training_rows = parse_int_param(req->getParameter("max_training_rows"),
                                             config.max_training_rows);

  if (config.days_back <= 0) {
    // default to all data unless explicitly constrained
    config.days_back = 0;
  }
  if (config.max_training_rows < 0) {
    config.max_training_rows = 0;
  }
  if (config.batch_size <= 0) {
    config.batch_size = 1;
  }
  config.model_name = payload.value("model_name", config.model_name);
  if (!is_safe_model_id(config.model_name)) {
    Json::Value err;
    err["error"] = "model_name contains invalid characters";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  std::string model_type = payload.value("model_type", "random_forest");
  std::transform(model_type.begin(), model_type.end(), model_type.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

  if (model_type == "random_forest") {
    config.type = trade::ml::ModelType::RANDOM_FOREST;
  } else if (model_type == "gradient_boosting" || model_type == "xgboost") {
    config.type = trade::ml::ModelType::GRADIENT_BOOSTING;
  } else if (model_type == "transformer") {
    config.type = trade::ml::ModelType::TRANSFORMER;
  } else {
    Json::Value err;
    err["error"] = "Unsupported model_type. Use random_forest, gradient_boosting, or transformer.";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  std::string db_url = cfg.get("DATABASE_URL");
  if (db_url.empty()) {
    Json::Value err;
    err["error"] = "DATABASE_URL is not configured";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k500InternalServerError);
    callback(resp);
    return;
  }

  auto &cache = CacheManager::getInstance();
  const auto [training_status, training_progress] = cache.get_training_status();
  if (training_status == "training") {
    Json::Value err;
    err["error"] = "A model training job is already running";
    err["status"] = training_status;
    err["progress"] = training_progress;
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k409Conflict);
    callback(resp);
    return;
  }

  // Trigger real training in a background thread
  std::thread training_thread([config, db_url, auto_set_active]() {
    auto &cache = CacheManager::getInstance();
    TR_LOG_INFO("ML training started: model='{}', epochs={}, batch_size={}, batch_training={}, max_training_rows={}, test_split={}, days_back={}",
                config.model_name, config.epochs, config.batch_size,
                config.batch_training, config.max_training_rows,
                config.test_split, config.days_back);

    cache.set_training_status("training", 10); // Started
    TR_LOG_INFO("ML training progress: 10% (initialization)");

    try {
      auto collector = std::make_shared<trade::ml::DataCollector>(db_url);
      trade::ml::ModelTrainer trainer(collector);

      cache.set_training_status("training", 50); // Mid-way
      TR_LOG_INFO("ML training progress: 50% (data loaded, training phase)");

      trade::ml::ModelMetrics metrics = trainer.train(config);
      cache.set_last_metrics(metrics);

      const std::string trained_at = now_iso_utc();
      const std::string version_id = std::to_string(std::time(nullptr));
      // Keep package names filesystem-safe for bind mounts and host volumes.
      const std::string model_id = config.model_name + "_" + version_id;

      const std::filesystem::path model_root(PredictController::model_dir_);
      const std::filesystem::path trained_root(PredictController::trained_models_dir_);
      if (trained_root.empty()) {
        throw std::runtime_error("trained models directory is not configured");
      }
      const std::filesystem::path package_dir =
          writable_package_dir_for_model(trained_root, model_id);
      remove_directory_tree(package_dir, "stale trained model package");

      std::error_code package_ec;
      std::filesystem::create_directories(package_dir, package_ec);
      if (package_ec) {
        throw std::runtime_error("Failed to create trained package directory: " +
                                 package_dir.string() + ": " + package_ec.message());
      }

      const bool is_transformer =
          config.type == trade::ml::ModelType::TRANSFORMER;
      if (is_transformer) {
        const auto transformer_features =
            feature_engineer_ ? static_cast<int64_t>(
                                   feature_engineer_->transformer_feature_dim())
                             : 0;
        trainer.export_transformer_artifact(package_dir / "transformer.onnx",
                                            transformer_features);
      }

      const auto required_artifacts = required_artifacts_for(config.type);
      const auto optional_artifacts = optional_artifacts_for(config.type);
      std::vector<std::string> metadata_required_artifacts = required_artifacts;
      if (is_transformer) {
        metadata_required_artifacts.push_back("transformer_config.json");
      }

      std::uintmax_t regressor_size = 0;
      std::uintmax_t classifier_size = 0;
      std::uintmax_t transformer_size = 0;
      std::uintmax_t transformer_config_size = 0;

      auto package_artifact = [&](const std::string &artifact_name, bool required) {
        const auto artifact_size = copy_artifact_via_temp_file(
            model_root / artifact_name, package_dir / artifact_name, required);
        if (artifact_name == "regressor.onnx") {
          regressor_size = artifact_size;
        } else if (artifact_name == "classifier.onnx") {
          classifier_size = artifact_size;
        } else if (artifact_name == "transformer.onnx") {
          transformer_size = artifact_size;
        } else if (artifact_name == "transformer_config.json") {
          transformer_config_size = artifact_size;
        }
      };

      if (!is_transformer) {
        for (const auto &artifact_name : required_artifacts) {
          package_artifact(artifact_name, true);
        }
        for (const auto &artifact_name : optional_artifacts) {
          package_artifact(artifact_name, false);
        }
      }

      if (is_transformer) {
        transformer_size = validated_file_size(package_dir / "transformer.onnx");
        transformer_config_size =
            validated_file_size(package_dir / "transformer_config.json");
      }

      const bool has_regressor = regressor_size > 0;
      const bool has_classifier = classifier_size > 0;
      const bool has_transformer = transformer_size > 0;
      const bool has_transformer_config = transformer_config_size > 0;
      const bool artifacts_valid = std::all_of(
          metadata_required_artifacts.begin(), metadata_required_artifacts.end(),
          [&](const std::string &artifact_name) {
            if (artifact_name == "regressor.onnx")
              return has_regressor;
            if (artifact_name == "classifier.onnx")
              return has_classifier;
            if (artifact_name == "transformer.onnx")
              return has_transformer;
            if (artifact_name == "transformer_config.json")
              return has_transformer_config;
            return false;
          });

      if (artifacts_valid) {
        nlohmann::json metrics_json;
        trade::ml::to_json(metrics_json, metrics);
        nlohmann::json metadata = {
            {"model_id", model_id},
            {"model_name", config.model_name},
            {"version_id", version_id},
            {"type", model_type_to_string(config.type)},
            {"trained_at", trained_at},
            {"validation_strategy", metrics.validation_strategy},
            {"feature_set_version", metrics.feature_set_version},
            {"metrics", metrics_json},
            {"artifacts_valid", artifacts_valid},
            {"required_artifacts", metadata_required_artifacts},
            {"artifacts", {{"regressor", has_regressor},
                             {"classifier", has_classifier},
                             {"transformer", has_transformer},
                             {"transformer_config", has_transformer_config}}},
            {"artifact_sizes",
             {{"regressor", regressor_size},
              {"classifier", classifier_size},
              {"transformer", transformer_size},
              {"transformer_config", transformer_config_size}}}};

        std::ofstream meta_file(package_dir / "metadata.json");
        if (!meta_file.is_open()) {
          throw std::runtime_error(
              "Failed to write metadata for trained package: " +
              package_dir.string());
        }
        meta_file << metadata.dump(2);
        meta_file.close();

        if (auto_set_active) {
          bool activated = false;
          if (model_manager_) {
            activated = model_manager_->load_models(package_dir.string());
            if (!activated) {
              TR_LOG_WARN("Trained package '{}' created but could not be activated; keeping current active model",
                          model_id);
              remove_directory_tree(package_dir, "invalid trained model package");
            }
          }

          if (activated) {
            cache.set("ml_active_model_id", model_id);
            cache.set("ml_active_model_name", config.model_name);
            cache.set("ml_active_model_version", version_id);
          }
        }
      } else {
        TR_LOG_WARN("Trained package '{}' is missing required artifacts; removing invalid package",
                    model_id);
        remove_directory_tree(package_dir, "invalid trained model package");
      }

      cache.set_training_status("training", 90);
      TR_LOG_INFO("ML training progress: 90% (packaging completed, reloading models)");

      // Reload models once training is done
      if (model_manager_) {
        model_manager_->reload_models();
      }

      cache.set_training_status("completed", 100);
      TR_LOG_INFO("ML training progress: 100% (completed)");
    } catch (const std::exception &e) {
      TR_LOG_ERROR("Training failed: {}", e.what());
      cache.set_training_status("failed", 0);
      TR_LOG_ERROR("ML training progress: failed");
    }
  });
  training_thread.detach();

  Json::Value resp;
  resp["status"] = "training_started";
  resp["message"] = "Started training process in background";
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::status(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;

  auto [status, progress] = CacheManager::getInstance().get_training_status();
  auto &cache = CacheManager::getInstance();

  Json::Value resp;
  resp["status"] = status;
  resp["progress"] = progress;

  if (const auto model_name = cache.get("ml_active_model_name")) {
    Json::Value current;
    current["model_name"] = *model_name;
    current["version_id"] = cache.get("ml_active_model_version").value_or("");
    resp["current_model"] = current;
  }

  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::performance(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {

  trade::ml::ModelMetrics metrics = CacheManager::getInstance().get_last_metrics();

  // Create a JSON response for the metrics
  nlohmann::json j;
  trade::ml::to_json(j, metrics);

  // Convert nlohmann::json to Json::Value for Drogon
  Json::Value resp;
  Json::Reader reader;
  reader.parse(j.dump(), resp);

  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::availableModels(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;

  Json::Value result(Json::arrayValue);

  try {
    auto &cache = CacheManager::getInstance();
    if (!model_dir_.empty()) {
      namespace fs = std::filesystem;
      fs::path dir(model_dir_);

      auto appendModelIfExists = [&](const std::string &file_name,
                                     const std::string &model_id,
                                     const std::string &display_name,
                                     const std::string &type) {
        fs::path file_path = dir / file_name;
        if (!fs::exists(file_path)) {
          return;
        }

        Json::Value model;
        model["model_id"] = model_id;
        model["model_name"] = display_name;
        model["type"] = type;

        try {
          auto write_time = fs::last_write_time(file_path);
          auto sys_time = std::chrono::time_point_cast<std::chrono::system_clock::duration>(
              write_time - fs::file_time_type::clock::now() +
              std::chrono::system_clock::now());
          std::time_t cftime = std::chrono::system_clock::to_time_t(sys_time);
          std::string ts = std::ctime(&cftime);
          ts.erase(std::remove(ts.begin(), ts.end(), '\n'), ts.end());
          model["trained_at"] = ts;
        } catch (const std::exception &) {
          model["trained_at"] = "unknown";
        }

        result.append(model);
      };

      appendModelIfExists("regressor.onnx", "regressor", "Regressor", "regression");
      appendModelIfExists("classifier.onnx", "classifier", "Classifier", "classification");
      appendModelIfExists("transformer.onnx", "transformer", "Transformer", "sequence");
    }

    if (!trained_models_dir_.empty()) {
      namespace fs = std::filesystem;
      fs::path trained_dir = fs::path(trained_models_dir_);
      if (fs::exists(trained_dir) && fs::is_directory(trained_dir)) {
        for (const auto &entry : fs::directory_iterator(trained_dir)) {
          if (!entry.is_directory()) {
            continue;
          }
          const fs::path meta_path = entry.path() / "metadata.json";
          if (!fs::exists(meta_path)) {
            continue;
          }

          try {
            std::ifstream in(meta_path);
            nlohmann::json meta = nlohmann::json::parse(in, nullptr, true, true);
            if (!meta.is_object()) {
              continue;
            }

            Json::Value model;
            model["model_id"] = meta.value("model_id", entry.path().filename().string());
            model["model_name"] = meta.value("model_name", "Trained Model");
            model["version_id"] = meta.value("version_id", "");
            model["type"] = meta.value("type", "unknown");
            model["trained_at"] = meta.value("trained_at", "");

            const auto package_type =
                model_type_from_string(meta.value("type", "unknown"));
            auto required_artifacts =
                required_artifacts_for(package_type);
            if (meta.contains("required_artifacts") &&
                meta["required_artifacts"].is_array()) {
              required_artifacts.clear();
              for (const auto &artifact : meta["required_artifacts"]) {
                if (artifact.is_string()) {
                  required_artifacts.push_back(artifact.get<std::string>());
                }
              }
            }

            bool valid = !required_artifacts.empty();
            for (const auto &artifact_name : required_artifacts) {
              const fs::path artifact_path = entry.path() / artifact_name;
              if (validated_file_size(artifact_path) == 0) {
                valid = false;
                break;
              }
            }
            if (!valid) {
              continue;
            }

            result.append(model);
          } catch (const std::exception &) {
          }
        }
      }
    }

    callback(HttpResponse::newHttpJsonResponse(result));
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to list available models: {}", e.what());
    Json::Value err;
    err["error"] = e.what();
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k500InternalServerError);
    callback(resp);
  }
}

void PredictController::setActiveModel(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  const std::string model_name = req->getParameter("model_name");
  if (model_name.empty() || !is_safe_model_id(model_name)) {
    Json::Value err;
    err["error"] = model_name.empty() ? "model_name is required"
                                      : "model_name contains invalid characters";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  auto &cache = CacheManager::getInstance();
  std::string selected_name = model_name;
  std::string selected_version;

  try {
    namespace fs = std::filesystem;
    if (!trained_models_dir_.empty()) {
      const fs::path model_root(model_dir_);
      const fs::path package_dir = fs::path(trained_models_dir_) / model_name;
      if (fs::exists(package_dir) && fs::is_directory(package_dir)) {
        const fs::path meta_path = package_dir / "metadata.json";
        if (fs::exists(meta_path)) {
          std::ifstream in(meta_path);
          nlohmann::json meta = nlohmann::json::parse(in, nullptr, true, true);
          selected_name = meta.value("model_name", selected_name);
          selected_version = meta.value("version_id", selected_version);
        }

        bool switched = false;
        if (model_manager_) {
          switched = model_manager_->load_models(package_dir.string());
        }

        if (!switched) {
          Json::Value err;
          err["error"] = "Failed to activate selected model package";
          auto resp = HttpResponse::newHttpJsonResponse(err);
          resp->setStatusCode(k500InternalServerError);
          callback(resp);
          return;
        }
      } else if (model_name == "regressor" || model_name == "classifier" ||
                 model_name == "transformer") {
        if (model_manager_) {
          model_manager_->load_models(model_root.string());
        }
        selected_version.clear();
      }
    }
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to switch model package '{}': {}", model_name, e.what());
  }

  cache.set("ml_active_model_id", model_name);
  cache.set("ml_active_model_name", selected_name);
  cache.set("ml_active_model_version", selected_version);

  Json::Value resp;
  resp["status"] = "success";
  resp["message"] = "Active model updated";
  resp["model_name"] = selected_name;
  resp["version_id"] = selected_version;
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::startSimulatedTrading(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  Json::Value payload = json_req ? *json_req : Json::Value(Json::objectValue);
  if (!payload.isObject()) {
    payload = Json::Value(Json::objectValue);
  }
  const Json::Value parameters = payload.get("parameters", Json::Value(Json::objectValue));
  const std::string execution_mode = payload.get(
      "execution_mode", parameters.get("execution_mode", Json::Value("simulated"))).asString();
  if (execution_mode != "simulated" && execution_mode != "live_parity") {
    Json::Value error;
    error["status"] = "error";
    error["error"] = "execution_mode must be simulated or live_parity";
    auto response = HttpResponse::newHttpJsonResponse(error);
    response->setStatusCode(k400BadRequest);
    callback(response);
    return;
  }
  Json::Value response = trade::trading::SimulatedTradingService::getInstance()
                             .startSession(payload, execution_mode);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::stopSimulatedTrading(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;
  Json::Value response = trade::trading::SimulatedTradingService::getInstance().stopSession();
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::simulatedTradingStatus(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  const std::string session_id = req->getParameter("session_id");
  Json::Value response = trade::trading::SimulatedTradingService::getInstance().getStatus(session_id);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::updateSimulatedStrategyParameters(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  Json::Value payload = json_req ? *json_req : Json::Value(Json::objectValue);
  Json::Value response = trade::trading::SimulatedTradingService::getInstance()
                             .updateStrategyParameters(payload);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::liveOrderBookSignals(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  std::vector<std::string> symbols;
  const std::string symbols_param = req->getParameter("symbols");
  if (!symbols_param.empty()) {
    std::stringstream ss(symbols_param);
    std::string item;
    while (std::getline(ss, item, ',')) {
      if (!item.empty()) {
        symbols.push_back(item);
      }
    }
  }
  const int page = parse_int_param(req->getParameter("page"), 1);
  const int per_page = parse_int_param(req->getParameter("per_page"), 10);
  Json::Value response = trade::trading::LiveTradingService::getInstance()
                             .getOrderBookSignals(symbols, page, per_page);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::simulatedOrderBookSignals(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  std::vector<std::string> symbols;
  std::stringstream ss(req->getParameter("symbols"));
  std::string item;
  while (std::getline(ss, item, ',')) {
    if (!item.empty()) {
      symbols.push_back(item);
    }
  }
  const int page = parse_int_param(req->getParameter("page"), 1);
  const int per_page = parse_int_param(req->getParameter("per_page"), 10);
  Json::Value response = trade::trading::SimulatedTradingService::getInstance()
                             .getOrderBookSignals(symbols, page, per_page);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::livePortfolioStatus(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;

  Json::Value live_portfolio =
      trade::trading::LiveTradingService::getInstance().refreshLivePortfolioStatus();
  if (live_portfolio.get("status", "").asString() == "error") {
    const std::string error = live_portfolio.get("error", "").asString();
    const bool setup_required = error.find("credential") != std::string::npos ||
                                error.find("configured") != std::string::npos;
    live_portfolio["setup_required"] = setup_required;
    auto resp = HttpResponse::newHttpJsonResponse(live_portfolio);
    resp->setStatusCode(setup_required ? k400BadRequest : k502BadGateway);
    callback(resp);
  } else {
    callback(HttpResponse::newHttpJsonResponse(live_portfolio));
  }
}

void PredictController::executeLiveTrade(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  if (!json_req || !json_req->isObject()) {
    Json::Value err;
    err["error"] = "JSON body with symbol, side, and amount is required";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }
  Json::Value response =
      trade::trading::LiveTradingService::getInstance().submitLiveOrder(*json_req);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::livePortfolioPositions(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;
  Json::Value response = trade::trading::LiveTradingService::getInstance().getOpenPositions();
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::closeLivePosition(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  const std::string symbol = json_req && json_req->isMember("symbol")
                                 ? (*json_req)["symbol"].asString()
                                 : req->getParameter("symbol");
  if (symbol.empty()) {
    Json::Value err;
    err["status"] = "error";
    err["error"] = "symbol is required";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  Json::Value response = trade::trading::LiveTradingService::getInstance().closePosition(symbol);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::liquidateLiveHoldings(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  Json::Value payload = json_req ? *json_req : Json::Value(Json::objectValue);
  if (!payload.isObject()) {
    payload = Json::Value(Json::objectValue);
  }
  Json::Value response =
      trade::trading::LiveTradingService::getInstance().liquidateCoinbaseHoldings(payload);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::startLiveTrading(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  Json::Value payload = json_req ? *json_req : Json::Value(Json::objectValue);
  if (!payload.isObject()) {
    payload = Json::Value(Json::objectValue);
  }
  Json::Value response = trade::trading::LiveTradingService::getInstance().startSession(payload);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::stopLiveTrading(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;
  Json::Value response = trade::trading::LiveTradingService::getInstance().stopSession();
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::liveTradingStatus(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  const std::string session_id = req->getParameter("session_id");
  Json::Value response = trade::trading::LiveTradingService::getInstance().getStatus(session_id);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::updateLiveStrategyParameters(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  Json::Value payload = json_req ? *json_req : Json::Value(Json::objectValue);
  Json::Value response = trade::trading::LiveTradingService::getInstance()
                             .updateStrategyParameters(payload);
  callback(HttpResponse::newHttpJsonResponse(response));
}

void PredictController::products(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;

  Json::Value categories(Json::objectValue);
  const std::vector<std::string> major = {
      "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD", "XRP-USD", "LTC-USD"};
  const std::vector<std::string> all_usd = {
      "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD", "XRP-USD",
      "LTC-USD", "AVAX-USD", "DOGE-USD", "LINK-USD", "MATIC-USD", "ATOM-USD",
      "UNI-USD", "AAVE-USD", "ALGO-USD", "BCH-USD", "ETC-USD", "FIL-USD"};

  Json::Value major_json(Json::arrayValue);
  for (const auto &symbol : major) {
    major_json.append(symbol);
  }
  Json::Value all_usd_json(Json::arrayValue);
  for (const auto &symbol : all_usd) {
    all_usd_json.append(symbol);
  }
  categories["major"] = major_json;
  categories["all_usd"] = all_usd_json;
  categories["all_products"] = all_usd_json;

  Json::Value resp;
  resp["categories"] = categories;
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::logMessage(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  const std::string message = json_req && json_req->isMember("message")
                                  ? (*json_req)["message"].asString()
                                  : "";
  if (!message.empty()) {
    TR_LOG_INFO("frontend: {}", message);
  }

  Json::Value resp;
  resp["status"] = "success";
  callback(HttpResponse::newHttpJsonResponse(resp));
}

namespace {

Json::Value defaultMlConfig() {
  Json::Value config(Json::objectValue);
  config["continuous_training_enabled"] = false;
  config["training_interval"] = 3600;
  config["new_data_threshold"] = 100;
  return config;
}

Json::Value loadMlConfig() {
  Json::Value config = defaultMlConfig();
  const auto stored = CacheManager::getInstance().get("ml_config");
  if (!stored) {
    return config;
  }

  Json::Value parsed;
  Json::CharReaderBuilder builder;
  std::string errs;
  std::istringstream stream(*stored);
  if (Json::parseFromStream(builder, stream, &parsed, &errs) && parsed.isObject()) {
    for (const auto &member : parsed.getMemberNames()) {
      config[member] = parsed[member];
    }
  }
  return config;
}

} // namespace

void PredictController::getMlConfig(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;
  callback(HttpResponse::newHttpJsonResponse(loadMlConfig()));
}

void PredictController::updateMlConfig(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  if (!json_req || !json_req->isObject()) {
    Json::Value err;
    err["error"] = "JSON object body is required";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  Json::Value config = loadMlConfig();
  for (const auto &member : json_req->getMemberNames()) {
    config[member] = (*json_req)[member];
  }

  Json::StreamWriterBuilder writer;
  writer["indentation"] = "";
  CacheManager::getInstance().set("ml_config", Json::writeString(writer, config));

  Json::Value resp = config;
  resp["status"] = "success";
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::pnlTrades(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  const std::string sort_by = req->getParameter("sort_by") == "pnl_percent"
                                  ? "pnl / NULLIF(ABS(price * size), 0)"
                                  : "pnl";

  Json::Value resp;
  resp["top_trades"] = Json::arrayValue;
  resp["bottom_trades"] = Json::arrayValue;

  try {
    auto exists = DatabaseManager::getInstance().query(
        "SELECT to_regclass('public.individual_trades') AS relname");
    if (exists.empty() || exists[0]["relname"].is_null()) {
      callback(HttpResponse::newHttpJsonResponse(resp));
      return;
    }

    auto rowToJson = [](const pqxx::row &row) {
      Json::Value trade;
      trade["symbol"] = row["symbol"].is_null() ? "" : row["symbol"].c_str();
      trade["side"] = row["side"].is_null() ? "" : row["side"].c_str();
      const double pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
      const double size = row["size"].is_null() ? 0.0 : row["size"].as<double>();
      const double price = row["price"].is_null() ? 0.0 : row["price"].as<double>();
      trade["pnl"] = pnl;
      const double notional = std::abs(price * size);
      trade["pnl_percent"] = notional > 0.0 ? (pnl / notional) * 100.0 : 0.0;
      trade["timestamp"] =
          row["timestamp"].is_null() ? Json::Value(0) : Json::Value(static_cast<Json::Int64>(row["timestamp"].as<long long>()));
      return trade;
    };

    const std::string base =
        "SELECT symbol, side, size, price, timestamp, pnl FROM individual_trades "
        "WHERE pnl IS NOT NULL AND pnl <> 0 ORDER BY " + sort_by;
    for (const auto &row : DatabaseManager::getInstance().query(base + " DESC LIMIT 10")) {
      resp["top_trades"].append(rowToJson(row));
    }
    for (const auto &row : DatabaseManager::getInstance().query(base + " ASC LIMIT 10")) {
      resp["bottom_trades"].append(rowToJson(row));
    }
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to fetch PnL trades: {}", e.what());
  }

  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::predictionComparison(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto json_req = req->getJsonObject();
  if (!json_req || !(*json_req)["model_ids"].isArray()) {
    Json::Value err;
    err["error"] = "model_ids array is required";
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  std::vector<double> pca_features;
  std::vector<std::vector<double>> sequence;
  try {
    Json::StreamWriterBuilder builder;
    auto features_json =
        nlohmann::json::parse(Json::writeString(builder, (*json_req)["features"]));
    ml::OrderBookFeatures features;
    ml::from_json(features_json, features);
    if (!feature_engineer_) {
      throw std::runtime_error("feature engineering is not initialized");
    }
    pca_features = feature_engineer_->preprocess(features);
    sequence = feature_engineer_->get_transformer_sequence(features.symbol);
  } catch (const std::exception &e) {
    Json::Value err;
    err["error"] = std::string("Invalid features payload: ") + e.what();
    auto resp = HttpResponse::newHttpJsonResponse(err);
    resp->setStatusCode(k400BadRequest);
    callback(resp);
    return;
  }

  Json::Value comparisons(Json::arrayValue);
  for (const auto &model_id_json : (*json_req)["model_ids"]) {
    if (!model_id_json.isString()) {
      continue;
    }
    const std::string model_id = model_id_json.asString();

    Json::Value comparison;
    comparison["model_name"] = model_id;
    comparison["version_id"] = "";

    if (!is_safe_model_id(model_id)) {
      comparison["error"] = "invalid model id";
      comparisons.append(comparison);
      continue;
    }

    try {
      namespace fs = std::filesystem;
      fs::path package_dir;
      if (model_id == "regressor" || model_id == "classifier" || model_id == "transformer") {
        package_dir = fs::path(model_dir_);
      } else {
        package_dir = fs::path(trained_models_dir_) / model_id;
        const fs::path meta_path = package_dir / "metadata.json";
        if (fs::exists(meta_path)) {
          std::ifstream in(meta_path);
          nlohmann::json meta = nlohmann::json::parse(in, nullptr, true, true);
          comparison["model_name"] = meta.value("model_name", model_id);
          comparison["version_id"] = meta.value("version_id", "");
        }
      }

      ml::ONNXModelManager candidate;
      if (!candidate.load_models(package_dir.string())) {
        throw std::runtime_error("failed to load model package");
      }

      const double win_prob =
          candidate.has_classifier() ? candidate.predict_win_prob(pca_features) : 0.5;
      double expected_return = 0.0;
      if (candidate.has_regressor()) {
        expected_return = candidate.predict_pnl(pca_features);
      } else if (candidate.has_transformer()) {
        expected_return = candidate.predict_transformer(sequence);
      }

      comparison["win_probability"] = std::clamp(win_prob, 0.0, 1.0);
      comparison["expected_return"] = expected_return;
      comparison["confidence"] = std::clamp(std::abs(win_prob - 0.5) * 2.0, 0.0, 1.0);
    } catch (const std::exception &e) {
      comparison["error"] = e.what();
    }

    comparisons.append(comparison);
  }

  Json::Value resp;
  resp["comparisons"] = comparisons;
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::resetMlDatabases(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  (void)req;

  Json::Value resp;
  try {
    for (const char *table : {"individual_trades", "order_book_signals"}) {
      const std::string qualified = std::string("public.") + table;
      auto exists = DatabaseManager::getInstance().query(
          "SELECT to_regclass('" + qualified + "') AS relname");
      if (!exists.empty() && !exists[0]["relname"].is_null()) {
        DatabaseManager::getInstance().query(std::string("TRUNCATE TABLE ") + table);
        resp["cleared"].append(table);
      }
    }
    resp["status"] = "success";
  } catch (const std::exception &e) {
    resp["status"] = "error";
    resp["error"] = e.what();
    auto error_resp = HttpResponse::newHttpJsonResponse(resp);
    error_resp->setStatusCode(k500InternalServerError);
    callback(error_resp);
    return;
  }

  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::executionReconciliation(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  using trade::trading::OutcomeAttribution;
  using trade::trading::SignalAttribution;

  const std::string session_id = sanitize_sql_literal(req->getParameter("session_id"));
  const std::string trade_type = sanitize_sql_literal(req->getParameter("trade_type"));
  const int hours = clamp_int(parse_int_param(req->getParameter("hours"), 24), 1, 24 * 30);
  const int max_signals =
      clamp_int(parse_int_param(req->getParameter("max_signals"), 20000), 100, 200000);
  const long long window_start =
      static_cast<long long>(std::time(nullptr)) - static_cast<long long>(hours) * 3600LL;

  Json::Value resp;
  resp["window_hours"] = hours;
  resp["window_start_timestamp"] = static_cast<Json::Int64>(window_start);
  resp["session_id"] = session_id;
  resp["trade_type"] = trade_type;
  resp["signal_rows"] = 0;
  resp["outcome_rows"] = 0;
  resp["signal_rows_truncated"] = false;
  resp["by_strategy"] = Json::arrayValue;

  std::vector<SignalAttribution> signals;
  std::vector<OutcomeAttribution> outcomes;

  try {
    auto tableExists = [](const char *table) {
      auto exists = DatabaseManager::getInstance().query(
          std::string("SELECT to_regclass('public.") + table + "') AS relname");
      return !exists.empty() && !exists[0]["relname"].is_null();
    };

    if (tableExists("order_book_signals")) {
      constexpr std::size_t kSignalPageSize = 5000;
      std::size_t page_offset = 0;
      std::size_t fetched = 0;
      bool exhausted = false;
      while (!exhausted && !resp["signal_rows_truncated"].asBool()) {
        std::ostringstream sql;
        sql << "SELECT symbol, signal_type, signal_data FROM order_book_signals WHERE timestamp >= "
            << window_start;
        if (!session_id.empty()) {
          sql << " AND session_id = '" << session_id << "'";
        }
        sql << " ORDER BY timestamp DESC LIMIT " << kSignalPageSize << " OFFSET " << page_offset;

        const auto rows = DatabaseManager::getInstance().query(sql.str());
        exhausted = rows.size() < kSignalPageSize;
        for (const auto &row : rows) {
          const Json::Value payload =
              row["signal_data"].is_null() ? Json::Value(Json::objectValue)
                                           : parse_json_object(row["signal_data"].c_str());
          if (!trade_type.empty() &&
              payload.get("trade_type", Json::Value("")).asString() != trade_type) {
            continue;
          }
          if (++fetched > static_cast<std::size_t>(max_signals)) {
            resp["signal_rows_truncated"] = true;
            break;
          }
          const Json::Value analysis =
              payload.get("execution_analysis", Json::Value(Json::objectValue));

          SignalAttribution attribution;
          attribution.symbol = row["symbol"].is_null() ? "" : row["symbol"].c_str();
          attribution.strategy = analysis.get("strategy", Json::Value("")).asString();
          const std::string signal_type =
              row["signal_type"].is_null() ? "" : row["signal_type"].c_str();
          attribution.signal_generated =
              analysis.isMember("signal_generated")
                  ? analysis["signal_generated"].asBool()
                  : (!signal_type.empty() && signal_type != "hold");
          attribution.executable_intent =
              analysis.get("executable_intent", Json::Value(false)).asBool();
          attribution.blocker_reason = analysis.get("blocker_reason", Json::Value("")).asString();
          attribution.intended_side = analysis.get("intended_side", Json::Value("")).asString();
          attribution.diagnostic_factor =
              analysis.get("diagnostic_factor", Json::Value("")).asString();
          attribution.expected_return = analysis.get("expected_return", Json::Value(0.0)).asDouble();
          attribution.fee_adjusted_expected_return =
              analysis.get("fee_adjusted_expected_return", Json::Value(0.0)).asDouble();
          signals.push_back(std::move(attribution));
        }
        page_offset += rows.size();
      }
    }

    if (tableExists("individual_trades")) {
      std::ostringstream sql;
      sql << "SELECT symbol, strategy_type, pnl, fees, is_closing_leg FROM individual_trades WHERE timestamp >= "
          << window_start;
      if (!session_id.empty()) {
        sql << " AND session_id = '" << session_id << "'";
      }
      if (!trade_type.empty()) {
        sql << " AND trade_type = '" << trade_type << "'";
      }
      for (const auto &row : DatabaseManager::getInstance().query(sql.str())) {
        OutcomeAttribution outcome;
        outcome.symbol = row["symbol"].is_null() ? "" : row["symbol"].c_str();
        outcome.strategy = row["strategy_type"].is_null() ? "" : row["strategy_type"].c_str();
        const double gross_pnl = row["pnl"].is_null() ? 0.0 : row["pnl"].as<double>();
        outcome.fees = row["fees"].is_null() ? 0.0 : row["fees"].as<double>();
        // New rows persist the leg explicitly, including exact-flat exits.
        // Fall back to the historical non-zero-PnL convention for rows written
        // before the column was introduced. Realized PnL is reported net of
        // fees to match the objective's after-fee expectancy definition.
        outcome.is_closing_leg = row["is_closing_leg"].is_null()
                                     ? gross_pnl != 0.0
                                     : row["is_closing_leg"].as<bool>();
        outcome.realized_pnl = outcome.is_closing_leg ? gross_pnl - outcome.fees : 0.0;
        outcomes.push_back(std::move(outcome));
      }
    }
  } catch (const std::exception &e) {
    TR_LOG_WARN("Failed to build execution reconciliation: {}", e.what());
    resp["error"] = e.what();
  }

  resp["signal_rows"] = static_cast<Json::UInt64>(signals.size());
  resp["outcome_rows"] = static_cast<Json::UInt64>(outcomes.size());

  const auto report = trade::trading::reconcileExecution(signals, outcomes);
  for (const auto &[strategy, metrics] : report.by_strategy) {
    resp["by_strategy"].append(reconciliation_to_json(metrics));
  }
  resp["by_symbol"] = Json::arrayValue;
  for (const auto &[symbol, metrics] : report.by_symbol) {
    Json::Value row = reconciliation_to_json(metrics);
    row["symbol"] = symbol;
    resp["by_symbol"].append(row);
  }
  resp["overall"] = reconciliation_to_json(report.overall);

  callback(HttpResponse::newHttpJsonResponse(resp));
}

} // namespace api
