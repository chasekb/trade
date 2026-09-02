#include "trading/QuoteBatchScheduler.hpp"

#include <algorithm>

namespace trade::trading {

QuoteBatchSelection selectQuoteBatch(const std::vector<std::string> &selected_symbols,
                                     const std::size_t cursor,
                                     const std::size_t max_symbols) {
  QuoteBatchSelection selection;
  if (selected_symbols.empty() || max_symbols == 0) {
    return selection;
  }

  const std::size_t start = cursor % selected_symbols.size();
  const std::size_t count = std::min(max_symbols, selected_symbols.size());
  selection.symbols.reserve(count);
  for (std::size_t offset = 0; offset < count; ++offset) {
    selection.symbols.push_back(selected_symbols[(start + offset) % selected_symbols.size()]);
  }
  selection.next_cursor = (start + count) % selected_symbols.size();
  return selection;
}

} // namespace trade::trading
