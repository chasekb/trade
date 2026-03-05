cmake_minimum_required(VERSION 3.20)
project(trading_bot_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Auto-detect the vcpkg installed include directory (handles any triplet name)
# Must be done BEFORE find_package calls so all packages can find headers
file(GLOB VCPKG_INSTALLED_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/vcpkg_installed/*/include")
if(VCPKG_INSTALLED_DIRS)
    list(GET VCPKG_INSTALLED_DIRS 0 VCPKG_INCLUDE_DIR)
    message(STATUS "Found vcpkg installed include dir: ${VCPKG_INCLUDE_DIR}")
    include_directories(BEFORE ${VCPKG_INCLUDE_DIR})
elseif(VCPKG_TRIPLET_INCLUDE_DIR)
    message(STATUS "Using VCPKG_TRIPLET_INCLUDE_DIR: ${VCPKG_TRIPLET_INCLUDE_DIR}")
    include_directories(BEFORE ${VCPKG_TRIPLET_INCLUDE_DIR})
    set(VCPKG_INCLUDE_DIR ${VCPKG_TRIPLET_INCLUDE_DIR})
else()
    message(WARNING "No vcpkg include directory found. Build may fail.")
endif()

find_package(Drogon CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(libpqxx CONFIG REQUIRED)
find_package(hiredis CONFIG REQUIRED)
find_package(redis++ CONFIG REQUIRED)
find_package(spdlog CONFIG REQUIRED)
find_package(onnxruntime CONFIG REQUIRED)
find_package(xtensor CONFIG REQUIRED)
find_package(Torch CONFIG REQUIRED)

# mlpack is header-only – no find_package needed, headers already in include_directories above
find_path(MLPACK_INCLUDE_DIR NAMES mlpack.hpp mlpack/core.hpp)
if(NOT MLPACK_INCLUDE_DIR)
    message(WARNING "mlpack headers not found explicitly, relying on global include dirs")
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

target_include_directories(trading_bot_cpp PRIVATE
    include
    ${VCPKG_INCLUDE_DIR}
    ${MLPACK_INCLUDE_DIR}
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
    torch
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
target_include_directories(test_feature_engineer PRIVATE include ${VCPKG_INCLUDE_DIR})
target_link_libraries(test_feature_engineer PRIVATE
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(test_feature_engineer PRIVATE ${xtensor_INCLUDE_DIRS})
endif()
