#include "db/DatabaseManager.hpp"
#include "config/Config.hpp"
#include "utils/Logger.hpp"

DatabaseManager &DatabaseManager::getInstance() {
  static DatabaseManager instance;
  return instance;
}

bool DatabaseManager::init() {
  auto &config = Config::getInstance();
  db_url_ = config.get("DATABASE_URL");

  if (db_url_.empty()) {
    TR_LOG_ERROR("DATABASE_URL is missing from configuration.");
    return false;
  }

  try {
    // Establish a short-lived connection to verify credentials and connectivity.
    pqxx::connection conn(db_url_);
    if (conn.is_open()) {
      TR_LOG_INFO("Successfully connected to PostgreSQL database: {}",
                  conn.dbname());
      return true;
    }

    TR_LOG_ERROR("Failed to open the database: {}", conn.dbname());
    return false;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Database connection error: {}", e.what());
    return false;
  }
}

pqxx::result DatabaseManager::query(const std::string &sql) {
  if (db_url_.empty() && !init()) {
    return pqxx::result{};
  }

  try {
    pqxx::connection conn(db_url_);
    pqxx::work W(conn);
    pqxx::result R = W.exec(sql);
    W.commit();
    return R;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Database query failed: {}", e.what());
  }

  return pqxx::result{};
}

pqxx::result DatabaseManager::execParams(const std::string &sql,
                                         const std::vector<std::string> &params) {
  if (db_url_.empty() && !init()) {
    return pqxx::result{};
  }

  try {
    pqxx::connection conn(db_url_);
    pqxx::work W(conn);
    pqxx::params bound;
    for (const auto &value : params) {
      bound.append(value);
    }
    pqxx::result R = W.exec(pqxx::zview(sql), bound);
    W.commit();
    return R;
  } catch (const std::exception &e) {
    TR_LOG_ERROR("Database parameterized query failed: {}", e.what());
  }

  return pqxx::result{};
}
