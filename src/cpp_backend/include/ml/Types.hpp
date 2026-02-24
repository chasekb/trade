#pragma once
#include <cstdint>
#include <nlohmann/json.hpp>
#include <string>

namespace ml {

struct OrderBookFeatures {
  int64_t timestamp;
  std::string symbol;
  double bid_ask_imbalance;
  double spread_percent;
  double mid_price;
  double bid_volume;
  double ask_volume;
  int order_book_depth;
  bool large_bid_wall;
  bool large_ask_wall;
  double wall_size;
  double volume_weighted_price;
  double price_momentum;
  double volatility;

  // Meta-features
  double volume_24h = 0.0;
  double volume_30d = 0.0;
  double high_24h = 0.0;
  double low_24h = 0.0;

  // Prev ML analysis
  double prev_win_probability = 0.0;
  double prev_expected_return = 0.0;
  double prev_confidence = 0.0;
};

// JSON Serialization
void from_json(const nlohmann::json &j, OrderBookFeatures &f);
void to_json(nlohmann::json &j, const OrderBookFeatures &f);

} // namespace ml
