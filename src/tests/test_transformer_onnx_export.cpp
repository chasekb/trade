#include "ml/TransformerOnnxExport.hpp"

#include <exception>
#include <filesystem>
#include <iostream>

int main() {
  const auto out = std::filesystem::temp_directory_path() /
                   "trade_transformer_smoke.onnx";

  try {
    trade::ml::export_transformer_to_onnx(out, 10);
  } catch (const std::exception &ex) {
    std::cerr << "Transformer ONNX export smoke test failed: " << ex.what()
              << std::endl;
    return 1;
  }

  if (!std::filesystem::exists(out) || std::filesystem::file_size(out) == 0) {
    std::cerr << "Transformer ONNX export produced no file" << std::endl;
    return 1;
  }

  std::filesystem::remove(out);
  return 0;
}
