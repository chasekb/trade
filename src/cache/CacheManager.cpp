#include "cache/CacheManager.hpp"
#include "config/Config.hpp"
#include "ml/ModelTrainer.hpp"
#include "utils/Logger.hpp"
#include <nlohmann/json.hpp>

CacheManager &CacheManager::getInstance() {
  static CacheManager instance;
  return instance;
}

bool CacheManager::init() {
  auto &config = Config::getInstance();
  std::string redis_url = config.get("REDIS_URL", "tcp://127.0.0.1:6379");

  try {
    redis_ = std::make_unique<sw::redis::Redis>(redis_url);
    // Ping to test connection
    redis_->ping();
    TR_LOG_INFO("Successfully connected to Redis at {}", redis_url);
    return true;
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis connection error: {}", e.what());
    redis_.reset();
    return false;
  }
}

bool CacheManager::set(const std::string &key, const std::string &value,
                       int expiration_seconds) {
  if (!redis_)
    return false;

  try {
    if (expiration_seconds > 0) {
      redis_->set(key, value, std::chrono::seconds(expiration_seconds));
    } else {
      redis_->set(key, value);
    }
    return true;
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis SET error: {}", e.what());
    return false;
  }
}

std::optional<std::string> CacheManager::get(const std::string &key) {
  if (!redis_)
    return std::nullopt;

  try {
    auto val = redis_->get(key);
    if (val) {
      return *val;
    }
    return std::nullopt;
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis GET error: {}", e.what());
    return std::nullopt;
  }
}

bool CacheManager::del(const std::string &key) {
  if (!redis_)
    return false;

  try {
    return redis_->del(key) > 0;
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis DEL error: {}", e.what());
    return false;
  }
}

void CacheManager::set_training_status(const std::string &status,
                                       int progress) {
  if (!redis_)
    return;
  try {
    redis_->set("ml_training_status", status);
    redis_->set("ml_training_progress", std::to_string(progress));
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis status set error: {}", e.what());
  }
}

std::pair<std::string, int> CacheManager::get_training_status() {
  if (!redis_)
    return {"idle", 0};
  try {
    auto status = redis_->get("ml_training_status");
    auto progress = redis_->get("ml_training_progress");

    std::string s = status ? *status : "idle";
    int p = progress ? std::stoi(*progress) : 0;
    return {s, p};
  } catch (const sw::redis::Error &e) {
    TR_LOG_ERROR("Redis status get error: {}", e.what());
    return {"error", 0};
  }
}

void CacheManager::set_last_metrics(const ml::ModelMetrics &metrics) {
  if (!redis_)
    return;
  try {
    nlohmann::json j;
    ml::to_json(j, metrics);
    redis_->set("ml_last_metrics", j.dump());
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to set metrics in Redis: {}", e.what());
  }
}

ml::ModelMetrics CacheManager::get_last_metrics() {
  ml::ModelMetrics metrics; // Returns defaults (0.0) if not found
  if (!redis_)
    return metrics;

  try {
    auto val = redis_->get("ml_last_metrics");
    if (val) {
      auto j = nlohmann::json::parse(*val);
      ml::from_json(j, metrics);
    }
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Failed to get metrics from Redis: {}", e.what());
  }
  return metrics;
}
