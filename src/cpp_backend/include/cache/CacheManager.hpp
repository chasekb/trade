#pragma once
#include <sw/redis++/redis++.h>
#include <memory>
#include <string>
#include <optional>

class CacheManager {
public:
    static CacheManager& getInstance();
    
    bool init();
    
    bool set(const std::string& key, const std::string& value, int expiration_seconds = -1);
    std::optional<std::string> get(const std::string& key);
    bool del(const std::string& key);

private:
    CacheManager() = default;
    ~CacheManager() = default;
    CacheManager(const CacheManager&) = delete;
    CacheManager& operator=(const CacheManager&) = delete;

    std::unique_ptr<sw::redis::Redis> redis_;
};
