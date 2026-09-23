
#pragma once
#include "ml/Calibration.hpp"

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
    return regressor_session_ != nullptr || classifier_session_ != nullptr ||
           transformer_session_ != nullptr;
  }

  bool has_regressor() const { return regressor_session_ != nullptr; }
  bool has_classifier() const { return classifier_session_ != nullptr; }
  // True only when a prediction from this transformer would be real, not
  // the ONNX graph's shape-correct-but-weight-free Identity placeholder
  // (see transformer_config.json's onnx_has_weights, written by
  // ModelTrainer.cpp's write_transformer_config — always false today, since
  // no real ONNX exporter exists). A transformer_weights.pt that failed to
  // load, or an older package that never had one, both correctly report no
  // transformer capability here rather than silently falling back to a
  // meaningless prediction.
  bool has_transformer() const {
    return has_torch_transformer_ ||
           (transformer_session_ != nullptr && onnx_has_weights_);
  }
  bool transformer_input_ready(const std::vector<std::vector<double>> &sequence) const;

  // True when the active transformer's real, gradient-trained weights were
  // loaded from transformer_weights.pt (see ModelTrainer::train_transformer/
  // export_transformer_artifact) via LibTorch, rather than the ONNX graph
  // (transformer.onnx), which remains a shape-correct, weight-free
  // placeholder — LibTorch's C++ API has no ONNX exporter, so this is the
  // only path that currently serves real predictions. Callers must use this
  // to decide which feature representation to feed predict_transformer:
  // true means the caller should build a raw+engineered sequence (see
  // FeatureEngineer::get_raw_transformer_sequence /
  // include/ml/TransformerFeatures.hpp), not the PCA-based
  // get_transformer_sequence.
  bool has_torch_transformer() const { return has_torch_transformer_; }

  // The active transformer's real input contract, read from its config/ONNX
  // shape at load time. Callers must use these instead of assuming a fixed
  // lookback/feature-width, since a retrained model can change either.
  std::size_t transformer_lookback() const { return transformer_lookback_; }
  std::size_t transformer_features() const { return transformer_features_; }

  // Optional post-hoc calibration, loaded from calibration.json beside the
  // model artifacts if present (see fit_and_write_model_calibration). Raw
  // model output is passed through unchanged when no fit is available —
  // absence of a calibration file is never treated as "already calibrated."
  bool has_win_probability_calibration() const {
    return !win_probability_calibration_.empty();
  }
  double calibrate_win_probability(double raw_probability) const;
  bool has_expected_return_calibration() const {
    return !expected_return_calibration_.empty();
  }
  double calibrate_expected_return(double raw_expected_return) const;

private:
  std::vector<float> run_inference(Ort::Session &session,
                                   const std::vector<double> &features,
                                   size_t output_index = 0);
  void reset_sessions();

  Ort::Env env_;
  Ort::SessionOptions session_options_;

  std::unique_ptr<Ort::Session> regressor_session_;
  std::unique_ptr<Ort::Session> classifier_session_;
  std::unique_ptr<Ort::Session> transformer_session_;

  // LibTorch-backed transformer, loaded from transformer_weights.pt when
  // present alongside transformer_config.json. Type-erased
  // (std::shared_ptr<void>) so this widely-included header never has to
  // include TransformerModel.hpp/<torch/torch.h> — only ONNXModelManager.cpp
  // knows the real type (trade::ml::StockTransformer) and
  // static_pointer_casts back to it, mirroring ModelTrainer.hpp's
  // trained_transformer_ member for the same reason.
  std::shared_ptr<void> torch_transformer_;
  bool has_torch_transformer_ = false;
  bool onnx_has_weights_ = false;

  // Feature dimensions expected by the model
  size_t input_dim_ = 0;
  size_t transformer_lookback_ = 0;
  size_t transformer_features_ = 0;
  bool transformer_channels_first_ = false;
  std::string model_dir_;

  trade::ml::CalibrationMap win_probability_calibration_;
  trade::ml::CalibrationMap expected_return_calibration_;
};

} // namespace ml
