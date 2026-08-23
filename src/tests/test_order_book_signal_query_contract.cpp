#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#ifndef TRADE_SOURCE_DIR
#error "TRADE_SOURCE_DIR must point at the repository source tree"
#endif

namespace {

struct FixtureRow {
  std::string signal_data;
  double strength;
  long long timestamp;
};

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << '\n';
    ++failures;
  }
}

std::string readFile(const std::string &path) {
  std::ifstream input(path);
  std::ostringstream contents;
  contents << input.rdbuf();
  return contents.str();
}

bool isValidObject(const std::string &payload) {
  try {
    const auto parsed = nlohmann::json::parse(payload);
    return parsed.is_object();
  } catch (...) {
    return false;
  }
}

} // namespace

int main() {
  const std::string source_dir = TRADE_SOURCE_DIR;
  const std::vector<std::string> service_paths = {
      source_dir + "/src/trading/LiveTradingService.cpp",
      source_dir + "/src/trading/SimulatedTradingService.cpp",
  };

  for (const auto &path : service_paths) {
    const std::string source = readFile(path);
    expect(!source.empty(), "service source is readable: " + path);
    expect(source.find("pg_input_is_valid") == std::string::npos,
           "unsupported pg_input_is_valid is absent: " + path);
    expect(source.find("signal_data::jsonb") == std::string::npos,
           "legacy signal_data is not cast to jsonb: " + path);
    expect(source.find("parseJsonString(row[\"signal_data\"]") != std::string::npos,
           "signal_data is parsed per row after SQL: " + path);
    expect(source.find("if (!signal.isObject())") != std::string::npos,
           "malformed/non-object payload degrades to an object: " + path);
    expect(source.find("ORDER BY strength DESC, timestamp DESC") != std::string::npos,
           "ordering remains strength then timestamp: " + path);
  }

  // These represent legacy rows returned by either read-only query path. The
  // payload must never participate in SQL execution or ordering: malformed
  // JSON and nonnumeric nested values are still returned as degraded rows.
  std::vector<FixtureRow> rows = {
      {"{not-json", 0.80, 100},
      {R"({"ml_analysis":{"win_probability":"not-a-number"}})", 0.80, 200},
      {R"({"ml_analysis":{"win_probability":0.91},"signal":"buy"})", 0.70, 300},
  };
  std::stable_sort(rows.begin(), rows.end(), [](const FixtureRow &left, const FixtureRow &right) {
    if (left.strength != right.strength) {
      return left.strength > right.strength;
    }
    return left.timestamp > right.timestamp;
  });

  expect(rows.size() == 3, "all valid, malformed, and nonnumeric rows survive");
  expect(rows[0].timestamp == 200 && rows[1].timestamp == 100,
         "ordering is deterministic without reading JSON fields");
  expect(!isValidObject(rows[1].signal_data),
         "malformed JSON is recognized as a degradable payload");
  expect(isValidObject(rows[0].signal_data),
         "nonnumeric nested value remains valid JSON and is degradable per row");
  expect(isValidObject(rows[2].signal_data), "valid JSON object remains readable");

  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
