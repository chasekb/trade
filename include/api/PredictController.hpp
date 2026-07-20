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
  ADD_METHOD_TO(PredictController::startSimulatedTrading, "/api/trading/simulated/start", Post);
  ADD_METHOD_TO(PredictController::startSimulatedTrading, "/api/simulated-trading/start", Post);
  ADD_METHOD_TO(PredictController::stopSimulatedTrading, "/api/trading/simulated/stop", Post);
  ADD_METHOD_TO(PredictController::stopSimulatedTrading, "/api/simulated-trading/stop", Post);
  ADD_METHOD_TO(PredictController::simulatedTradingStatus, "/api/simulated-trading/status", Get);
  ADD_METHOD_TO(PredictController::simulatedTradingStatus, "/api/trading/simulated/status", Get);
  ADD_METHOD_TO(PredictController::updateSimulatedStrategyParameters, "/api/trading/simulated/update-strategy-params", Post);
  ADD_METHOD_TO(PredictController::liveOrderBookSignals, "/api/orderbook/live-signals", Get);
  ADD_METHOD_TO(PredictController::simulatedOrderBookSignals, "/api/orderbook/simulated-signals", Get);
  ADD_METHOD_TO(PredictController::livePortfolioStatus, "/api/live-portfolio/status", Get);
  ADD_METHOD_TO(PredictController::livePortfolioPositions, "/api/trading/live/positions", Get);
  ADD_METHOD_TO(PredictController::closeLivePosition, "/api/trading/live/close-position", Post);
  ADD_METHOD_TO(PredictController::startLiveTrading, "/api/trading/live/start", Post);
  ADD_METHOD_TO(PredictController::stopLiveTrading, "/api/trading/live/stop", Post);
  ADD_METHOD_TO(PredictController::liveTradingStatus, "/api/trading/live/status", Get);
  ADD_METHOD_TO(PredictController::updateLiveStrategyParameters, "/api/trading/live/update-strategy-params", Post);
  ADD_METHOD_TO(PredictController::executeLiveTrade, "/api/trading/live/execute", Post);
  ADD_METHOD_TO(PredictController::products, "/api/products", Get);
  ADD_METHOD_TO(PredictController::logMessage, "/api/log", Post);
  ADD_METHOD_TO(PredictController::getMlConfig, "/api/ml/config", Get);
  ADD_METHOD_TO(PredictController::updateMlConfig, "/api/ml/config", Post);
  ADD_METHOD_TO(PredictController::pnlTrades, "/api/ml/pnl-trades", Get);
  ADD_METHOD_TO(PredictController::predictionComparison, "/api/ml/prediction-comparison", Post);
  ADD_METHOD_TO(PredictController::resetMlDatabases, "/api/ml/databases", Delete);
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

  void startSimulatedTrading(const HttpRequestPtr &req,
                           std::function<void(const HttpResponsePtr &)> &&callback);
  void stopSimulatedTrading(const HttpRequestPtr &req,
                          std::function<void(const HttpResponsePtr &)> &&callback);
  void simulatedTradingStatus(const HttpRequestPtr &req,
                             std::function<void(const HttpResponsePtr &)> &&callback);
  void updateSimulatedStrategyParameters(const HttpRequestPtr &req,
                                         std::function<void(const HttpResponsePtr &)> &&callback);
  void liveOrderBookSignals(const HttpRequestPtr &req,
                            std::function<void(const HttpResponsePtr &)> &&callback);
  void simulatedOrderBookSignals(const HttpRequestPtr &req,
                                 std::function<void(const HttpResponsePtr &)> &&callback);
  void livePortfolioStatus(const HttpRequestPtr &req,
                           std::function<void(const HttpResponsePtr &)> &&callback);
  void livePortfolioPositions(const HttpRequestPtr &req,
                              std::function<void(const HttpResponsePtr &)> &&callback);
  void closeLivePosition(const HttpRequestPtr &req,
                         std::function<void(const HttpResponsePtr &)> &&callback);
  void startLiveTrading(const HttpRequestPtr &req,
                        std::function<void(const HttpResponsePtr &)> &&callback);
  void stopLiveTrading(const HttpRequestPtr &req,
                       std::function<void(const HttpResponsePtr &)> &&callback);
  void liveTradingStatus(const HttpRequestPtr &req,
                         std::function<void(const HttpResponsePtr &)> &&callback);
  void updateLiveStrategyParameters(const HttpRequestPtr &req,
                                    std::function<void(const HttpResponsePtr &)> &&callback);
  void executeLiveTrade(const HttpRequestPtr &req,
                        std::function<void(const HttpResponsePtr &)> &&callback);
  void products(const HttpRequestPtr &req,
                std::function<void(const HttpResponsePtr &)> &&callback);
  void logMessage(const HttpRequestPtr &req,
                  std::function<void(const HttpResponsePtr &)> &&callback);
  void getMlConfig(const HttpRequestPtr &req,
                   std::function<void(const HttpResponsePtr &)> &&callback);
  void updateMlConfig(const HttpRequestPtr &req,
                      std::function<void(const HttpResponsePtr &)> &&callback);
  void pnlTrades(const HttpRequestPtr &req,
                 std::function<void(const HttpResponsePtr &)> &&callback);
  void predictionComparison(const HttpRequestPtr &req,
                            std::function<void(const HttpResponsePtr &)> &&callback);
  void resetMlDatabases(const HttpRequestPtr &req,
                        std::function<void(const HttpResponsePtr &)> &&callback);

  static void init(const std::string &param_path, const std::string &model_dir);

  // Shared inference surfaces for non-HTTP callers (e.g. the trading loop).
  // May return nullptr before init() runs.
  static ml::FeatureEngineer *featureEngineer() { return feature_engineer_.get(); }
  static ml::ONNXModelManager *modelManager() { return model_manager_.get(); }

private:
  static std::unique_ptr<ml::FeatureEngineer> feature_engineer_;
  static std::unique_ptr<ml::ONNXModelManager> model_manager_;
  static std::string model_dir_;
  static std::string trained_models_dir_;
};

} // namespace api
