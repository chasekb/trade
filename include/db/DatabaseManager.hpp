#pragma once
#include <pqxx/pqxx>
#include <string>
#include <vector>

class DatabaseManager {
public:
    static DatabaseManager& getInstance();

    // Initialize the database URL and verify connectivity.
    bool init();

    // Execute a simple query.
    pqxx::result query(const std::string& sql);

    // Parameterized execution: placeholders $1..$n bound to params in order.
    // Use for any SQL that embeds request-derived values.
    pqxx::result execParams(const std::string& sql, const std::vector<std::string>& params);

private:
    DatabaseManager() = default;
    ~DatabaseManager() = default;
    DatabaseManager(const DatabaseManager&) = delete;
    DatabaseManager& operator=(const DatabaseManager&) = delete;

    std::string db_url_;
};
