#pragma once

#include <torch/torch.h>
#include <vector>

namespace trade {
namespace ml {

// Groups temporal features into patches and projects them to embedding
// dimension.
struct PatchEmbeddingImpl : torch::nn::Module {
  PatchEmbeddingImpl(int64_t n_features, int64_t patch_size,
                     int64_t embedding_dim);
  torch::Tensor forward(torch::Tensor x);

  int64_t patch_size_;
  torch::nn::Conv1d projection;
};
TORCH_MODULE(PatchEmbedding);

// Export-friendly causal self-attention.
struct CausalSelfAttentionImpl : torch::nn::Module {
  CausalSelfAttentionImpl(int64_t embedding_dim, int64_t n_heads,
                          double dropout = 0.1);
  torch::Tensor forward(torch::Tensor x);

  int64_t embedding_dim_;
  torch::nn::Linear qkv;
  torch::nn::Linear proj;
  torch::nn::Dropout attn_dropout;
  torch::nn::Dropout res_dropout;
};
TORCH_MODULE(CausalSelfAttention);

// Standard Transformer Block (Pre-Norm).
struct TransformerBlockImpl : torch::nn::Module {
  TransformerBlockImpl(int64_t embedding_dim, int64_t n_heads,
                       double dropout = 0.1);
  torch::Tensor forward(torch::Tensor x);

  torch::nn::LayerNorm ln1, ln2;
  CausalSelfAttention attn;
  torch::nn::Sequential mlp;
};
TORCH_MODULE(TransformerBlock);

// The full Patch-based Temporal Transformer model.
struct StockTransformerImpl : torch::nn::Module {
  StockTransformerImpl(int64_t n_features, int64_t lookback, int64_t patch_size,
                       int64_t embedding_dim, int64_t n_heads, int64_t n_layers,
                       double dropout = 0.1);
  torch::Tensor forward(torch::Tensor x);

  int64_t lookback_;
  int64_t patch_size_;
  PatchEmbedding patch_embed;
  torch::Tensor pos_embed;
  torch::nn::Dropout dropout;
  torch::nn::ModuleList blocks;
  torch::nn::LayerNorm ln_f;
  torch::nn::Linear head;
};
TORCH_MODULE(StockTransformer);

} // namespace ml
} // namespace trade
