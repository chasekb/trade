#include "../include/db/DatabaseManager.hpp"
#include "../include/config/Config.hpp"
#include "../include/utils/Logger.hpp"

DatabaseManager &DatabaseManager::getInstance() {
  static DatabaseManager instance;
  return instance;
}

bool DatabaseManager::init() {
  auto &config = Config::getInstance();
  std::string db_url = config.get("DATABASE_URL");

  if (db_url.empty()) {
    LOG_ERROR("DATABASE_URL is missing from configuration.");
    return false;
  }

  try {
    // Just establish a connection to test
    conn_ = std::make_unique<pqxx::connection>(db_url);
    if (conn_->is_open()) {
      LOG_INFO("Successfully connected to PostgreSQL database: {}",
               conn_->dbname());
      return true;
    } else {
      LOG_ERROR("Failed to open the database: {}", conn_->dbname());
      return false;
    }
  } catch (const std::exception &e) {
    LOG_ERROR("Database connection error: {}", e.what());
    return false;
  }
}

pqxx::result DatabaseManager::query(const std::string &sql) {
  if (!conn_ || !conn_->is_open()) {
    try {
      init(); // try to reconnect
    } catch (...) {
    }
  }

  if (conn_ && conn_->is_open()) {
    try {
      pqxx::work W(*conn_);
      pqxx::result R = W.exec(sql);
      W.commit();
      return R;
    } catch (const std::exception &e) {
      LOG_ERROR("Database query failed: {}", e.what());
    }
  }
  return pqxx::result{};
}
