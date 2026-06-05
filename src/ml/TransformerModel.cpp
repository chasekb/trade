#include "ml/TransformerModel.hpp"
#include <cmath>

namespace trade {
namespace ml {

PatchEmbeddingImpl::PatchEmbeddingImpl(int64_t n_features, int64_t patch_size,
                                       int64_t embedding_dim)
    : patch_size_(patch_size),
      projection(torch::nn::Conv1d(torch::nn::Conv1dOptions(
          n_features, embedding_dim, patch_size).stride(patch_size))) {
  register_module("projection", projection);
}

torch::Tensor PatchEmbeddingImpl::forward(torch::Tensor x) {
  // x shape: (B, T, F)
  int64_t T = x.size(1);

  if (T % patch_size_ != 0) {
    int64_t padding = patch_size_ - (T % patch_size_);
    x = torch::constant_pad_nd(x, {0, 0, padding, 0}); // Pad temporal dimension
  }

  // Project each temporal patch with ONNX-friendly dimension permutation.
  x = x.permute({0, 2, 1}); // (B, F, T)
  x = projection->forward(x);
  return x.permute({0, 2, 1}); // (B, T/P, E)
}

CausalSelfAttentionImpl::CausalSelfAttentionImpl(int64_t embedding_dim,
                                                 int64_t n_heads,
                                                 double dropout_rate)
    : embedding_dim_(embedding_dim),
      qkv(torch::nn::Linear(embedding_dim, embedding_dim * 3)),
      proj(torch::nn::Linear(embedding_dim, embedding_dim)),
      attn_dropout(torch::nn::Dropout(dropout_rate)),
      res_dropout(torch::nn::Dropout(dropout_rate)) {
  (void)n_heads;
  register_module("qkv", qkv);
  register_module("proj", proj);
  register_module("attn_dropout", attn_dropout);
  register_module("res_dropout", res_dropout);
}

torch::Tensor CausalSelfAttentionImpl::forward(torch::Tensor x) {
  int64_t B = x.size(0);
  int64_t N = x.size(1);
  int64_t D = x.size(2);

  auto qkv_out = qkv->forward(x);
  auto q = qkv_out.slice(-1, 0, D);
  auto k = qkv_out.slice(-1, D, 2 * D);
  auto v = qkv_out.slice(-1, 2 * D, 3 * D);

  auto mask = torch::tril(torch::ones({N, N}, x.options())).unsqueeze(0);

  auto attn = q.matmul(k.permute({0, 2, 1})) *
              (1.0 / std::sqrt(static_cast<double>(D)));
  attn = attn.masked_fill(mask == 0, -1e9);
  attn = torch::softmax(attn, -1);
  attn = attn_dropout->forward(attn);

  auto y = attn.matmul(v); // (B, N, D)

  return res_dropout->forward(proj->forward(y));
}

TransformerBlockImpl::TransformerBlockImpl(int64_t embedding_dim,
                                           int64_t n_heads,
                                           double dropout_rate)
    : ln1(torch::nn::LayerNorm(torch::nn::LayerNormOptions({embedding_dim}))),
      ln2(torch::nn::LayerNorm(torch::nn::LayerNormOptions({embedding_dim}))),
      attn(CausalSelfAttention(embedding_dim, n_heads, dropout_rate)),
      mlp_fc1(torch::nn::Linear(embedding_dim, 4 * embedding_dim)),
      mlp_act(torch::nn::GELU()),
      mlp_fc2(torch::nn::Linear(4 * embedding_dim, embedding_dim)),
      mlp_dropout(torch::nn::Dropout(dropout_rate)) {
  register_module("ln1", ln1);
  register_module("ln2", ln2);
  register_module("attn", attn);
  register_module("mlp_fc1", mlp_fc1);
  register_module("mlp_act", mlp_act);
  register_module("mlp_fc2", mlp_fc2);
  register_module("mlp_dropout", mlp_dropout);
}

torch::Tensor TransformerBlockImpl::forward(torch::Tensor x) {
  x = x + attn->forward(ln1->forward(x));
  auto y = mlp_fc1->forward(ln2->forward(x));
  y = mlp_act->forward(y);
  y = mlp_fc2->forward(y);
  y = mlp_dropout->forward(y);
  x = x + y;
  return x;
}

StockTransformerImpl::StockTransformerImpl(int64_t n_features, int64_t lookback,
                                           int64_t patch_size,
                                           int64_t embedding_dim,
                                           int64_t n_heads, int64_t n_layers,
                                           double dropout_rate)
    : lookback_(lookback), patch_size_(patch_size),
      patch_embed(PatchEmbedding(n_features, patch_size, embedding_dim)),
      dropout(torch::nn::Dropout(dropout_rate)),
      blocks(torch::nn::ModuleList()),
      ln_f(torch::nn::LayerNorm(torch::nn::LayerNormOptions({embedding_dim}))),
      head(torch::nn::Linear(embedding_dim, 1)) {

  int64_t num_patches = std::ceil((double)lookback / patch_size);
  // Positional embeddings are a fixed architectural constant here, not a
  // learned weight, so keep them out of the autograd graph and ONNX export
  // parameter set.
  pos_embed = torch::zeros({1, num_patches, embedding_dim});
  register_buffer("pos_embed", pos_embed);

  for (int64_t i = 0; i < n_layers; ++i) {
    blocks->push_back(TransformerBlock(embedding_dim, n_heads, dropout_rate));
  }

  register_module("patch_embed", patch_embed);
  register_module("dropout", dropout);
  register_module("blocks", blocks);
  register_module("ln_f", ln_f);
  register_module("head", head);
}

torch::Tensor StockTransformerImpl::forward(torch::Tensor x) {
  // x shape: (B, T, F)
  x = patch_embed->forward(x);
  x = x + pos_embed;
  x = dropout->forward(x);

  for (auto &block : *blocks) {
    x = block->as<TransformerBlock>()->forward(x);
  }

  x = ln_f->forward(x);
  x = x.select(1, -1); // Take the last token: (B, D)
  return head->forward(x);
}

} // namespace ml
} // namespace trade
