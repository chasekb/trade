cmake_minimum_required(VERSION 3.20)
project(trading_bot_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Drogon CONFIG REQUIRED)
find_package(jsoncpp CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(libpqxx CONFIG REQUIRED)
find_package(hiredis CONFIG REQUIRED)
find_package(redis++ CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(onnxruntime CONFIG REQUIRED)
find_package(xtensor CONFIG REQUIRED)
find_package(Python3 COMPONENTS Development REQUIRED)
find_package(Torch REQUIRED)
find_package(OpenSSL REQUIRED)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${TORCH_CXX_FLAGS}")

# mlpack is header-only – no find_package needed, headers already in include_directories above
# Collect all source files
set(SOURCES
    src/main.cpp
    src/config/Config.cpp
    src/utils/Logger.cpp
    src/db/DatabaseManager.cpp
    src/cache/CacheManager.cpp
    src/ml/FeatureEngineer.cpp
    src/ml/Metrics.cpp
    src/ml/ONNXModelManager.cpp
    src/ml/Types.cpp
    src/ml/DataCollector.cpp
    src/ml/ExecutionCohorts.cpp
    src/ml/TrainingValidation.cpp
    src/ml/ModelTrainer.cpp
    src/ml/TransformerOnnxExport.cpp
    src/ml/TransformerModel.cpp
    src/exchange/CoinbaseAuth.cpp
    src/exchange/CoinbaseAdvancedClient.cpp
    src/exchange/CoinbaseOrder.cpp
    src/trading/PositionSizingPolicy.cpp
    src/trading/StrategySignal.cpp
    src/trading/StrategyExpectancyHarness.cpp
    src/trading/ExecutionReconciliation.cpp
    src/trading/TradingStatsService.cpp
    src/trading/SimulatedTradingService.cpp
    src/trading/LiveTradingService.cpp
    src/trading/CoinbasePortfolio.cpp
    src/trading/TradingStatsCalculator.cpp
    src/api/PredictController.cpp
)

add_executable(trading_bot_cpp ${SOURCES})

# Prevent duplicate ONNX schema registration when linking static ONNX/ORT
# archives in the backend image.
target_compile_definitions(trading_bot_cpp PRIVATE
    __ONNX_DISABLE_STATIC_REGISTRATION
)

target_include_directories(trading_bot_cpp PRIVATE
    include
    ${TORCH_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)

target_link_libraries(trading_bot_cpp PRIVATE
    Drogon::Drogon
    OpenSSL::SSL
    OpenSSL::Crypto
    nlohmann_json::nlohmann_json
    libpqxx::pqxx
    hiredis::hiredis
    redis++::redis++_static
    spdlog::spdlog
    onnxruntime::onnxruntime
    xtensor
    Python3::Python
    ${TORCH_LIBRARIES}
    # mlpack is header-only, linked via include dirs above
)

if(xtensor_INCLUDE_DIRS)
    target_include_directories(trading_bot_cpp PRIVATE ${xtensor_INCLUDE_DIRS})
endif()

# Test executable
add_executable(test_feature_engineer
    src/tests/test_feature_engineer.cpp
    src/ml/FeatureEngineer.cpp
)
target_include_directories(test_feature_engineer PRIVATE include)
target_link_libraries(test_feature_engineer PRIVATE
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(test_feature_engineer PRIVATE ${xtensor_INCLUDE_DIRS})
endif()

enable_testing()

add_executable(test_execution_cohorts
    src/tests/test_execution_cohorts.cpp
    src/ml/ExecutionCohorts.cpp
)
target_include_directories(test_execution_cohorts PRIVATE include)
target_link_libraries(test_execution_cohorts PRIVATE
    nlohmann_json::nlohmann_json
    libpqxx::pqxx
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(test_execution_cohorts PRIVATE ${xtensor_INCLUDE_DIRS})
endif()
add_test(NAME execution_cohorts COMMAND test_execution_cohorts)

add_executable(test_training_validation
    src/tests/test_training_validation.cpp
    src/ml/TrainingValidation.cpp
    src/ml/Metrics.cpp
    src/ml/ExecutionCohorts.cpp
)
target_include_directories(test_training_validation PRIVATE include)
target_link_libraries(test_training_validation PRIVATE
    nlohmann_json::nlohmann_json
    libpqxx::pqxx
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(test_training_validation PRIVATE ${xtensor_INCLUDE_DIRS})
endif()
add_test(NAME training_validation COMMAND test_training_validation)

add_executable(test_position_sizing_policy
    src/tests/test_position_sizing_policy.cpp
    src/trading/PositionSizingPolicy.cpp
)
target_include_directories(test_position_sizing_policy PRIVATE include)
add_test(NAME position_sizing_policy COMMAND test_position_sizing_policy)

add_executable(test_portfolio_accounting
    src/tests/test_portfolio_accounting.cpp
)
target_include_directories(test_portfolio_accounting PRIVATE include)
add_test(NAME portfolio_accounting COMMAND test_portfolio_accounting)

add_executable(test_live_reconciliation_contract
    src/tests/test_live_reconciliation_contract.cpp
)
target_include_directories(test_live_reconciliation_contract PRIVATE include)
add_test(NAME live_reconciliation_contract COMMAND test_live_reconciliation_contract)

add_executable(test_strategy_signal
    src/tests/test_strategy_signal.cpp
    src/trading/StrategySignal.cpp
)
target_include_directories(test_strategy_signal PRIVATE include)
add_test(NAME strategy_signal COMMAND test_strategy_signal)

add_executable(test_strategy_expectancy_harness
    src/tests/test_strategy_expectancy_harness.cpp
    src/trading/StrategyExpectancyHarness.cpp
    src/trading/StrategySignal.cpp
)
target_include_directories(test_strategy_expectancy_harness PRIVATE include)
add_test(NAME strategy_expectancy_harness COMMAND test_strategy_expectancy_harness)

add_executable(test_execution_reconciliation
    src/tests/test_execution_reconciliation.cpp
    src/trading/ExecutionReconciliation.cpp
)
target_include_directories(test_execution_reconciliation PRIVATE include)
add_test(NAME execution_reconciliation COMMAND test_execution_reconciliation)

add_executable(test_coinbase_auth
    src/tests/test_coinbase_auth.cpp
    src/exchange/CoinbaseAuth.cpp
)
target_include_directories(test_coinbase_auth PRIVATE include)
target_link_libraries(test_coinbase_auth PRIVATE
    OpenSSL::SSL
    OpenSSL::Crypto
)
add_test(NAME coinbase_auth COMMAND test_coinbase_auth)

add_executable(test_coinbase_order
    src/tests/test_coinbase_order.cpp
    src/exchange/CoinbaseOrder.cpp
)
target_include_directories(test_coinbase_order PRIVATE include)
target_link_libraries(test_coinbase_order PRIVATE
    JsonCpp::JsonCpp
)
add_test(NAME coinbase_order COMMAND test_coinbase_order)

add_executable(test_coinbase_portfolio
    src/tests/test_coinbase_portfolio.cpp
    src/trading/CoinbasePortfolio.cpp
)
target_include_directories(test_coinbase_portfolio PRIVATE include)
target_link_libraries(test_coinbase_portfolio PRIVATE JsonCpp::JsonCpp Drogon::Drogon)
add_test(NAME coinbase_portfolio COMMAND test_coinbase_portfolio)

add_executable(test_trading_stats_calculator
    src/tests/test_trading_stats_calculator.cpp
    src/trading/TradingStatsCalculator.cpp
)
target_include_directories(test_trading_stats_calculator PRIVATE include)
target_link_libraries(test_trading_stats_calculator PRIVATE
    spdlog::spdlog
)
add_test(NAME trading_stats_calculator COMMAND test_trading_stats_calculator)

add_executable(test_transformer_onnx_export
    src/tests/test_transformer_onnx_export.cpp
    src/ml/DataCollector.cpp
    src/ml/ExecutionCohorts.cpp
    src/ml/TrainingValidation.cpp
    src/ml/Metrics.cpp
    src/ml/ModelTrainer.cpp
    src/ml/TransformerOnnxExport.cpp
    src/ml/TransformerModel.cpp
)
target_include_directories(test_transformer_onnx_export PRIVATE
    include
    ${TORCH_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)
target_link_libraries(test_transformer_onnx_export PRIVATE
    libpqxx::pqxx
    onnxruntime::onnxruntime
    spdlog::spdlog
    Python3::Python
    ${TORCH_LIBRARIES}
)
add_test(NAME transformer_onnx_export COMMAND test_transformer_onnx_export)
