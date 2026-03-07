
#pragma once
#include <memory>
#include <onnxruntime/onnxruntime_cxx_api.h>
#include <string>
#include <vector>

namespace ml {

class ONNXModelManager {
public:
  ONNXModelManager();
  ~ONNXModelManager() = default;

  // Load models from directory
  bool load_models(const std::string &model_dir);
  bool reload_models(); // Reload from the same directory

  // Predict PnL (Regression)
  double predict_pnl(const std::vector<double> &features);

  // Predict Win Probability (Classification)
  double predict_win_prob(const std::vector<double> &features);

  // Predict using Transformer (3D input: SeqLen x Features)
  double predict_transformer(const std::vector<std::vector<double>> &sequence);

  bool is_ready() const {
    return regressor_session_ != nullptr && classifier_session_ != nullptr;
  }

private:
  std::vector<float> run_inference(Ort::Session &session,
                                   const std::vector<double> &features);

  Ort::Env env_;
  Ort::SessionOptions session_options_;

  std::unique_ptr<Ort::Session> regressor_session_;
  std::unique_ptr<Ort::Session> classifier_session_;
  std::unique_ptr<Ort::Session> transformer_session_;

  // Feature dimensions expected by the model
  size_t input_dim_ = 0;
  size_t transformer_lookback_ = 0;
  size_t transformer_features_ = 0;
  std::string model_dir_;
};

} // namespace ml
