#include "../include/cache/CacheManager.hpp"
#include "../include/config/Config.hpp"
#include "../include/utils/Logger.hpp"

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
