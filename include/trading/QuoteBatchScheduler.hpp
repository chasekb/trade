#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace trade::trading {

struct QuoteBatchSelection {
  std::vector<std::string> symbols;
  std::size_t next_cursor = 0;
};

// Select a bounded, deterministic round-robin slice without changing the
// selected universe. The caller performs requests sequentially, preserving
// the provider's existing pacing and retry behavior.
QuoteBatchSelection selectQuoteBatch(const std::vector<std::string> &selected_symbols,
                                     std::size_t cursor,
                                     std::size_t max_symbols);

} // namespace trade::trading
