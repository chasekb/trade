#pragma once
#include "ml/ModelTrainer.hpp"
#include <memory>
#include <optional>
#include <string>
#include <sw/redis++/redis++.h>
#include <utility>

class CacheManager {
public:
  static CacheManager &getInstance();

  bool init();

  bool set(const std::string &key, const std::string &value,
           int expiration_seconds = -1);
  std::optional<std::string> get(const std::string &key);
  bool del(const std::string &key);

  // training status
  void set_training_status(const std::string &status, int progress);
  std::pair<std::string, int> get_training_status();

  // ML metrics persistence
  void set_last_metrics(const ml::ModelMetrics &metrics);
  ml::ModelMetrics get_last_metrics();

private:
  CacheManager() = default;
  ~CacheManager() = default;
  CacheManager(const CacheManager &) = delete;
  CacheManager &operator=(const CacheManager &) = delete;

  std::unique_ptr<sw::redis::Redis> redis_;
};
