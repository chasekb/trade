
#include "api/PredictController.hpp"
#include "cache/CacheManager.hpp"
#include "config/Config.hpp"
#include "ml/ModelTrainer.hpp"
#include "ml/Types.hpp"
#include "trading/TradingStatsService.hpp"
#include "utils/Logger.hpp"
#include <chrono>
#include <algorithm>
#include <cctype>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
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

bool copy_if_exists(const std::filesystem::path &src,
                    const std::filesystem::path &dst) {
  try {
    if (!std::filesystem::exists(src)) {
      return false;
    }
    std::filesystem::create_directories(dst.parent_path());
    std::filesystem::copy_file(src, dst,
                               std::filesystem::copy_options::overwrite_existing);
    return true;
  } catch (const std::exception &) {
    return false;
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

    std::error_code ec;
    fs::create_directories(fs::path(trained_models_dir_), ec);
    if (ec) {
      const fs::path fallback("/tmp/trade_trained_models");
      ec.clear();
      fs::create_directories(fallback, ec);
      if (!ec) {
        trained_models_dir_ = fallback.string();
        TR_LOG_WARN("Configured trained-model path unavailable; falling back to {}",
                    trained_models_dir_);
      } else {
        TR_LOG_ERROR("Unable to create trained model directory at '{}' and fallback '{}': {}",
                     trained_models_dir_, fallback.string(), ec.message());
      }
    }
  }

  feature_engineer_ = std::make_unique<ml::FeatureEngineer>();
  if (!feature_engineer_->load_parameters(param_path)) {
    TR_LOG_ERROR("Failed to load feature engineer parameters from {}",
                 param_path);
  }

  model_manager_ = std::make_unique<ml::ONNXModelManager>();
  if (!model_manager_->load_models(model_dir)) {
    TR_LOG_ERROR("Failed to load ONNX models from {}", model_dir);
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

    if (!feature_engineer_ || !model_manager_ || !model_manager_->is_ready()) {
      Json::Value err;
      err["error"] = "ML services not initialized";
      auto resp = HttpResponse::newHttpJsonResponse(err);
      resp->setStatusCode(k503ServiceUnavailable);
      callback(resp);
      return;
    }

    // Run Preprocessing
    auto pca_features = feature_engineer_->preprocess(features);

    // Run Inference
    double pnl = model_manager_->predict_pnl(pca_features);
    double win_prob = model_manager_->predict_win_prob(pca_features);

    // Phase 6: Transformer Prediction
    auto sequence = feature_engineer_->get_transformer_sequence();
    double transformer_pnl = model_manager_->predict_transformer(sequence);

    Json::Value result;
    result["expected_pnl"] = pnl;
    result["transformer_pnl"] = transformer_pnl;
    result["win_probability"] = win_prob;
    result["confidence"] = std::abs(win_prob - 0.5) * 2.0;
    result["timestamp"] = (Json::Int64)features.timestamp;

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
  (void)req;

  const auto stats = trade::trading::TradingStatsService().getTradingStats();

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
      const std::string model_id = config.model_name + ":" + version_id;

      const std::filesystem::path model_root(PredictController::model_dir_);
      const std::filesystem::path trained_root(PredictController::trained_models_dir_);
      if (trained_root.empty()) {
        throw std::runtime_error("trained models directory is not configured");
      }
      const std::filesystem::path package_dir = trained_root / model_id;
      std::filesystem::create_directories(package_dir);

      const bool has_regressor = copy_if_exists(model_root / "regressor.onnx",
                                                package_dir / "regressor.onnx");
      const bool has_classifier = copy_if_exists(model_root / "classifier.onnx",
                                                 package_dir / "classifier.onnx");
      const bool has_transformer = copy_if_exists(model_root / "transformer.onnx",
                                                  package_dir / "transformer.onnx");

      nlohmann::json metadata = {
          {"model_id", model_id},
          {"model_name", config.model_name},
          {"version_id", version_id},
          {"type", model_type_to_string(config.type)},
          {"trained_at", trained_at},
          {"artifacts", {{"regressor", has_regressor},
                           {"classifier", has_classifier},
                           {"transformer", has_transformer}}}};

      std::ofstream meta_file(package_dir / "metadata.json");
      meta_file << metadata.dump(2);
      meta_file.close();

      if (auto_set_active) {
        if (model_manager_) {
          model_manager_->load_models(package_dir.string());
        }
        cache.set("ml_active_model_id", model_id);
        cache.set("ml_active_model_name", config.model_name);
        cache.set("ml_active_model_version", version_id);
      }

      cache.set_training_status("training", 90);
      TR_LOG_INFO("ML training progress: 90% (training completed, reloading models)");

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
  if (model_name.empty()) {
    Json::Value err;
    err["error"] = "model_name is required";
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

        if (model_manager_) {
          model_manager_->load_models(package_dir.string());
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

} // namespace api
