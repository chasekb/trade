
#include "ml/ONNXModelManager.hpp"
#include <array>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

namespace ml {

void ONNXModelManager::reset_sessions() {
  regressor_session_.reset();
  classifier_session_.reset();
  transformer_session_.reset();
  input_dim_ = 0;
  transformer_lookback_ = 0;
  transformer_features_ = 0;
  transformer_channels_first_ = false;
}

ONNXModelManager::ONNXModelManager()
    : env_(ORT_LOGGING_LEVEL_WARNING, "ONNXModelManager"), session_options_() {
  session_options_.SetIntraOpNumThreads(1);
  session_options_.SetGraphOptimizationLevel(
      GraphOptimizationLevel::ORT_ENABLE_EXTENDED);
}

bool ONNXModelManager::load_models(const std::string &model_dir) {
  try {
    std::filesystem::path dir(model_dir);
    const std::string reg_path = (dir / "regressor.onnx").string();
    const std::string cls_path = (dir / "classifier.onnx").string();
    const std::string trans_path = (dir / "transformer.onnx").string();
    const std::filesystem::path transformer_config_path =
        dir / "transformer_config.json";

    std::unique_ptr<Ort::Session> new_regressor_session;
    std::unique_ptr<Ort::Session> new_classifier_session;
    std::unique_ptr<Ort::Session> new_transformer_session;
    std::size_t new_input_dim = 0;
    std::size_t new_transformer_lookback = 0;
    std::size_t new_transformer_features = 0;
    bool new_transformer_channels_first = false;

    if (std::filesystem::exists(transformer_config_path)) {
      try {
        std::ifstream config_stream(transformer_config_path);
        if (config_stream.is_open()) {
          const auto config =
              nlohmann::json::parse(config_stream, nullptr, true, true);
          const std::string layout = config.value("input_layout", "channels_last");
          if (layout == "channels_first") {
            spdlog::warn(
                "Transformer config at {} requests unsupported layout '{}'; loading as channels_last to match the exporter contract",
                transformer_config_path.string(), layout);
          } else if (layout != "channels_last") {
            spdlog::warn(
                "Transformer config at {} has unknown input_layout '{}'; defaulting to channels_last",
                transformer_config_path.string(), layout);
          }
          new_transformer_channels_first = false;
          const std::size_t configured_lookback =
              config.value("lookback", static_cast<std::size_t>(0));
          const std::size_t configured_features =
              config.value("n_features", static_cast<std::size_t>(0));
          if (configured_lookback > 0) {
            new_transformer_lookback = configured_lookback;
          }
          if (configured_features > 0) {
            new_transformer_features = configured_features;
          }
        }
      } catch (const std::exception &e) {
        spdlog::warn("Ignoring transformer config at {} because it could not be parsed: {}",
                     transformer_config_path.string(), e.what());
      }
    }

    const bool has_regressor = std::filesystem::exists(reg_path);
    const bool has_classifier = std::filesystem::exists(cls_path);
    const bool has_transformer = std::filesystem::exists(trans_path);

    if (has_regressor) {
      try {
#ifdef _WIN32
        std::wstring w_reg_path(reg_path.begin(), reg_path.end());
        new_regressor_session = std::make_unique<Ort::Session>(
            env_, w_reg_path.c_str(), session_options_);
#else
        new_regressor_session = std::make_unique<Ort::Session>(
            env_, reg_path.c_str(), session_options_);
#endif
      } catch (const std::exception &e) {
        spdlog::warn("Skipping regressor model at {} because it could not be loaded: {}",
                     reg_path, e.what());
      }
    }

    if (has_classifier) {
      try {
#ifdef _WIN32
        std::wstring w_cls_path(cls_path.begin(), cls_path.end());
        new_classifier_session = std::make_unique<Ort::Session>(
            env_, w_cls_path.c_str(), session_options_);
#else
        new_classifier_session = std::make_unique<Ort::Session>(
            env_, cls_path.c_str(), session_options_);
#endif
      } catch (const std::exception &e) {
        spdlog::warn("Skipping classifier model at {} because it could not be loaded: {}",
                     cls_path, e.what());
      }
    }

    if (has_transformer) {
      try {
#ifdef _WIN32
        std::wstring w_trans_path(trans_path.begin(), trans_path.end());
        new_transformer_session = std::make_unique<Ort::Session>(
            env_, w_trans_path.c_str(), session_options_);
#else
        new_transformer_session = std::make_unique<Ort::Session>(
            env_, trans_path.c_str(), session_options_);
#endif
        if (new_transformer_lookback == 0 || new_transformer_features == 0) {
          try {
            auto info = new_transformer_session->GetInputTypeInfo(0)
                            .GetTensorTypeAndShapeInfo();
            auto shape = info.GetShape();
            if (shape.size() >= 3) {
              if (new_transformer_channels_first) {
                new_transformer_features = static_cast<std::size_t>(shape[1]);
                new_transformer_lookback = static_cast<std::size_t>(shape[2]);
              } else {
                new_transformer_lookback = static_cast<std::size_t>(shape[1]);
                new_transformer_features = static_cast<std::size_t>(shape[2]);
              }
            }
          } catch (const std::exception &shape_error) {
            spdlog::warn(
                "Loaded transformer session at {} but could not read shape metadata: {}",
                trans_path, shape_error.what());
          }
        }
        spdlog::info("Loaded Transformer model. Lookback: {}, Features: {}",
                     new_transformer_lookback, new_transformer_features);
      } catch (const std::exception &e) {
        new_transformer_session.reset();
        new_transformer_lookback = 0;
        new_transformer_features = 0;
        new_transformer_channels_first = false;
        spdlog::warn(
            "Skipping transformer model at {} because it could not be loaded: {}",
            trans_path, e.what());
      }
    }

    const bool has_loaded_regressor = new_regressor_session != nullptr;
    const bool has_loaded_classifier = new_classifier_session != nullptr;
    const bool has_loaded_transformer = new_transformer_session != nullptr;

    if (!has_loaded_regressor && !has_loaded_classifier && !has_loaded_transformer) {
      spdlog::warn("No usable ONNX models found in {}; using neutral fallbacks",
                   model_dir);
      return false;
    }

    Ort::Session *shape_session = new_regressor_session ? new_regressor_session.get()
                                                        : new_classifier_session.get();
    if (shape_session != nullptr) {
      Ort::TypeInfo type_info = shape_session->GetInputTypeInfo(0);
      auto tensor_info = type_info.GetTensorTypeAndShapeInfo();
      auto input_shape = tensor_info.GetShape();

      if (input_shape.size() >= 2) {
        new_input_dim = static_cast<std::size_t>(input_shape[1]);
      } else if (!input_shape.empty()) {
        new_input_dim = static_cast<std::size_t>(input_shape[0]);
      }
    }

    regressor_session_ = std::move(new_regressor_session);
    classifier_session_ = std::move(new_classifier_session);
    transformer_session_ = std::move(new_transformer_session);
    input_dim_ = new_input_dim;
    transformer_lookback_ = new_transformer_lookback;
    transformer_features_ = new_transformer_features;
    transformer_channels_first_ = new_transformer_channels_first;
    model_dir_ = model_dir;

    spdlog::info(
        "Loaded ONNX models from {}. Capabilities: regressor={}, classifier={}, transformer={}, expected input dimension: {}",
        model_dir, has_loaded_regressor, has_loaded_classifier,
        has_loaded_transformer, input_dim_);
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
  if (transformer_lookback_ == 0 || transformer_features_ == 0) {
    spdlog::error(
        "Transformer model is loaded but input dimensions are unavailable");
    return 0.0;
  }

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

    if (transformer_channels_first_) {
      for (size_t j = 0; j < transformer_features_; ++j) {
        for (size_t i = 0; i < transformer_lookback_; ++i) {
          input_tensor_values.push_back(
              (i < seq_len && j < sequence[i].size())
                  ? static_cast<float>(sequence[i][j])
                  : 0.0f);
        }
      }
    } else {
      for (size_t i = 0; i < transformer_lookback_; ++i) {
        if (i < seq_len) {
          for (size_t j = 0; j < transformer_features_; ++j) {
            input_tensor_values.push_back(
                j < sequence[i].size() ? static_cast<float>(sequence[i][j])
                                       : 0.0f);
          }
        } else {
          for (size_t j = 0; j < transformer_features_; ++j)
            input_tensor_values.push_back(0.0f);
        }
      }
    }

    std::array<int64_t, 3> input_shape = transformer_channels_first_
                                             ? std::array<int64_t, 3>{
                                                   1,
                                                   static_cast<int64_t>(transformer_features_),
                                                   static_cast<int64_t>(transformer_lookback_)}
                                             : std::array<int64_t, 3>{
                                                   1,
                                                   static_cast<int64_t>(transformer_lookback_),
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
