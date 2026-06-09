#pragma once
#include <pqxx/pqxx>
#include <string>

class DatabaseManager {
public:
    static DatabaseManager& getInstance();
    
    // Initialize the database URL and verify connectivity.
    bool init();
    
    // Execute a simple query.
    pqxx::result query(const std::string& sql);
    
    // Example parameterized execution
    // pqxx::result execParams(const std::string& sql, args...);

private:
    DatabaseManager() = default;
    ~DatabaseManager() = default;
    DatabaseManager(const DatabaseManager&) = delete;
    DatabaseManager& operator=(const DatabaseManager&) = delete;

    std::string db_url_;
};
