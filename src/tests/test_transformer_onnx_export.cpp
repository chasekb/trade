#include "ml/TransformerOnnxExport.hpp"

#include <array>
#include <exception>
#include <filesystem>
#include <iostream>
#include <onnxruntime/onnxruntime_cxx_api.h>
#include <vector>

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

  try {
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "transformer_onnx_export_test");
    Ort::SessionOptions session_options;
    session_options.SetIntraOpNumThreads(1);
    Ort::Session session(env, out.c_str(), session_options);

    std::array<float, 600> input{};
    std::array<int64_t, 3> input_dims = {1, 10, 60};
    auto memory_info =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    auto input_tensor = Ort::Value::CreateTensor<float>(
        memory_info, input.data(), input.size(), input_dims.data(),
        input_dims.size());

    Ort::AllocatorWithDefaultOptions allocator;
    auto input_name = session.GetInputNameAllocated(0, allocator);
    auto output_name = session.GetOutputNameAllocated(0, allocator);
    const char *input_names[] = {input_name.get()};
    const char *output_names[] = {output_name.get()};

    auto outputs = session.Run(Ort::RunOptions{nullptr}, input_names,
                               &input_tensor, 1, output_names, 1);
    if (outputs.empty() ||
        outputs[0].GetTensorTypeAndShapeInfo().GetElementCount() !=
            input.size()) {
      std::cerr << "Transformer ONNX export produced unexpected output"
                << std::endl;
      return 1;
    }
  } catch (const std::exception &ex) {
    std::cerr << "Transformer ONNX export is not loadable: " << ex.what()
              << std::endl;
    return 1;
  }

  std::filesystem::remove(out);
  return 0;
}
