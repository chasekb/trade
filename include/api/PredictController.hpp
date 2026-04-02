#pragma once
#include "ml/FeatureEngineer.hpp"
#include "ml/ONNXModelManager.hpp"
#include <drogon/HttpController.h>
#include <memory>
#include <string>

using namespace drogon;

namespace api {

class PredictController : public drogon::HttpController<PredictController> {
public:
  METHOD_LIST_BEGIN
  ADD_METHOD_TO(PredictController::predict, "/predict", Post);
  ADD_METHOD_TO(PredictController::tradingStats, "/api/trades/stats", Get);
  ADD_METHOD_TO(PredictController::train, "/ml/train", Post);
  ADD_METHOD_TO(PredictController::train, "/api/ml/train", Post);
  ADD_METHOD_TO(PredictController::status, "/ml/status", Get);
  ADD_METHOD_TO(PredictController::status, "/api/ml/status", Get);
  ADD_METHOD_TO(PredictController::performance, "/ml/performance", Get);
  ADD_METHOD_TO(PredictController::performance, "/api/ml/performance", Get);
  ADD_METHOD_TO(PredictController::availableModels, "/api/ml/models", Get);
  ADD_METHOD_TO(PredictController::setActiveModel, "/api/ml/models/set_active", Post);
  METHOD_LIST_END

  void predict(const HttpRequestPtr &req,
               std::function<void(const HttpResponsePtr &)> &&callback);

  void tradingStats(const HttpRequestPtr &req,
                    std::function<void(const HttpResponsePtr &)> &&callback);

  void train(const HttpRequestPtr &req,
             std::function<void(const HttpResponsePtr &)> &&callback);

  void status(const HttpRequestPtr &req,
              std::function<void(const HttpResponsePtr &)> &&callback);

  void performance(const HttpRequestPtr &req,
                   std::function<void(const HttpResponsePtr &)> &&callback);

  void availableModels(const HttpRequestPtr &req,
                       std::function<void(const HttpResponsePtr &)> &&callback);

  void setActiveModel(const HttpRequestPtr &req,
                      std::function<void(const HttpResponsePtr &)> &&callback);

  static void init(const std::string &param_path, const std::string &model_dir);

private:
  static std::unique_ptr<ml::FeatureEngineer> feature_engineer_;
  static std::unique_ptr<ml::ONNXModelManager> model_manager_;
  static std::string model_dir_;
};

} // namespace api
