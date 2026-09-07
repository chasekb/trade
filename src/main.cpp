#include "api/PredictController.hpp"
#include "cache/CacheManager.hpp"
#include "config/Config.hpp"
#include "db/DatabaseManager.hpp"
#include "utils/Logger.hpp"
#include <drogon/drogon.h>
#include <functional>
#include <string>

namespace {

Json::Value makeDefaultProductsResponse() {
  Json::Value categories(Json::objectValue);

  Json::Value major(Json::arrayValue);
  major.append("BTC-USD");
  major.append("ETH-USD");
  major.append("SOL-USD");
  major.append("ADA-USD");
  major.append("DOT-USD");
  major.append("XRP-USD");
  major.append("LTC-USD");

  Json::Value crypto(Json::arrayValue);
  crypto.append("BTC-USD");
  crypto.append("ETH-USD");
  crypto.append("ADA-USD");
  crypto.append("SOL-USD");
  crypto.append("DOT-USD");
  crypto.append("XRP-USD");

  categories["all_products"] = major;
  categories["all_usd"] = major;
  categories["major"] = major;
  categories["crypto"] = crypto;
  categories["all_eur"] = Json::Value(Json::arrayValue);
  categories["all_usdt"] = Json::Value(Json::arrayValue);
  categories["all_btc"] = Json::Value(Json::arrayValue);
  categories["minor"] = Json::Value(Json::arrayValue);

  Json::Value response(Json::objectValue);
  response["categories"] = categories;
  return response;
}

Json::Value makeDefaultMlConfig() {
  Json::Value config(Json::objectValue);
  config["continuous_training_enabled"] = false;
  config["training_interval"] = 3600;
  config["new_data_threshold"] = 100;
  config["batch_training_enabled"] = true;
  config["batch_size"] = 1000;
  return config;
}

Json::Value loadMlConfigFromCacheOrDefault() {
  auto cached = CacheManager::getInstance().get("ml_config");
  if (!cached || cached->empty()) {
    return makeDefaultMlConfig();
  }

  Json::CharReaderBuilder builder;
  builder["collectComments"] = false;
  Json::Value config;
  std::string errors;
  std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
  if (reader && reader->parse(cached->data(), cached->data() + cached->size(), &config, &errors) && config.isObject()) {
    Json::Value merged = makeDefaultMlConfig();
    for (const auto &key : {"continuous_training_enabled", "training_interval", "new_data_threshold", "batch_training_enabled", "batch_size"}) {
      if (config.isMember(key)) {
        merged[key] = config[key];
      }
    }
    return merged;
  }

  return makeDefaultMlConfig();
}

void persistMlConfig(const Json::Value &config) {
  Json::StreamWriterBuilder writer;
  writer["indentation"] = "";
  CacheManager::getInstance().set("ml_config", Json::writeString(writer, config));
}

} // namespace

int main() {
  // 1. Load configuration from .env
  auto &config = Config::getInstance();
  config.loadEnv(".env");

  // 2. Initialize logger
  Logger::init(config.get("LOG_LEVEL", "info"));
  TR_LOG_INFO("Trading Bot C++ Backend starting...");

  // 3. Initialize database
  if (!DatabaseManager::getInstance().init()) {
    TR_LOG_WARN(
        "Could not connect to PostgreSQL database. Continuing without DB.");
  }

  // 4. Initialize Redis cache
  if (!CacheManager::getInstance().init()) {
    TR_LOG_WARN("Could not connect to Redis. Continuing without cache.");
  }

  // 5. Initialize ML Services
  std::string model_dir = config.get("MODEL_DIR", "data/onnx");
  std::string param_path =
      config.get("FEATURE_PARAMS_PATH", "data/cpp_assets/feature_params.json");
  api::PredictController::init(param_path, model_dir);

  // 6. Register compatibility endpoints for the frontend dev stack
  drogon::app().registerHandler(
      "/api/health",
      [](const drogon::HttpRequestPtr &,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        Json::Value json;
        json["status"] = "healthy";
        json["service"] = "trading-bot-cpp-backend";
        json["version"] = "0.1.0";
        callback(drogon::HttpResponse::newHttpJsonResponse(json));
      },
      {drogon::Get});

  drogon::app().registerHandler(
      "/api/products",
      [](const drogon::HttpRequestPtr &,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        callback(drogon::HttpResponse::newHttpJsonResponse(makeDefaultProductsResponse()));
      },
      {drogon::Get});

  drogon::app().registerHandler(
      "/api/log",
      [](const drogon::HttpRequestPtr &req,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        auto json_req = req->getJsonObject();
        if (json_req && json_req->isObject() && json_req->isMember("message") &&
            (*json_req)["message"].isString()) {
          TR_LOG_INFO("frontend log: {}", (*json_req)["message"].asString());
        } else {
          TR_LOG_INFO("frontend log event received");
        }
        Json::Value resp;
        resp["status"] = "ok";
        callback(drogon::HttpResponse::newHttpJsonResponse(resp));
      },
      {drogon::Post});

  drogon::app().registerHandler(
      "/api/ml/config",
      [](const drogon::HttpRequestPtr &,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        callback(drogon::HttpResponse::newHttpJsonResponse(loadMlConfigFromCacheOrDefault()));
      },
      {drogon::Get});

  drogon::app().registerHandler(
      "/api/ml/config",
      [](const drogon::HttpRequestPtr &req,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        auto json_req = req->getJsonObject();
        if (!json_req || !json_req->isObject()) {
          Json::Value err;
          err["error"] = "Request body must be a JSON object";
          auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
          resp->setStatusCode(drogon::k400BadRequest);
          callback(resp);
          return;
        }

        Json::Value config = loadMlConfigFromCacheOrDefault();
        for (const auto &key : {"continuous_training_enabled", "training_interval", "new_data_threshold", "batch_training_enabled", "batch_size"}) {
          if (json_req->isMember(key)) {
            config[key] = (*json_req)[key];
          }
        }

        persistMlConfig(config);
        callback(drogon::HttpResponse::newHttpJsonResponse(config));
      },
      {drogon::Post});

  // 7. Register health endpoint
  drogon::app().registerHandler(
      "/health",
      [](const drogon::HttpRequestPtr &,
         std::function<void(const drogon::HttpResponsePtr &)> &&callback) {
        Json::Value json;
        json["status"] = "healthy";
        json["service"] = "trading-bot-cpp-backend";
        json["version"] = "0.1.0";
        callback(drogon::HttpResponse::newHttpJsonResponse(json));
      },
      {drogon::Get});

  int port = Config::getInstance().getInt("PORT", 8080);
  TR_LOG_INFO("Server listening on port {}", port);

  drogon::app().addListener("0.0.0.0", port).setThreadNum(4).run();

  return 0;
}
