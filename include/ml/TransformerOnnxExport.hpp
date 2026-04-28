#pragma once

#include <cstdint>
#include <filesystem>
#include <memory>

namespace trade {
namespace ml {

std::shared_ptr<::ONNX_NAMESPACE::ModelProto>
export_transformer_to_onnx(const std::filesystem::path &output_path,
                           int64_t input_features);

} // namespace ml
} // namespace trade
