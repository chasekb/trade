
#include "ml/Types.hpp"

namespace ml {

void from_json(const nlohmann::json &j, OrderBookFeatures &f) {
  j.at("timestamp").get_to(f.timestamp);
  j.at("symbol").get_to(f.symbol);
  j.at("bid_ask_imbalance").get_to(f.bid_ask_imbalance);
  j.at("spread_percent").get_to(f.spread_percent);
  j.at("mid_price").get_to(f.mid_price);
  j.at("bid_volume").get_to(f.bid_volume);
  j.at("ask_volume").get_to(f.ask_volume);
  j.at("order_book_depth").get_to(f.order_book_depth);
  j.at("large_bid_wall").get_to(f.large_bid_wall);
  j.at("large_ask_wall").get_to(f.large_ask_wall);
  j.at("wall_size").get_to(f.wall_size);
  j.at("volume_weighted_price").get_to(f.volume_weighted_price);
  j.at("price_momentum").get_to(f.price_momentum);
  j.at("volatility").get_to(f.volatility);

  if (j.contains("volume_24h"))
    j.at("volume_24h").get_to(f.volume_24h);
  if (j.contains("volume_30d"))
    j.at("volume_30d").get_to(f.volume_30d);
  if (j.contains("high_24h"))
    j.at("high_24h").get_to(f.high_24h);
  if (j.contains("low_24h"))
    j.at("low_24h").get_to(f.low_24h);

  if (j.contains("prev_win_probability"))
    j.at("prev_win_probability").get_to(f.prev_win_probability);
  if (j.contains("prev_expected_return"))
    j.at("prev_expected_return").get_to(f.prev_expected_return);
  if (j.contains("prev_confidence"))
    j.at("prev_confidence").get_to(f.prev_confidence);
}

void to_json(nlohmann::json &j, const OrderBookFeatures &f) {
  j = nlohmann::json{{"timestamp", f.timestamp},
                     {"symbol", f.symbol},
                     {"bid_ask_imbalance", f.bid_ask_imbalance},
                     {"spread_percent", f.spread_percent},
                     {"mid_price", f.mid_price},
                     {"bid_volume", f.bid_volume},
                     {"ask_volume", f.ask_volume},
                     {"order_book_depth", f.order_book_depth},
                     {"large_bid_wall", f.large_bid_wall},
                     {"large_ask_wall", f.large_ask_wall},
                     {"wall_size", f.wall_size},
                     {"volume_weighted_price", f.volume_weighted_price},
                     {"price_momentum", f.price_momentum},
                     {"volatility", f.volatility},
                     {"volume_24h", f.volume_24h},
                     {"volume_30d", f.volume_30d},
                     {"high_24h", f.high_24h},
                     {"low_24h", f.low_24h},
                     {"prev_win_probability", f.prev_win_probability},
                     {"prev_expected_return", f.prev_expected_return},
                     {"prev_confidence", f.prev_confidence}};
}

} // namespace ml
