
#include "ml/ONNXModelManager.hpp"
#include <algorithm>
#include <filesystem>
#include <numeric>
#include <spdlog/spdlog.h>

namespace ml {

void ONNXModelManager::reset_sessions() {
  regressor_session_.reset();
  classifier_session_.reset();
  transformer_session_.reset();
  input_dim_ = 0;
  transformer_lookback_ = 0;
  transformer_features_ = 0;
}

ONNXModelManager::ONNXModelManager()
    : env_(ORT_LOGGING_LEVEL_WARNING, "ONNXModelManager"), session_options_() {
  session_options_.SetIntraOpNumThreads(1);
  session_options_.SetGraphOptimizationLevel(
      GraphOptimizationLevel::ORT_ENABLE_EXTENDED);
}

bool ONNXModelManager::load_models(const std::string &model_dir) {
  model_dir_ = model_dir;
  try {
    reset_sessions();
    std::filesystem::path dir(model_dir);
    std::string reg_path = (dir / "regressor.onnx").string();
    std::string cls_path = (dir / "classifier.onnx").string();
    std::string trans_path = (dir / "transformer.onnx").string();

    if (std::filesystem::exists(trans_path)) {
#ifdef _WIN32
      std::wstring w_trans_path(trans_path.begin(), trans_path.end());
      transformer_session_ = std::make_unique<Ort::Session>(
          env_, w_trans_path.c_str(), session_options_);
#else
      transformer_session_ = std::make_unique<Ort::Session>(
          env_, trans_path.c_str(), session_options_);
#endif
      // Get transformer info
      auto info =
          transformer_session_->GetInputTypeInfo(0).GetTensorTypeAndShapeInfo();
      auto shape = info.GetShape();
      if (shape.size() >= 3) {
        transformer_lookback_ = shape[1];
        transformer_features_ = shape[2];
      }
      spdlog::info("Loaded Transformer model. Lookback: {}, Features: {}",
                   transformer_lookback_, transformer_features_);
    }

    const bool has_regressor = std::filesystem::exists(reg_path);
    const bool has_classifier = std::filesystem::exists(cls_path);
    const bool has_transformer = std::filesystem::exists(trans_path);

    if (!has_regressor && !has_classifier && !has_transformer) {
      spdlog::error("No ONNX models found in {}", model_dir);
      return false;
    }

    if (has_regressor) {
      // Load Regressor
#ifdef _WIN32
      std::wstring w_reg_path(reg_path.begin(), reg_path.end());
      regressor_session_ = std::make_unique<Ort::Session>(
          env_, w_reg_path.c_str(), session_options_);
#else
      regressor_session_ = std::make_unique<Ort::Session>(env_, reg_path.c_str(),
                                                          session_options_);
#endif
    }

    if (has_classifier) {
      // Load Classifier
#ifdef _WIN32
      std::wstring w_cls_path(cls_path.begin(), cls_path.end());
      classifier_session_ = std::make_unique<Ort::Session>(
          env_, w_cls_path.c_str(), session_options_);
#else
      classifier_session_ = std::make_unique<Ort::Session>(env_, cls_path.c_str(),
                                                           session_options_);
#endif
    }

    Ort::Session *shape_session = regressor_session_ ? regressor_session_.get()
                                                     : classifier_session_.get();
    if (shape_session != nullptr) {
      Ort::TypeInfo type_info = shape_session->GetInputTypeInfo(0);
      auto tensor_info = type_info.GetTensorTypeAndShapeInfo();
      auto input_shape = tensor_info.GetShape();

      if (input_shape.size() >= 2) {
        input_dim_ = input_shape[1];
      } else {
        input_dim_ = input_shape[0];
      }
    }

    spdlog::info(
        "Loaded ONNX models from {}. Capabilities: regressor={}, classifier={}, transformer={}, expected input dimension: {}",
        model_dir, has_regressor, has_classifier, has_transformer, input_dim_);
    return true;
  } catch (const std::exception &e) {
    spdlog::error("Failed to load ONNX models: {}", e.what());
    return false;
  }
}

double ONNXModelManager::predict_pnl(const std::vector<double> &features) {
  if (!regressor_session_)
    return 0.0;
  auto outputs = run_inference(*regressor_session_, features);
  return outputs.empty() ? 0.0 : static_cast<double>(outputs[0]);
}

double ONNXModelManager::predict_win_prob(const std::vector<double> &features) {
  if (!classifier_session_)
    return 0.5;
  auto outputs = run_inference(*classifier_session_, features);
  // For many classifiers, outputs[0] might be the class index (0 or 1)
  // and outputs[1] might be probabilities.
  // However, simple exports might just have probabilities as output 0.
  // Let's assume it's the score/probability.
  return outputs.empty() ? 0.5 : static_cast<double>(outputs[0]);
}

double ONNXModelManager::predict_transformer(
    const std::vector<std::vector<double>> &sequence) {
  if (!transformer_session_)
    return 0.0;

  try {
    size_t seq_len = sequence.size();
    size_t n_features = sequence.empty() ? 0 : sequence[0].size();

    if (seq_len != transformer_lookback_ ||
        n_features != transformer_features_) {
      spdlog::warn("Transformer input mismatch: expected {}x{}, got {}x{}",
                   transformer_lookback_, transformer_features_, seq_len,
                   n_features);
    }

    std::vector<float> input_tensor_values;
    input_tensor_values.reserve(transformer_lookback_ * transformer_features_);

    for (size_t i = 0; i < transformer_lookback_; ++i) {
      if (i < seq_len) {
        for (size_t j = 0; j < transformer_features_; ++j) {
          input_tensor_values.push_back(j < sequence[i].size()
                                            ? static_cast<float>(sequence[i][j])
                                            : 0.0f);
        }
      } else {
        for (size_t j = 0; j < transformer_features_; ++j)
          input_tensor_values.push_back(0.0f);
      }
    }

    std::array<int64_t, 3> input_shape = {
        1, static_cast<int64_t>(transformer_lookback_),
        static_cast<int64_t>(transformer_features_)};
    auto memory_info =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info, input_tensor_values.data(), input_tensor_values.size(),
        input_shape.data(), input_shape.size());

    Ort::AllocatorWithDefaultOptions allocator;
    auto input_name_ptr =
        transformer_session_->GetInputNameAllocated(0, allocator);
    auto output_name_ptr =
        transformer_session_->GetOutputNameAllocated(0, allocator);
    const char *input_names[] = {input_name_ptr.get()};
    const char *output_names[] = {output_name_ptr.get()};

    auto output_tensors =
        transformer_session_->Run(Ort::RunOptions{nullptr}, input_names,
                                  &input_tensor, 1, output_names, 1);
    float *output_data = output_tensors[0].GetTensorMutableData<float>();
    return static_cast<double>(output_data[0]);

  } catch (const std::exception &e) {
    spdlog::error("Transformer inference failed: {}", e.what());
    return 0.0;
  }
}

std::vector<float>
ONNXModelManager::run_inference(Ort::Session &session,
                                const std::vector<double> &features) {
  try {
    // Convert double to float for ONNX
    std::vector<float> input_tensor_values(features.begin(), features.end());

    // Pad or truncate if needed (should match input_dim_)
    if (input_tensor_values.size() != input_dim_) {
      spdlog::warn("Inference feature count mismatch: got {}, expected {}",
                   input_tensor_values.size(), input_dim_);
      input_tensor_values.resize(input_dim_, 0.0f);
    }

    std::array<int64_t, 2> input_shape = {1, static_cast<int64_t>(input_dim_)};

    auto memory_info =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory_info, input_tensor_values.data(), input_tensor_values.size(),
        input_shape.data(), input_shape.size());

    const char *input_names[] = {"float_input"};
    const char *output_names[] = {
        "variable"}; // Typical skl2onnx output name if not specified

    // Try to get actual names if they are different
    Ort::AllocatorWithDefaultOptions allocator;
    auto input_name_ptr = session.GetInputNameAllocated(0, allocator);
    auto output_name_ptr = session.GetOutputNameAllocated(0, allocator);

    const char *actual_input_names[] = {input_name_ptr.get()};
    const char *actual_output_names[] = {output_name_ptr.get()};

    auto output_tensors =
        session.Run(Ort::RunOptions{nullptr}, actual_input_names, &input_tensor,
                    1, actual_output_names, 1);

    float *output_data = output_tensors[0].GetTensorMutableData<float>();
    size_t output_count =
        output_tensors[0].GetTensorTypeAndShapeInfo().GetElementCount();

    return std::vector<float>(output_data, output_data + output_count);
  } catch (const std::exception &e) {
    spdlog::error("ONNX inference failed: {}", e.what());
    return {};
  }
}

} // namespace ml

namespace ml {

bool ONNXModelManager::reload_models() {
  if (model_dir_.empty())
    return false;
  return load_models(model_dir_);
}

} // namespace ml
