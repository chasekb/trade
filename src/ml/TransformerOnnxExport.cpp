#include "ml/TransformerOnnxExport.hpp"

#include "ml/TransformerModel.hpp"
#include <cmath>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
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
constexpr double kLayerNormEps = 1e-5;

struct ChannelFirstLinearImpl : torch::nn::Module {
  ChannelFirstLinearImpl(int64_t in_channels, int64_t out_channels)
      : in_channels_(in_channels),
        out_channels_(out_channels),
        weight(torch::empty({out_channels, in_channels})),
        bias(torch::empty({out_channels})) {
    register_buffer("weight", weight);
    register_buffer("bias", bias);
  }

  torch::Tensor forward(const torch::Tensor &x) {
    const auto input_parts = x.split(1, 1);
    const auto weight_rows = weight.split(1, 0);
    const auto bias_parts = bias.split(1, 0);

    std::vector<torch::Tensor> outputs;
    outputs.reserve(static_cast<size_t>(out_channels_));
    for (int64_t o = 0; o < out_channels_; ++o) {
      const auto coeffs = weight_rows[static_cast<size_t>(o)].split(1, 1);
      torch::Tensor y = input_parts[0] * 0 + bias_parts[static_cast<size_t>(o)];
      for (int64_t c = 0; c < in_channels_; ++c) {
        y = y + input_parts[static_cast<size_t>(c)] *
                    coeffs[static_cast<size_t>(c)];
      }
      outputs.push_back(y);
    }
    return torch::cat(outputs, 1);
  }

  int64_t in_channels_;
  int64_t out_channels_;
  torch::Tensor weight;
  torch::Tensor bias;
};
TORCH_MODULE(ChannelFirstLinear);

struct ChannelFirstLayerNormImpl : torch::nn::Module {
  explicit ChannelFirstLayerNormImpl(int64_t channels)
      : weight(torch::ones({channels})), bias(torch::zeros({channels})) {
    register_buffer("weight", weight);
    register_buffer("bias", bias);
  }

  torch::Tensor forward(const torch::Tensor &x) {
    auto mean = x.mean(1, true);
    auto centered = x - mean;
    auto var = centered.mul(centered).mean(1, true);
    auto normalized = centered / torch::sqrt(var + kLayerNormEps);
    return normalized * weight.unsqueeze(0).unsqueeze(-1) +
           bias.unsqueeze(0).unsqueeze(-1);
  }

  torch::Tensor weight;
  torch::Tensor bias;
};
TORCH_MODULE(ChannelFirstLayerNorm);

struct ChannelFirstPatchEmbeddingImpl : torch::nn::Module {
  ChannelFirstPatchEmbeddingImpl(int64_t n_features, int64_t patch_size,
                                 int64_t lookback, int64_t embedding_dim)
      : patch_size_(patch_size),
        num_patches_((lookback + patch_size - 1) / patch_size),
        projection(ChannelFirstLinear(n_features * patch_size, embedding_dim)) {
    register_module("projection", projection);
  }

  torch::Tensor forward(torch::Tensor x) {
    const auto time_tokens = x.split(1, 2);
    std::vector<torch::Tensor> patches;
    patches.reserve(static_cast<size_t>(num_patches_));
    for (int64_t patch = 0; patch < num_patches_; ++patch) {
      std::vector<torch::Tensor> values;
      values.reserve(static_cast<size_t>(patch_size_));
      for (int64_t offset = 0; offset < patch_size_; ++offset) {
        const int64_t index = patch * patch_size_ + offset;
        values.push_back(time_tokens[static_cast<size_t>(index)]);
      }
      patches.push_back(projection->forward(torch::cat(values, 1)));
    }
    return torch::cat(patches, 2);
  }

  int64_t patch_size_;
  int64_t num_patches_;
  ChannelFirstLinear projection;
};
TORCH_MODULE(ChannelFirstPatchEmbedding);

struct ChannelFirstCausalSelfAttentionImpl : torch::nn::Module {
  ChannelFirstCausalSelfAttentionImpl(int64_t embedding_dim, int64_t n_heads,
                                      double dropout = 0.1)
      : embedding_dim_(embedding_dim),
        n_heads_(n_heads),
        head_dim_(embedding_dim / n_heads),
        qkv(ChannelFirstLinear(embedding_dim, embedding_dim * 3)),
        proj(ChannelFirstLinear(embedding_dim, embedding_dim)),
        attn_dropout(torch::nn::Dropout(dropout)),
        res_dropout(torch::nn::Dropout(dropout)) {
    if (embedding_dim % n_heads != 0) {
      throw std::runtime_error(
          "Transformer embedding dimension must be divisible by number of heads");
    }
    register_module("qkv", qkv);
    register_module("proj", proj);
    register_module("attn_dropout", attn_dropout);
    register_module("res_dropout", res_dropout);
  }

  torch::Tensor forward(torch::Tensor x) {
    const auto qkv_out = qkv->forward(x);
    const auto qkv_parts = qkv_out.split(embedding_dim_, 1);
    const auto q_tokens = qkv_parts[0].split(1, 2);
    const auto k_tokens = qkv_parts[1].split(1, 2);
    const auto v_tokens = qkv_parts[2].split(1, 2);

    std::vector<torch::Tensor> token_outputs;
    token_outputs.reserve(q_tokens.size());
    for (size_t i = 0; i < q_tokens.size(); ++i) {
      const auto q_heads = q_tokens[i].split(head_dim_, 1);

      std::vector<torch::Tensor> head_outputs;
      head_outputs.reserve(static_cast<size_t>(n_heads_));
      for (int64_t h = 0; h < n_heads_; ++h) {
        const auto q_h = q_heads[static_cast<size_t>(h)];

        std::vector<torch::Tensor> score_cols;
        score_cols.reserve(k_tokens.size());
        for (size_t j = 0; j < k_tokens.size(); ++j) {
          const auto k_heads = k_tokens[j].split(head_dim_, 1);
          auto score = (q_h * k_heads[static_cast<size_t>(h)]).sum(1, true) *
                       (1.0 / std::sqrt(static_cast<double>(head_dim_)));
          if (j > i) {
            score = torch::full_like(score, -1e9);
          }
          score_cols.push_back(score);
        }

        auto attn_row = torch::softmax(torch::cat(score_cols, 2), -1);
        attn_row = attn_dropout->forward(attn_row);

        torch::Tensor head_output;
        for (size_t j = 0; j < v_tokens.size(); ++j) {
          const auto v_heads = v_tokens[j].split(head_dim_, 1);
          auto attn_ij = attn_row.split(1, 2)[j];
          auto weighted = v_heads[static_cast<size_t>(h)] * attn_ij;
          head_output = head_output.defined() ? head_output + weighted
                                              : weighted;
        }
        head_outputs.push_back(head_output);
      }
      token_outputs.push_back(torch::cat(head_outputs, 1));
    }

    auto y = torch::cat(token_outputs, 2);
    return res_dropout->forward(proj->forward(y));
  }

  int64_t embedding_dim_;
  int64_t n_heads_;
  int64_t head_dim_;
  ChannelFirstLinear qkv;
  ChannelFirstLinear proj;
  torch::nn::Dropout attn_dropout;
  torch::nn::Dropout res_dropout;
};
TORCH_MODULE(ChannelFirstCausalSelfAttention);

struct ChannelFirstTransformerBlockImpl : torch::nn::Module {
  ChannelFirstTransformerBlockImpl(int64_t embedding_dim, int64_t n_heads,
                                   double dropout = 0.1)
      : ln1(ChannelFirstLayerNorm(embedding_dim)),
        ln2(ChannelFirstLayerNorm(embedding_dim)),
        attn(ChannelFirstCausalSelfAttention(embedding_dim, n_heads, dropout)),
        mlp_fc1(ChannelFirstLinear(embedding_dim, 4 * embedding_dim)),
        mlp_act(torch::nn::GELU()),
        mlp_fc2(ChannelFirstLinear(4 * embedding_dim, embedding_dim)),
        mlp_dropout(torch::nn::Dropout(dropout)) {
    register_module("ln1", ln1);
    register_module("ln2", ln2);
    register_module("attn", attn);
    register_module("mlp_fc1", mlp_fc1);
    register_module("mlp_act", mlp_act);
    register_module("mlp_fc2", mlp_fc2);
    register_module("mlp_dropout", mlp_dropout);
  }

  torch::Tensor forward(torch::Tensor x) {
    x = x + attn->forward(ln1->forward(x));
    auto y = mlp_fc1->forward(ln2->forward(x));
    y = mlp_act->forward(y);
    y = mlp_fc2->forward(y);
    y = mlp_dropout->forward(y);
    return x + y;
  }

  ChannelFirstLayerNorm ln1, ln2;
  ChannelFirstCausalSelfAttention attn;
  ChannelFirstLinear mlp_fc1;
  torch::nn::GELU mlp_act;
  ChannelFirstLinear mlp_fc2;
  torch::nn::Dropout mlp_dropout;
};
TORCH_MODULE(ChannelFirstTransformerBlock);

struct ChannelFirstStockTransformerImpl : torch::nn::Module {
  ChannelFirstStockTransformerImpl(int64_t n_features, int64_t lookback,
                                   int64_t patch_size, int64_t embedding_dim,
                                   int64_t n_heads, int64_t n_layers,
                                   double dropout_rate = 0.1)
      : lookback_(lookback),
        patch_size_(patch_size),
        embedding_dim_(embedding_dim),
        num_patches_((lookback + patch_size - 1) / patch_size),
        patch_embed(ChannelFirstPatchEmbedding(n_features, patch_size, lookback,
                                               embedding_dim)),
        dropout_layer(torch::nn::Dropout(dropout_rate)),
        blocks(torch::nn::ModuleList()),
        ln_f(ChannelFirstLayerNorm(embedding_dim)),
        head(ChannelFirstLinear(embedding_dim, 1)) {
    pos_embed = torch::zeros({1, embedding_dim, num_patches_});
    register_buffer("pos_embed", pos_embed);

    for (int64_t i = 0; i < n_layers; ++i) {
      blocks->push_back(ChannelFirstTransformerBlock(embedding_dim, n_heads,
                                                     dropout_rate));
    }

    register_module("patch_embed", patch_embed);
    register_module("dropout", dropout_layer);
    register_module("blocks", blocks);
    register_module("ln_f", ln_f);
    register_module("head", head);
  }

  torch::Tensor forward(torch::Tensor x) {
    x = patch_embed->forward(x);
    x = x + pos_embed;
    x = dropout_layer->forward(x);

    for (auto &block : *blocks) {
      x = block->as<ChannelFirstTransformerBlock>()->forward(x);
    }

    x = ln_f->forward(x);
    const auto tokens = x.split(1, 2);
    return head->forward(tokens.back());
  }

  int64_t lookback_;
  int64_t patch_size_;
  int64_t embedding_dim_;
  int64_t num_patches_;
  ChannelFirstPatchEmbedding patch_embed;
  torch::Tensor pos_embed;
  torch::nn::Dropout dropout_layer;
  torch::nn::ModuleList blocks;
  ChannelFirstLayerNorm ln_f;
  ChannelFirstLinear head;
};
TORCH_MODULE(ChannelFirstStockTransformer);

void copy_tensor(const torch::Tensor &dst, const torch::Tensor &src) {
  dst.copy_(src);
}

void copy_linear(const torch::nn::Linear &dst, const torch::nn::Linear &src) {
  dst->weight.copy_(src->weight);
  dst->bias.copy_(src->bias);
}

void copy_channel_first_linear(const ChannelFirstLinear &dst,
                               const torch::nn::Linear &src) {
  copy_tensor(dst->weight, src->weight);
  copy_tensor(dst->bias, src->bias);
}

void copy_patch_projection(const ChannelFirstLinear &dst,
                           const torch::nn::Conv1d &src) {
  dst->weight.copy_(src->weight.permute({0, 2, 1}).contiguous().flatten(1));
  dst->bias.copy_(src->bias);
}

void copy_layer_norm(const ChannelFirstLayerNorm &dst,
                     const torch::nn::LayerNorm &src) {
  copy_tensor(dst->weight, src->weight);
  copy_tensor(dst->bias, src->bias);
}

void copy_transformer_weights(const trade::ml::StockTransformer &source,
                              const ChannelFirstStockTransformer &target) {
  copy_patch_projection(target->patch_embed->projection,
                        source->patch_embed->projection);
  copy_tensor(target->pos_embed, source->pos_embed.permute({0, 2, 1}).contiguous());
  copy_channel_first_linear(target->head, source->head);
  copy_layer_norm(target->ln_f, source->ln_f);

  auto source_block_it = source->blocks->begin();
  auto target_block_it = target->blocks->begin();
  for (; source_block_it != source->blocks->end() &&
         target_block_it != target->blocks->end();
       ++source_block_it, ++target_block_it) {
    auto source_block = (*source_block_it)->as<trade::ml::TransformerBlock>();
    auto target_block = (*target_block_it)->as<ChannelFirstTransformerBlock>();

    copy_layer_norm(target_block->ln1, source_block->ln1);
    copy_layer_norm(target_block->ln2, source_block->ln2);
    copy_channel_first_linear(target_block->attn->qkv, source_block->attn->qkv);
    copy_channel_first_linear(target_block->attn->proj, source_block->attn->proj);
    copy_channel_first_linear(target_block->mlp_fc1, source_block->mlp_fc1);
    copy_channel_first_linear(target_block->mlp_fc2, source_block->mlp_fc2);
  }
}
} // namespace

namespace trade {
namespace ml {

std::shared_ptr<::ONNX_NAMESPACE::ModelProto>
export_transformer_to_onnx(const std::filesystem::path &output_path,
                           int64_t input_features) {
  if (input_features <= 0) {
    throw std::runtime_error(
        "Transformer input feature dimension must be positive");
  }

  torch::NoGradGuard no_grad;

  auto source_model = trade::ml::StockTransformer(
      input_features, kTransformerLookback, kTransformerPatchSize,
      kTransformerEmbeddingDim, kTransformerHeads, kTransformerLayers,
      kTransformerDropout);
  source_model->eval();

  auto export_model = ChannelFirstStockTransformer(
      input_features, kTransformerLookback, kTransformerPatchSize,
      kTransformerEmbeddingDim, kTransformerHeads, kTransformerLayers,
      kTransformerDropout);
  copy_transformer_weights(source_model, export_model);
  export_model->eval();

  for (auto &parameter : export_model->parameters()) {
    parameter.requires_grad_(false);
  }
  auto sample = torch::zeros(
      {1, input_features, kTransformerLookback},
      torch::TensorOptions().dtype(torch::kFloat32));

  torch::jit::Stack inputs;
  inputs.emplace_back(sample);

  auto traced = torch::jit::tracer::trace(
      std::move(inputs),
      [export_model](torch::jit::Stack stack) mutable -> torch::jit::Stack {
        auto input = stack.at(0).toTensor();
        auto output = export_model->forward(input);
        return {output};
      },
      [](const at::Tensor &) { return std::string("sequence_input"); }, false,
      false, nullptr, {"sequence_input"});

  auto graph = traced.first->graph;
  auto export_result = torch::jit::export_onnx(
      graph, {}, kTransformerOpsetVersion, {}, false,
      torch::onnx::OperatorExportTypes::ONNX, true, true, {}, true, false,
      std::string());

  auto model_proto = std::get<0>(export_result);
  if (model_proto == nullptr) {
    throw std::runtime_error("Failed to create transformer ONNX model proto");
  }

  if (!output_path.parent_path().empty()) {
    std::filesystem::create_directories(output_path.parent_path());
  }
  std::ofstream out(output_path, std::ios::binary);
  if (!out.is_open()) {
    throw std::runtime_error("Failed to open transformer ONNX output path: " +
                             output_path.string());
  }

  const std::string onnx_bytes =
      torch::jit::serialize_model_proto_to_string(model_proto);
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

  return model_proto;
}

} // namespace ml
} // namespace trade
