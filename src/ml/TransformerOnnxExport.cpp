#include "ml/TransformerOnnxExport.hpp"

#include "ml/TransformerModel.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

#include <spdlog/spdlog.h>
#include <torch/csrc/jit/frontend/tracer.h>
#include <torch/csrc/jit/serialization/export.h>

namespace {
constexpr int64_t kTransformerLookback = 60;
constexpr int64_t kTransformerPatchSize = 5;
constexpr int64_t kTransformerEmbeddingDim = 64;
constexpr int64_t kTransformerHeads = 4;
constexpr int64_t kTransformerLayers = 3;
constexpr double kTransformerDropout = 0.1;
constexpr int kTransformerOpsetVersion = 17;
} // namespace

namespace trade {
namespace ml {

void export_transformer_to_onnx(const std::filesystem::path &output_path,
                                int64_t input_features) {
  if (input_features <= 0) {
    throw std::runtime_error(
        "Transformer input feature dimension must be positive");
  }

  if (!output_path.parent_path().empty()) {
    std::filesystem::create_directories(output_path.parent_path());
  }

  auto model = trade::ml::StockTransformer(
      input_features, kTransformerLookback, kTransformerPatchSize,
      kTransformerEmbeddingDim, kTransformerHeads, kTransformerLayers,
      kTransformerDropout);
  model->eval();

  for (auto &parameter : model->parameters()) {
    parameter.requires_grad_(false);
  }

  torch::NoGradGuard no_grad;
  auto sample = torch::zeros({1, kTransformerLookback, input_features},
                             torch::TensorOptions().dtype(torch::kFloat32));

  torch::jit::Stack inputs;
  inputs.emplace_back(sample);

  auto traced = torch::jit::tracer::trace(
      std::move(inputs),
      [model](torch::jit::Stack stack) mutable -> torch::jit::Stack {
        auto input = stack.at(0).toTensor();
        auto output = model->forward(input);
        return {output};
      },
      [](const at::Tensor &) { return std::string("sequence_input"); }, false,
      false, nullptr, {"sequence_input"});

  auto graph = traced.first->graph;
  const std::map<std::string, at::Tensor> initializers;
  const std::unordered_map<std::string, std::unordered_map<int64_t, std::string>>
      dynamic_axes;

  auto [model_proto, raw_data_export_map, symbol_dim_map, success, node_names] =
      torch::jit::export_onnx(graph, initializers, kTransformerOpsetVersion,
                              dynamic_axes);

  (void)raw_data_export_map;
  (void)symbol_dim_map;
  (void)success;
  (void)node_names;

  const std::string onnx_bytes =
      torch::jit::serialize_model_proto_to_string(model_proto);
  torch::jit::check_onnx_proto(onnx_bytes);

  std::ofstream out(output_path, std::ios::binary | std::ios::trunc);
  if (!out.is_open()) {
    throw std::runtime_error("Failed to open transformer ONNX output path: " +
                             output_path.string());
  }
  if (!out.write(onnx_bytes.data(),
                 static_cast<std::streamsize>(onnx_bytes.size()))) {
    throw std::runtime_error("Failed to serialize transformer ONNX model to " +
                             output_path.string());
  }
  out.close();

  const auto file_size = std::filesystem::file_size(output_path);
  if (file_size == 0) {
    throw std::runtime_error("Serialized transformer ONNX model is empty: " +
                             output_path.string());
  }

  spdlog::info("Transformer model package prepared at {}",
               output_path.parent_path().string());
}

} // namespace ml
} // namespace trade
