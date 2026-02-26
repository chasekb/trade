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

# Collect all source files
set(SOURCES
    src/cpp_backend/main.cpp
    src/cpp_backend/config/Config.cpp
    src/cpp_backend/utils/Logger.cpp
    src/cpp_backend/db/DatabaseManager.cpp
    src/cpp_backend/cache/CacheManager.cpp
    src/cpp_backend/ml/FeatureEngineer.cpp
    src/cpp_backend/ml/ONNXModelManager.cpp
    src/cpp_backend/ml/Types.cpp
    src/cpp_backend/api/PredictController.cpp
)

add_executable(trading_bot_cpp ${SOURCES})

target_include_directories(trading_bot_cpp PRIVATE src/cpp_backend/include)

target_link_libraries(trading_bot_cpp PRIVATE
    Drogon::Drogon
    nlohmann_json::nlohmann_json
    libpqxx::pqxx
    hiredis::hiredis
    redis++::redis++_static
    spdlog::spdlog
    onnxruntime::onnxruntime
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(trading_bot_cpp PRIVATE ${xtensor_INCLUDE_DIRS})
endif()

# Test executable
add_executable(test_feature_engineer 
    src/cpp_backend/tests/test_feature_engineer.cpp
    src/cpp_backend/ml/FeatureEngineer.cpp
)
target_include_directories(test_feature_engineer PRIVATE src/cpp_backend/include)
target_link_libraries(test_feature_engineer PRIVATE
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    xtensor
)
if(xtensor_INCLUDE_DIRS)
    target_include_directories(test_feature_engineer PRIVATE ${xtensor_INCLUDE_DIRS})
endif()
