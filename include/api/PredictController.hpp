
#pragma once
#include "ml/FeatureEngineer.hpp"
#include "ml/ONNXModelManager.hpp"
#include <drogon/HttpController.h>
#include <memory>

using namespace drogon;

namespace api {

class PredictController : public drogon::HttpController<PredictController> {
public:
  METHOD_LIST_BEGIN
  ADD_METHOD_TO(PredictController::predict, "/predict", Post);
  ADD_METHOD_TO(PredictController::train, "/ml/train", Post);
  ADD_METHOD_TO(PredictController::status, "/ml/status", Get);
  ADD_METHOD_TO(PredictController::performance, "/ml/performance", Get);
  METHOD_LIST_END

  void predict(const HttpRequestPtr &req,
               std::function<void(const HttpResponsePtr &)> &&callback);

  void train(const HttpRequestPtr &req,
             std::function<void(const HttpResponsePtr &)> &&callback);

  void status(const HttpRequestPtr &req,
              std::function<void(const HttpResponsePtr &)> &&callback);

  void performance(const HttpRequestPtr &req,
                   std::function<void(const HttpResponsePtr &)> &&callback);

  static void init(const std::string &param_path, const std::string &model_dir);

private:
  static std::unique_ptr<ml::FeatureEngineer> feature_engineer_;
  static std::unique_ptr<ml::ONNXModelManager> model_manager_;
};

} // namespace api
