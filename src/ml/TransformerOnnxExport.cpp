#include "ml/TransformerOnnxExport.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

namespace {
constexpr int kOnnxOpsetVersion = 13;
constexpr int64_t kOnnxIrVersion = 8;
constexpr int kTensorProtoFloat = 1;

void append_varint(std::string &out, std::uint64_t value) {
  while (value >= 0x80) {
    out.push_back(static_cast<char>((value & 0x7f) | 0x80));
    value >>= 7;
  }
  out.push_back(static_cast<char>(value));
}

void append_key(std::string &out, int field_number, int wire_type) {
  append_varint(out, (static_cast<std::uint64_t>(field_number) << 3) |
                         static_cast<std::uint64_t>(wire_type));
}

void append_int64(std::string &out, int field_number, std::int64_t value) {
  append_key(out, field_number, 0);
  append_varint(out, static_cast<std::uint64_t>(value));
}

void append_int32(std::string &out, int field_number, int value) {
  append_int64(out, field_number, value);
}

void append_string(std::string &out, int field_number,
                   const std::string &value) {
  append_key(out, field_number, 2);
  append_varint(out, value.size());
  out.append(value);
}

void append_message(std::string &out, int field_number,
                    const std::string &message) {
  append_key(out, field_number, 2);
  append_varint(out, message.size());
  out.append(message);
}

std::string make_tensor_shape(std::int64_t dim_0, std::int64_t dim_1,
                              std::int64_t dim_2) {
  std::string shape;
  {
    std::string dim;
    append_int64(dim, 1, dim_0);
    append_message(shape, 1, dim);
  }
  {
    std::string dim;
    append_int64(dim, 1, dim_1);
    append_message(shape, 1, dim);
  }
  {
    std::string dim;
    append_int64(dim, 1, dim_2);
    append_message(shape, 1, dim);
  }
  return shape;
}

std::string make_tensor_type(std::int64_t dim_0, std::int64_t dim_1,
                             std::int64_t dim_2) {
  std::string tensor_type;
  append_int32(tensor_type, 1, kTensorProtoFloat);
  append_message(tensor_type, 2, make_tensor_shape(dim_0, dim_1, dim_2));
  return tensor_type;
}

std::string make_type_proto(std::int64_t dim_0, std::int64_t dim_1,
                            std::int64_t dim_2) {
  std::string type_proto;
  append_message(type_proto, 1,
                 make_tensor_type(dim_0, dim_1, dim_2));
  return type_proto;
}

std::string make_value_info(const std::string &name, std::int64_t dim_0,
                            std::int64_t dim_1, std::int64_t dim_2) {
  std::string value_info;
  append_string(value_info, 1, name);
  append_message(value_info, 2, make_type_proto(dim_0, dim_1, dim_2));
  return value_info;
}

std::string make_node(const std::string &name, const std::string &input,
                      const std::string &output,
                      const std::string &op_type) {
  std::string node;
  append_string(node, 1, input);
  append_string(node, 2, output);
  append_string(node, 3, name);
  append_string(node, 4, op_type);
  return node;
}

std::string make_opset_import() {
  std::string opset;
  append_string(opset, 1, "");
  append_int64(opset, 2, kOnnxOpsetVersion);
  return opset;
}

std::string make_graph(std::int64_t input_features) {
  constexpr std::int64_t kBatchSize = 1;
  constexpr std::int64_t kLookback = 60;
  std::string graph;
  append_message(graph, 1,
                 make_node("transformer_identity", "sequence_input",
                           "transformer_output", "Identity"));
  append_string(graph, 2, "trade_transformer_identity");
  append_message(graph, 11,
                 make_value_info("sequence_input", kBatchSize, kLookback,
                                 input_features));
  append_message(graph, 12,
                 make_value_info("transformer_output", kBatchSize, kLookback,
                                 input_features));
  return graph;
}

std::string make_model(std::int64_t input_features) {
  std::string model;
  append_int64(model, 1, kOnnxIrVersion);
  append_string(model, 2, "trade-cpp");
  append_message(model, 7, make_graph(input_features));
  append_message(model, 8, make_opset_import());
  return model;
}
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

  const std::string onnx_bytes = make_model(input_features);
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
}

} // namespace ml
} // namespace trade
