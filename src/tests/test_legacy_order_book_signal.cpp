#include "trading/LegacyOrderBookSignal.hpp"

#include <cassert>

int main() {
  using trade::trading::legacy_order_book::parseObject;
  using trade::trading::legacy_order_book::winProbability;

  const Json::Value valid = parseObject(
      R"({"signal_type":"buy","ml_analysis":{"win_probability":0.81}})");
  assert(valid.isObject());
  assert(valid["signal_type"].asString() == "buy");
  assert(winProbability(valid) == 0.81);

  // Legacy malformed and non-object payloads must degrade to an empty object,
  // allowing the caller to overlay database fields without throwing.
  assert(parseObject("not-json").isObject());
  assert(parseObject("[1,2,3]").isObject());
  assert(parseObject("").isObject());

  Json::Value nonnumeric(Json::objectValue);
  nonnumeric["ml_analysis"]["win_probability"] = "not-a-number";
  assert(winProbability(nonnumeric) == 0.5);

  Json::Value missing(Json::objectValue);
  assert(winProbability(missing) == 0.5);
  return 0;
}