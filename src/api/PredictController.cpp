
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
#include <nlohmann/json.hpp>
#include <thread>

namespace api {

std::unique_ptr<ml::FeatureEngineer> PredictController::feature_engineer_ =
    nullptr;
std::unique_ptr<ml::ONNXModelManager> PredictController::model_manager_ =
    nullptr;

void PredictController::init(const std::string &param_path,
                             const std::string &model_dir) {
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
  if (!json_req) {
    Json::Value err;
    err["error"] = "Invalid JSON";
    callback(HttpResponse::newHttpJsonResponse(err));
    return;
  }

  nlohmann::json payload;
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

  trade::ml::TrainingConfig config;
  config.epochs = payload.value("epochs", config.epochs);
  config.learning_rate = payload.value("learning_rate", config.learning_rate);
  config.batch_size = payload.value("batch_size", config.batch_size);
  config.test_split = payload.value("test_split", config.test_split);
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

  auto &cfg = Config::getInstance();
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
  std::thread training_thread([config, db_url]() {
    auto &cache = CacheManager::getInstance();
    cache.set_training_status("training", 10); // Started

    try {
      auto collector = std::make_shared<trade::ml::DataCollector>(db_url);
      trade::ml::ModelTrainer trainer(collector);

      cache.set_training_status("training", 50); // Mid-way
      trade::ml::ModelMetrics metrics = trainer.train(config);
      cache.set_last_metrics(metrics);
      cache.set_training_status("training", 90);

      // Reload models once training is done
      if (model_manager_) {
        model_manager_->reload_models();
      }

      cache.set_training_status("completed", 100);
    } catch (const std::exception &e) {
      TR_LOG_ERROR("Training failed: {}", e.what());
      cache.set_training_status("failed", 0);
    }
  });
  training_thread.detach();

  Json::Value resp;
  resp["status"] = "Started training process in background";
  callback(HttpResponse::newHttpJsonResponse(resp));
}

void PredictController::status(
    const HttpRequestPtr &req,
    std::function<void(const HttpResponsePtr &)> &&callback) {
  auto [status, progress] = CacheManager::getInstance().get_training_status();

  Json::Value resp;
  resp["status"] = status;
  resp["progress"] = progress;
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

} // namespace api
