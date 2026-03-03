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

# mlpack is header-only – use find_path instead of find_package
find_path(MLPACK_INCLUDE_DIR NAMES mlpack.hpp mlpack/core.hpp
    HINTS ${CMAKE_PREFIX_PATH}/include
    PATH_SUFFIXES mlpack
)
if(NOT MLPACK_INCLUDE_DIR)
    message(FATAL_ERROR "mlpack headers not found. Ensure vcpkg installed mlpack.")
endif()

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
    src/ml/TransformerModel.cpp
    src/ml/ModelTrainer.cpp
    src/api/PredictController.cpp
)

add_executable(trading_bot_cpp ${SOURCES})

target_include_directories(trading_bot_cpp PRIVATE include ${MLPACK_INCLUDE_DIR})

target_link_libraries(trading_bot_cpp PRIVATE
    Drogon::Drogon
    nlohmann_json::nlohmann_json
    libpqxx::pqxx
    hiredis::hiredis
    redis++::redis++_static
    spdlog::spdlog
    onnxruntime::onnxruntime
    xtensor
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
