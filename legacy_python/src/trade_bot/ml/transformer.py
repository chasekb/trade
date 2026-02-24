
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class PatchEmbedding(nn.Module):
    """
    Groups temporal features into patches and projects them to embedding dimension.
    Input: (Batch, SeqLen, Features)
    Output: (Batch, NumPatches, EmbeddingDim)
    """
    def __init__(self, n_features, patch_size, embedding_dim):
        super().__init__()
        self.patch_size = patch_size
        self.projection = nn.Linear(n_features * patch_size, embedding_dim)

    def forward(self, x):
        B, T, F = x.shape
        # Ensure T is divisible by patch_size
        if T % self.patch_size != 0:
            padding = self.patch_size - (T % self.patch_size)
            x = F.pad(x, (0, 0, padding, 0)) # Pad temporal dimension at the beginning
            T = x.shape[1]

        # Reshape to patches: (B, T/P, P*F)
        x = x.reshape(B, T // self.patch_size, self.patch_size * F)
        x = self.projection(x)
        return x

class CausalSelfAttention(nn.Module):
    """
    Multi-head causal self-attention.
    """
    def __init__(self, embedding_dim, n_heads, dropout=0.1):
        super().__init__()
        assert embedding_dim % n_heads == 0
        self.n_heads = n_heads
        self.embedding_dim = embedding_dim
        
        self.qkv = nn.Linear(embedding_dim, embedding_dim * 3)
        self.proj = nn.Linear(embedding_dim, embedding_dim)
        self.attn_dropout = nn.Dropout(dropout)
        self.res_dropout = nn.Dropout(dropout)

    def forward(self, x):
        B, N, D = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        
        # Split heads
        q = q.view(B, N, self.n_heads, D // self.n_heads).transpose(1, 2)
        k = k.view(B, N, self.n_heads, D // self.n_heads).transpose(1, 2)
        v = v.view(B, N, self.n_heads, D // self.n_heads).transpose(1, 2)

        # Causal mask
        mask = torch.tril(torch.ones(N, N, device=x.device)).view(1, 1, N, N)
        
        # Attention
        attn = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(k.size(-1)))
        attn = attn.masked_fill(mask == 0, float('-inf'))
        attn = F.softmax(attn, dim=-1)
        attn = self.attn_dropout(attn)
        
        y = attn @ v # (B, H, N, D/H)
        y = y.transpose(1, 2).contiguous().view(B, N, D)
        
        return self.res_dropout(self.proj(y))

class TransformerBlock(nn.Module):
    """
    Standard Transformer Block (Pre-Norm).
    """
    def __init__(self, embedding_dim, n_heads, dropout=0.1):
        super().__init__()
        self.ln1 = nn.LayerNorm(embedding_dim)
        self.attn = CausalSelfAttention(embedding_dim, n_heads, dropout)
        self.ln2 = nn.LayerNorm(embedding_dim)
        self.mlp = nn.Sequential(
            nn.Linear(embedding_dim, 4 * embedding_dim),
            nn.GELU(),
            nn.Linear(4 * embedding_dim, embedding_dim),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x

class StockTransformer(nn.Module):
    """
    The full Patch-based Temporal Transformer model.
    """
    def __init__(self, n_features, lookback, patch_size, embedding_dim, n_heads, n_layers, dropout=0.1):
        super().__init__()
        self.lookback = lookback
        self.patch_size = patch_size
        
        self.patch_embed = PatchEmbedding(n_features, patch_size, embedding_dim)
        
        num_patches = math.ceil(lookback / patch_size)
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embedding_dim))
        self.dropout = nn.Dropout(dropout)
        
        self.blocks = nn.ModuleList([
            TransformerBlock(embedding_dim, n_heads, dropout) for _ in range(n_layers)
        ])
        
        self.ln_f = nn.LayerNorm(embedding_dim)
        self.head = nn.Linear(embedding_dim, 1) # Predicting next log return (PnL)

    def forward(self, x):
        # x shape: (Batch, SeqLen, Features)
        x = self.patch_embed(x)
        x = x + self.pos_embed
        x = self.dropout(x)
        
        for block in self.blocks:
            x = block(x)
            
        x = self.ln_f(x)
        # We take the last token's representation for prediction
        x = x[:, -1, :]
        return self.head(x)
