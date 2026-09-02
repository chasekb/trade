#pragma once

#include <json/json.h>

#include <cmath>
#include <memory>
#include <string>

namespace trade::trading::legacy_order_book {

// Legacy order-book rows store signal_data as TEXT. Keep parsing outside SQL
// so malformed historical payloads degrade one row instead of aborting the
// whole query.
inline Json::Value parseObject(const std::string &text) {
  if (text.empty()) {
    return Json::Value(Json::objectValue);
  }

  Json::Value root;
  Json::CharReaderBuilder builder;
  builder["collectComments"] = false;
  std::string errors;
  std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
  if (reader->parse(text.data(), text.data() + text.size(), &root, &errors) &&
      root.isObject()) {
    return root;
  }
  return Json::Value(Json::objectValue);
}

inline double numberOrDefault(const Json::Value &value, double fallback) {
  if (!value.isNumeric()) {
    return fallback;
  }
  const double number = value.asDouble();
  return std::isfinite(number) ? number : fallback;
}

inline double winProbability(const Json::Value &signal) {
  const Json::Value ml_analysis =
      signal.get("ml_analysis", Json::Value(Json::objectValue));
  return numberOrDefault(ml_analysis.get("win_probability", Json::Value()), 0.5);
}

}  // namespace trade::trading::legacy_order_book