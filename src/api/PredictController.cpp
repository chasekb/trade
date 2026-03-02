
#include "api/PredictController.hpp"
#include "cache/CacheManager.hpp"
#include "ml/Types.hpp"
#include "utils/Logger.hpp"
#include <chrono>
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

  // Phase 3 Orchestration: Trigger training in a background thread
  std::thread training_thread([]() {
    auto &cache = CacheManager::getInstance();
    cache.set_training_status("training", 10); // Started

    try {
      // In a real scenario, we'd use a ModelTrainer instance here
      // auto trainer = std::make_unique<ml::ModelTrainer>(...);
      // trainer->train(config);

      // For now, simulate training
      std::this_thread::sleep_for(std::chrono::seconds(5));
      cache.set_training_status("training", 50); // Mid-way
      std::this_thread::sleep_for(std::chrono::seconds(5));

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

  ml::ModelMetrics metrics = CacheManager::getInstance().get_last_metrics();

  // Create a JSON response for the metrics
  nlohmann::json j;
  ml::to_json(j, metrics);

  // Convert nlohmann::json to Json::Value for Drogon
  Json::Value resp;
  Json::Reader reader;
  reader.parse(j.dump(), resp);

  callback(HttpResponse::newHttpJsonResponse(resp));
}

} // namespace api
