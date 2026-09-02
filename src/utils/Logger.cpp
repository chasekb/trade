#include "utils/Logger.hpp"
#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>

std::shared_ptr<spdlog::logger> Logger::logger_ = nullptr;

void Logger::init(const std::string &level) {
  if (logger_)
    return;

  try {
    auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
    // Match Python's %(asctime)s - %(name)s - %(levelname)s - %(message)s
    console_sink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%n] [%^%l%$] %v");

    logger_ = std::make_shared<spdlog::logger>("trading_bot", console_sink);

    // Set log level
    if (level == "debug")
      logger_->set_level(spdlog::level::debug);
    else if (level == "trace")
      logger_->set_level(spdlog::level::trace);
    else if (level == "warn")
      logger_->set_level(spdlog::level::warn);
    else if (level == "error")
      logger_->set_level(spdlog::level::err);
    else
      logger_->set_level(spdlog::level::info);

    spdlog::register_logger(logger_);
    spdlog::set_default_logger(logger_);

  } catch (const spdlog::spdlog_ex &ex) {
    printf("Log initialization failed: %s\n", ex.what());
  }
}

std::shared_ptr<spdlog::logger> Logger::get() {
  if (!logger_) {
    init(); // Ensure it's initialized with defaults if called early
  }
  return logger_;
}
