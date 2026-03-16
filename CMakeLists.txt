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
find_package(Torch CONFIG REQUIRED)
# Workaround for arm64 libtorch_cpu unresolved SLEEF symbols in some vcpkg builds
find_package(sleef CONFIG QUIET)
find_package(SLEEF CONFIG QUIET)

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
    src/ml/TransformerModel.cpp
    src/ml/ModelTrainer.cpp
    src/api/PredictController.cpp
)

add_executable(trading_bot_cpp ${SOURCES})

target_include_directories(trading_bot_cpp PRIVATE
    include
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

# vcpkg/libtorch on arm64 can miss transitive SLEEF linkage from torch target.
# Link SLEEF explicitly with robust target/library fallbacks.
set(SLEEF_LINK_LIBS "")
if(TARGET sleef::sleef)
    list(APPEND SLEEF_LINK_LIBS sleef::sleef)
elseif(TARGET SLEEF::sleef)
    list(APPEND SLEEF_LINK_LIBS SLEEF::sleef)
elseif(TARGET sleef)
    list(APPEND SLEEF_LINK_LIBS sleef)
endif()

# arm64 libtorch can also require additional SLEEF companion libraries for
# GNU ABI / vectorized symbols that are not always propagated transitively.
if(TARGET sleef::sleefgnuabi)
    list(APPEND SLEEF_LINK_LIBS sleef::sleefgnuabi)
elseif(TARGET SLEEF::sleefgnuabi)
    list(APPEND SLEEF_LINK_LIBS SLEEF::sleefgnuabi)
elseif(TARGET sleefgnuabi)
    list(APPEND SLEEF_LINK_LIBS sleefgnuabi)
endif()

if(TARGET sleef::sleefquad)
    list(APPEND SLEEF_LINK_LIBS sleef::sleefquad)
elseif(TARGET SLEEF::sleefquad)
    list(APPEND SLEEF_LINK_LIBS SLEEF::sleefquad)
elseif(TARGET sleefquad)
    list(APPEND SLEEF_LINK_LIBS sleefquad)
endif()

# Some vcpkg/sleef configs expose raw libraries without imported targets.
if(NOT SLEEF_LINK_LIBS)
    find_library(SLEEF_LIBRARY
        NAMES sleef libsleef
        PATH_SUFFIXES lib
    )
    find_library(SLEEF_GNUABI_LIBRARY
        NAMES sleefgnuabi libsleefgnuabi
        PATH_SUFFIXES lib
    )
    find_library(SLEEF_QUAD_LIBRARY
        NAMES sleefquad libsleefquad
        PATH_SUFFIXES lib
    )

    if(SLEEF_LIBRARY)
        list(APPEND SLEEF_LINK_LIBS ${SLEEF_LIBRARY})
    endif()
    if(SLEEF_GNUABI_LIBRARY)
        list(APPEND SLEEF_LINK_LIBS ${SLEEF_GNUABI_LIBRARY})
    endif()
    if(SLEEF_QUAD_LIBRARY)
        list(APPEND SLEEF_LINK_LIBS ${SLEEF_QUAD_LIBRARY})
    endif()
endif()

list(REMOVE_DUPLICATES SLEEF_LINK_LIBS)

if(SLEEF_LINK_LIBS)
    message(STATUS "Linking SLEEF explicitly: ${SLEEF_LINK_LIBS}")
    # On Linux, the linker may enable --as-needed by default. In that mode,
    # explicitly listed SLEEF shared libraries can still be dropped even though
    # libtorch_cpu.so needs them, which leaves arm64/SVE symbols unresolved in
    # GitHub Actions. Disable as-needed for this target so the explicit SLEEF
    # linkage is retained.
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        target_link_options(trading_bot_cpp PRIVATE "-Wl,--no-as-needed")
    endif()
    target_link_libraries(trading_bot_cpp PRIVATE ${SLEEF_LINK_LIBS})
else()
    message(STATUS "SLEEF libraries not found; proceeding without explicit SLEEF linkage")
endif()

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
