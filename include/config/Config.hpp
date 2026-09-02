#pragma once
#include <string>
#include <unordered_map>
#include <optional>

class Config {
public:
    static Config& getInstance();
    
    void loadEnv(const std::string& filepath = ".env");
    
    std::string get(const std::string& key, const std::string& defaultValue = "") const;
    std::optional<std::string> getOptional(const std::string& key) const;
    
    // Specific typed getters
    int getInt(const std::string& key, int defaultValue = 0) const;
    bool getBool(const std::string& key, bool defaultValue = false) const;

private:
    Config() = default;
    ~Config() = default;
    Config(const Config&) = delete;
    Config& operator=(const Config&) = delete;

    std::unordered_map<std::string, std::string> envVars_;
    
    void trim(std::string& s);
};
