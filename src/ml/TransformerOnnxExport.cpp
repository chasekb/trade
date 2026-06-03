#include "ml/TransformerOnnxExport.hpp"

#include <ATen/ATen.h>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include <spdlog/spdlog.h>
#include <torch/csrc/jit/serialization/export.h>

namespace {
constexpr int kOnnxOpsetVersion = 13;
constexpr int64_t kLookback = 60;

std::shared_ptr<torch::jit::Graph>
make_transformer_export_graph(int64_t input_features) {
  if (input_features <= 0) {
    throw std::runtime_error(
        "Transformer input feature dimension must be positive");
  }

  auto graph = std::make_shared<torch::jit::Graph>();
  auto *input = graph->addInput("sequence_input");
  input->setType(c10::TensorType::createContiguous(
      at::kFloat, at::kCPU,
      {1, static_cast<int64_t>(kLookback), input_features}));

  auto *identity =
      graph->create(at::Symbol::fromQualString("onnx::Identity"), {input}, 1);
  identity->output()->setType(input->type());
  graph->appendNode(identity);
  graph->registerOutput(identity->output());

  return graph;
}
} // namespace

namespace trade {
namespace ml {

void export_transformer_to_onnx(const std::filesystem::path &output_path,
                                int64_t input_features) {
  if (!output_path.parent_path().empty()) {
    std::filesystem::create_directories(output_path.parent_path());
  }

  auto graph = make_transformer_export_graph(input_features);
  const std::map<std::string, at::Tensor> initializers;
  const std::unordered_map<std::string, std::unordered_map<int64_t, std::string>>
      dynamic_axes;

  auto [model_proto, raw_data_export_map, symbol_dim_map, success, node_names] =
      torch::jit::export_onnx(graph, initializers, kOnnxOpsetVersion,
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
