#include "ml/TransformerOnnxExport.hpp"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>

namespace {
constexpr int kTransformerOpsetVersion = 13;
constexpr int64_t kOnnxIrVersion = 8;
constexpr int kTensorProtoFloat = 1;

void append_varint(std::string &out, uint64_t value) {
  while (value >= 0x80) {
    out.push_back(static_cast<char>((value & 0x7f) | 0x80));
    value >>= 7;
  }
  out.push_back(static_cast<char>(value));
}

void append_key(std::string &out, int field_number, int wire_type) {
  append_varint(out, (static_cast<uint64_t>(field_number) << 3) |
                         static_cast<uint64_t>(wire_type));
}

void append_int64(std::string &out, int field_number, int64_t value) {
  append_key(out, field_number, 0);
  append_varint(out, static_cast<uint64_t>(value));
}

void append_int32(std::string &out, int field_number, int value) {
  append_int64(out, field_number, value);
}

void append_string(std::string &out, int field_number, const std::string &value) {
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

std::string make_tensor_type() {
  std::string tensor_type;
  append_int32(tensor_type, 1, kTensorProtoFloat);
  return tensor_type;
}

std::string make_type_proto() {
  std::string type_proto;
  append_message(type_proto, 1, make_tensor_type());
  return type_proto;
}

std::string make_value_info(const std::string &name) {
  std::string value_info;
  append_string(value_info, 1, name);
  append_message(value_info, 2, make_type_proto());
  return value_info;
}

std::string make_identity_node() {
  std::string node;
  append_string(node, 1, "sequence_input");
  append_string(node, 2, "variable");
  append_string(node, 3, "transformer_identity");
  append_string(node, 4, "Identity");
  return node;
}

std::string make_opset_import() {
  std::string opset;
  append_int64(opset, 2, kTransformerOpsetVersion);
  return opset;
}

std::string make_graph() {
  std::string graph;
  append_message(graph, 1, make_identity_node());
  append_string(graph, 2, "trade_transformer_runtime_fallback");
  append_message(graph, 11, make_value_info("sequence_input"));
  append_message(graph, 12, make_value_info("variable"));
  return graph;
}

std::string make_model() {
  std::string model;
  append_int64(model, 1, kOnnxIrVersion);
  append_string(model, 2, "trade-cpp");
  append_message(model, 7, make_graph());
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

  const std::string onnx_bytes = make_model();
  std::ofstream out(output_path, std::ios::binary);
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
