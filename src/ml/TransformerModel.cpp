#include "ml/TransformerModel.hpp"
#include <cmath>

namespace trade {
namespace ml {

PatchEmbeddingImpl::PatchEmbeddingImpl(int64_t n_features, int64_t patch_size,
                                       int64_t embedding_dim)
    : patch_size_(patch_size),
      projection(torch::nn::Linear(n_features * patch_size, embedding_dim)) {
  register_module("projection", projection);
}

torch::Tensor PatchEmbeddingImpl::forward(torch::Tensor x) {
  // x shape: (B, T, F)
  int64_t B = x.size(0);
  int64_t T = x.size(1);
  int64_t F = x.size(2);

  if (T % patch_size_ != 0) {
    int64_t padding = patch_size_ - (T % patch_size_);
    x = torch::constant_pad_nd(x, {0, 0, padding, 0}); // Pad temporal dimension
    T = x.size(1);
  }

  // Reshape to patches: (B, T/P, P*F)
  x = x.reshape({B, T / patch_size_, patch_size_ * F});
  return projection->forward(x);
}

CausalSelfAttentionImpl::CausalSelfAttentionImpl(int64_t embedding_dim,
                                                 int64_t n_heads,
                                                 double dropout_rate)
    : n_heads_(n_heads), embedding_dim_(embedding_dim),
      qkv(torch::nn::Linear(embedding_dim, embedding_dim * 3)),
      proj(torch::nn::Linear(embedding_dim, embedding_dim)),
      attn_dropout(torch::nn::Dropout(dropout_rate)),
      res_dropout(torch::nn::Dropout(dropout_rate)) {
  register_module("qkv", qkv);
  register_module("proj", proj);
  register_module("attn_dropout", attn_dropout);
  register_module("res_dropout", res_dropout);
}

torch::Tensor CausalSelfAttentionImpl::forward(torch::Tensor x) {
  int64_t B = x.size(0);
  int64_t N = x.size(1);
  int64_t D = x.size(2);

  auto chunks = qkv->forward(x).chunk(3, -1);
  auto q = chunks[0].reshape({B, N, n_heads_, D / n_heads_}).transpose(1, 2);
  auto k = chunks[1].reshape({B, N, n_heads_, D / n_heads_}).transpose(1, 2);
  auto v = chunks[2].reshape({B, N, n_heads_, D / n_heads_}).transpose(1, 2);

  auto mask = torch::tril(torch::ones({N, N}, x.options())).reshape({1, 1, N, N});

  auto attn = (q.matmul(k.transpose(-2, -1))) * (1.0 / std::sqrt(k.size(-1)));
  attn = attn.masked_fill(mask == 0, -1e9);
  attn = torch::softmax(attn, -1);
  attn = attn_dropout->forward(attn);

  auto y = attn.matmul(v); // (B, H, N, D/H)
  y = y.transpose(1, 2).contiguous().reshape({B, N, D});

  return res_dropout->forward(proj->forward(y));
}

TransformerBlockImpl::TransformerBlockImpl(int64_t embedding_dim,
                                           int64_t n_heads,
                                           double dropout_rate)
    : ln1(torch::nn::LayerNorm(torch::nn::LayerNormOptions({embedding_dim}))),
      ln2(torch::nn::LayerNorm(torch::nn::LayerNormOptions({embedding_dim}))),
      attn(CausalSelfAttention(embedding_dim, n_heads, dropout_rate)),
      mlp(torch::nn::Sequential(
          torch::nn::Linear(embedding_dim, 4 * embedding_dim),
          torch::nn::GELU(),
          torch::nn::Linear(4 * embedding_dim, embedding_dim),
          torch::nn::Dropout(dropout_rate))) {
  register_module("ln1", ln1);
  register_module("ln2", ln2);
  register_module("attn", attn);
  register_module("mlp", mlp);
}

torch::Tensor TransformerBlockImpl::forward(torch::Tensor x) {
  x = x + attn->forward(ln1->forward(x));
  x = x + mlp->forward(ln2->forward(x));
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
