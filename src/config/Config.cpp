#include "config/Config.hpp"
#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>

Config &Config::getInstance() {
  static Config instance;
  return instance;
}

void Config::trim(std::string &s) {
  s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char ch) {
            return !std::isspace(ch);
          }));
  s.erase(std::find_if(s.rbegin(), s.rend(),
                       [](unsigned char ch) { return !std::isspace(ch); })
              .base(),
          s.end());
}

void Config::loadEnv(const std::string &filepath) {
  std::ifstream file(filepath);
  if (!file.is_open()) {
    std::cerr << "Warning: Could not open " << filepath
              << ". Falling back to system environment variables." << std::endl;
    return;
  }

  std::string line;
  while (std::getline(file, line)) {
    trim(line);
    if (line.empty() || line[0] == '#')
      continue;

    auto pos = line.find('=');
    if (pos != std::string::npos) {
      std::string key = line.substr(0, pos);
      std::string value = line.substr(pos + 1);
      trim(key);
      trim(value);

      // Remove quotes if present
      if (value.size() >= 2 &&
          ((value.front() == '"' && value.back() == '"') ||
           (value.front() == '\'' && value.back() == '\''))) {
        value = value.substr(1, value.size() - 2);
      }

      envVars_[key] = value;
    }
  }
}

std::string Config::get(const std::string &key,
                        const std::string &defaultValue) const {
  // Check our loaded .env first
  auto it = envVars_.find(key);
  if (it != envVars_.end()) {
    return it->second;
  }

  // Fallback to actual process environment variables (e.g., set by docker)
  const char *env_p = std::getenv(key.c_str());
  if (env_p) {
    return std::string(env_p);
  }

  return defaultValue;
}

std::optional<std::string> Config::getOptional(const std::string &key) const {
  auto it = envVars_.find(key);
  if (it != envVars_.end()) {
    return it->second;
  }
  const char *env_p = std::getenv(key.c_str());
  if (env_p) {
    return std::string(env_p);
  }
  return std::nullopt;
}

int Config::getInt(const std::string &key, int defaultValue) const {
  std::string val = get(key);
  if (val.empty())
    return defaultValue;
  try {
    return std::stoi(val);
  } catch (...) {
    return defaultValue;
  }
}

bool Config::getBool(const std::string &key, bool defaultValue) const {
  std::string val = get(key);
  if (val.empty())
    return defaultValue;

  std::string lowerVal = val;
  std::transform(lowerVal.begin(), lowerVal.end(), lowerVal.begin(), ::tolower);

  if (lowerVal == "true" || lowerVal == "1" || lowerVal == "yes" ||
      lowerVal == "on")
    return true;
  if (lowerVal == "false" || lowerVal == "0" || lowerVal == "no" ||
      lowerVal == "off")
    return false;

  return defaultValue;
}
