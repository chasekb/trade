#pragma once

#include <cstdint>
#include <filesystem>

namespace trade {
namespace ml {

void export_transformer_to_onnx(const std::filesystem::path &output_path,
                                int64_t input_features);

} // namespace ml
} // namespace trade
