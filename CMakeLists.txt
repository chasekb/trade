cmake_minimum_required(VERSION 3.20)
project(trading_bot_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Drogon CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(libpqxx CONFIG REQUIRED)
find_package(hiredis CONFIG REQUIRED)
find_package(redis++ CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(onnxruntime CONFIG REQUIRED)
find_package(xtensor CONFIG REQUIRED)
find_package(Python3 COMPONENTS Development REQUIRED)
find_package(Torch REQUIRED)

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
    src/ml/ModelTrainer.cpp
    src/ml/TransformerOnnxExport.cpp
    src/ml/TransformerModel.cpp
    src/trading/TradingStatsService.cpp
    src/trading/SimulatedTradingService.cpp
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

add_executable(test_transformer_onnx_export
    src/tests/test_transformer_onnx_export.cpp
    src/ml/TransformerOnnxExport.cpp
)
target_include_directories(test_transformer_onnx_export PRIVATE include)
target_link_libraries(test_transformer_onnx_export PRIVATE
    onnxruntime::onnxruntime
)
add_test(NAME transformer_onnx_export COMMAND test_transformer_onnx_export)
