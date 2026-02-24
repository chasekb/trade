
#include "ml/FeatureEngineer.hpp"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

using json = nlohmann::json;

bool compare_vectors(const std::vector<double> &a, const std::vector<double> &b,
                     double tol, const std::string &name) {
  if (a.size() != b.size()) {
    std::cout << "FAIL: " << name << " size mismatch! C++: " << a.size()
              << ", Python: " << b.size() << std::endl;
    return false;
  }
  double max_diff = 0.0;
  for (size_t i = 0; i < a.size(); ++i) {
    double diff = std::abs(a[i] - b[i]);
    if (diff > max_diff)
      max_diff = diff;
  }
  if (max_diff > tol) {
    std::cout << "FAIL: " << name << " difference too large: " << max_diff
              << " (tol: " << tol << ")" << std::endl;
    return false;
  }
  std::cout << "PASS: " << name << " (max diff: " << max_diff << ")"
            << std::endl;
  return true;
}

int main() {
  ml::FeatureEngineer fe;
  if (!fe.load_parameters("data/cpp_assets/feature_params.json")) {
    std::cerr << "Failed to load parameters!" << std::endl;
    return 1;
  }

  std::ifstream golden_file("data/cpp_assets/golden_features.json");
  if (!golden_file.is_open()) {
    std::cerr << "Failed to load golden data!" << std::endl;
    return 1;
  }
  json golden_data;
  golden_file >> golden_data;

  bool all_passed = true;
  for (size_t i = 0; i < golden_data.size(); ++i) {
    std::cout << "\n--- Testing Sample " << i << " ---" << std::endl;
    auto raw = golden_data[i]["raw"];
    ml::OrderBookFeatures f;
    f.bid_ask_imbalance = raw["bid_ask_imbalance"];
    f.spread_percent = raw["spread_percent"];
    f.mid_price = raw["mid_price"];
    f.bid_volume = raw["bid_volume"];
    f.ask_volume = raw["ask_volume"];
    f.order_book_depth = raw["order_book_depth"];
    f.large_bid_wall = raw["large_bid_wall"];
    f.large_ask_wall = raw["large_ask_wall"];
    f.wall_size = raw["wall_size"];
    f.volume_weighted_price = raw["volume_weighted_price"];
    f.price_momentum = raw["price_momentum"];
    f.volatility = raw["volatility"];
    f.volume_24h = raw["volume_24h"];
    f.volume_30d = raw["volume_30d"];
    f.high_24h = raw["high_24h"];
    f.low_24h = raw["low_24h"];
    f.prev_win_probability = raw["prev_win_probability"];
    f.prev_expected_return = raw["prev_expected_return"];
    f.prev_confidence = raw["prev_confidence"];

    auto cpp_pca = fe.preprocess(f);
    std::vector<double> py_pca = golden_data[i]["pca"];

    if (!compare_vectors(cpp_pca, py_pca, 1e-7, "PCA Output")) {
      all_passed = false;

      // Debug intermediate steps if PCA fails
      // (In a real test we'd expose intermediate steps or use friend classes)
    }
  }

  if (all_passed) {
    std::cout << "\nALL FEATURE ENGINEERING TESTS PASSED!" << std::endl;
    return 0;
  } else {
    std::cout << "\nSOME TESTS FAILED!" << std::endl;
    return 1;
  }
}
