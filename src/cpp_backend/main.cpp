#include "include/api/PredictController.hpp"
#include "include/cache/CacheManager.hpp"
#include "include/config/Config.hpp"
#include "include/db/DatabaseManager.hpp"
#include "include/utils/Logger.hpp"
#include <drogon/drogon.h>
#include <string>

int main() {
  // 1. Load configuration from .env
  auto &config = Config::getInstance();
  config.loadEnv(".env");

  // 2. Initialize logger
  Logger::init(config.get("LOG_LEVEL", "info"));
  LOG_INFO("Trading Bot C++ Backend starting...");

  // 3. Initialize database
  if (!DatabaseManager::getInstance().init()) {
    LOG_WARN(
        "Could not connect to PostgreSQL database. Continuing without DB.");
  }

  // 4. Initialize Redis cache
  if (!CacheManager::getInstance().init()) {
    LOG_WARN("Could not connect to Redis. Continuing without cache.");
  }

  // 5. Initialize ML Services
  std::string model_dir = config.get("MODEL_DIR", "data/onnx");
  std::string param_path =
      config.get("FEATURE_PARAMS_PATH", "data/cpp_assets/feature_params.json");
  api::PredictController::init(param_path, model_dir);

  // 6. Register health endpoint
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
  LOG_INFO("Server listening on port {}", port);

  drogon::app().addListener("0.0.0.0", port).setThreadNum(4).run();

  return 0;
}
