#pragma once
#include <memory>
#include <spdlog/spdlog.h>
#include <string>

class Logger {
public:
  static void init(const std::string &level = "info");
  static std::shared_ptr<spdlog::logger> get();

private:
  static std::shared_ptr<spdlog::logger> logger_;
};

// Convenience macros mapping to standard spdlog
#define LOG_TRACE(...) SPDLOG_LOGGER_TRACE(Logger::get(), __VA_ARGS__)
#define LOG_DEBUG(...) SPDLOG_LOGGER_DEBUG(Logger::get(), __VA_ARGS__)
#define LOG_INFO(...) SPDLOG_LOGGER_INFO(Logger::get(), __VA_ARGS__)
#define LOG_WARN(...) SPDLOG_LOGGER_WARN(Logger::get(), __VA_ARGS__)
#define LOG_ERROR(...) SPDLOG_LOGGER_ERROR(Logger::get(), __VA_ARGS__)
#define LOG_CRITICAL(...) SPDLOG_LOGGER_CRITICAL(Logger::get(), __VA_ARGS__)
