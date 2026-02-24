#pragma once
#include <pqxx/pqxx>
#include <memory>
#include <string>

class DatabaseManager {
public:
    static DatabaseManager& getInstance();
    
    // Initialize the connection pool or a single connection
    bool init();
    
    // Execute a simple query
    pqxx::result query(const std::string& sql);
    
    // Example parameterized execution
    // pqxx::result execParams(const std::string& sql, args...);

private:
    DatabaseManager() = default;
    ~DatabaseManager() = default;
    DatabaseManager(const DatabaseManager&) = delete;
    DatabaseManager& operator=(const DatabaseManager&) = delete;

    std::unique_ptr<pqxx::connection> conn_;
};
