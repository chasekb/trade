#include "trading/QuoteBatchScheduler.hpp"

#include <iostream>
#include <set>
#include <string>
#include <vector>

using trade::trading::selectQuoteBatch;

int main() {
  int failures = 0;
  const auto expect = [&](bool condition, const char *label) {
    if (!condition) {
      std::cerr << "FAIL: " << label << '\n';
      ++failures;
    }
  };

  const std::vector<std::string> symbols = {"BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD"};
  const auto first = selectQuoteBatch(symbols, 0, 2);
  expect(first.symbols == std::vector<std::string>{"BTC-USD", "ETH-USD"},
         "first batch is bounded and preserves selected order");
  expect(first.next_cursor == 2, "cursor advances by the admitted batch size");

  const auto second = selectQuoteBatch(symbols, first.next_cursor, 2);
  expect(second.symbols == std::vector<std::string>{"SOL-USD", "ADA-USD"},
         "second batch advances without repeating symbols");
  expect(second.next_cursor == 4, "cursor advances across batches");

  const auto wrapped = selectQuoteBatch(symbols, second.next_cursor, 2);
  expect(wrapped.symbols == std::vector<std::string>{"DOT-USD", "BTC-USD"},
         "batch wraps fairly at the end of the universe");
  expect(wrapped.next_cursor == 1, "wrapped cursor points after the last selected symbol");

  expect(selectQuoteBatch(symbols, 0, 0).symbols.empty(),
         "zero batch size performs no provider work");
  expect(selectQuoteBatch({}, 0, 2).next_cursor == 0,
         "empty universe remains safe");

  // A large universe must make progress in bounded, deterministic slices;
  // provider failures are isolated by the caller and must not alter ordering.
  std::vector<std::string> large_universe;
  for (int index = 0; index < 257; ++index) {
    large_universe.push_back("ASSET-" + std::to_string(index) + "-USD");
  }
  std::set<std::string> visited;
  std::size_t cursor = 0;
  for (int tick = 0; tick < 40; ++tick) {
    const auto batch = selectQuoteBatch(large_universe, cursor, 8);
    expect(batch.symbols.size() == 8, "large universe keeps the provider batch bounded");
    for (const auto &symbol : batch.symbols) visited.insert(symbol);
    cursor = batch.next_cursor;
  }
  expect(visited.size() == 257, "large universe receives fair coverage over worker ticks");
  expect(selectQuoteBatch(large_universe, 0, 8).symbols ==
             selectQuoteBatch(large_universe, 257 * 3, 8).symbols,
         "round-robin selection is repeatable after full-universe rotations");

  if (failures == 0) {
    std::cout << "All quote batch scheduler tests passed\n";
    return 0;
  }
  return 1;
}
