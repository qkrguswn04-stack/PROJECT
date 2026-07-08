"""
╔══════════════════════════════════════════════════════════════════════════╗
║  Advanced Clinical Drug Recommendation System  (2026 Edition)           ║
║                                                                          ║
║  Architecture Stack:                                                     ║
║    ① NumericalEmbedding   — per-feature token projection                ║
║    ② TabTransformer       — MHSA captures vital-sign correlations       ║
║    ③ DeepFM Interaction   — explicit 2nd-order feature crosses          ║
║    ④ GCN Label Correlator — graph propagation across drug nodes         ║
║    ⑤ 50 Independent Heads — sigmoid per drug (Multi-Label BCE)          ║
║                                                                          ║
║  Loss: Focal Loss  (handles severe label imbalance)                     ║
║  Eval: ROC-AUC · F1 · Precision · Recall (all macro, multi-label)      ║
╚══════════════════════════════════════════════════════════════════════════╝

pip install torch scikit-learn matplotlib seaborn
python clinical_advanced.py
"""

import math
import warnings
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import (f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_META: Dict[str, Tuple[float, float, str]] = {
    # name        : (low,   high,  unit)
    "HR"          : (40,    180,   "bpm"),
    "SBP"         : (70,    220,   "mmHg"),
    "DBP"         : (40,    130,   "mmHg"),
    "RR"          : (8,     40,    "br/min"),
    "Temp"        : (35.0,  41.0,  "°C"),
    "SpO2"        : (70,    100,   "%"),
    "WBC"         : (1.0,   30.0,  "K/µL"),
    "Hb"          : (5.0,   18.0,  "g/dL"),
    "Platelets"   : (20,    600,   "K/µL"),
    "Creatinine"  : (0.4,   15.0,  "mg/dL"),
    "Na"          : (120,   160,   "mEq/L"),
    "K"           : (2.5,   7.0,   "mEq/L"),
    "Glucose"     : (50,    500,   "mg/dL"),
    "Lactate"     : (0.5,   15.0,  "mmol/L"),
    "CRP"         : (0.0,   300.0, "mg/L"),
}
FEATURE_NAMES = list(FEATURE_META.keys())   # 15 features
DRUG_NAMES    = [f"Drug_{i:02d}" for i in range(50)]


# ─────────────────────────────────────────────────────────────────────────────
#  1.  DATASET
# ─────────────────────────────────────────────────────────────────────────────

def generate_clinical_data(
    n_samples : int = 4000,
    n_features: int = 15,
    n_labels  : int = 50,
    seed      : int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Synthetic clinical tabular data.
    Labels have realistic co-prescription correlations and class imbalance
    (positive rate ≈ 10–25 % per drug, mimicking real ICU data).
    """
    rng = np.random.default_rng(seed)
    feat_names = FEATURE_NAMES[:n_features]

    # ── Features ────────────────────────────────────────────────────────────
    X = np.zeros((n_samples, n_features), dtype=np.float32)
    for i, name in enumerate(feat_names):
        lo, hi = FEATURE_META[name][:2]
        X[:, i] = rng.uniform(lo, hi, n_samples).astype(np.float32)

    # Normalize to roughly [0, 1] for stable embedding
    lo_arr = np.array([FEATURE_META[n][0] for n in feat_names], dtype=np.float32)
    hi_arr = np.array([FEATURE_META[n][1] for n in feat_names], dtype=np.float32)
    X_norm = (X - lo_arr) / (hi_arr - lo_arr + 1e-8)

    # ── Labels (correlated multi-label) ─────────────────────────────────────
    base_p = rng.uniform(0.07, 0.28, n_labels)   # imbalanced base probabilities
    Y = np.zeros((n_samples, n_labels), dtype=np.float32)

    for i in range(n_samples):
        hr_dev   = (X_norm[i, 0] - 0.5) * 2       # [-1, 1]
        spo2_dev = (0.5 - X_norm[i, 5]) * 2        # low SpO2 → high
        temp_dev = (X_norm[i, 4] - 0.5) * 2

        for j in range(n_labels):
            p  = base_p[j]
            p += 0.06 * hr_dev   * math.sin(j * 0.4)
            p += 0.04 * spo2_dev * math.cos(j * 0.3)
            p += 0.03 * temp_dev * (1 if j % 3 == 0 else -0.5)
            p  = float(np.clip(p, 0.03, 0.50))
            Y[i, j] = rng.binomial(1, p)

        # Co-prescription groups (simulate clinical drug families)
        groups = [(0, 4), (5, 10), (11, 16), (17, 22), (23, 28),
                  (29, 33), (34, 38), (39, 43), (44, 47), (48, 50)]
        for lo_g, hi_g in groups:
            anchor = min(lo_g, n_labels - 1)
            if Y[i, anchor] == 1:
                for k in range(lo_g + 1, min(hi_g, n_labels)):
                    Y[i, k] = rng.binomial(1, 0.65)

    return X_norm, Y


class ClinicalDataset(Dataset):
    def __init__(self, X: np.ndarray, Y: np.ndarray):
        self.X = torch.from_numpy(X).float()
        self.Y = torch.from_numpy(Y).float()

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx]


# ─────────────────────────────────────────────────────────────────────────────
#  2.  MODEL COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

# ── 2-A  Numerical Embedding ─────────────────────────────────────────────────

class NumericalEmbedding(nn.Module):
    """
    Lifts each scalar feature x_i into a d-dimensional token:
        e_i = W_i · x_i + b_i + pos_i       ∈ R^d

    This gives the Transformer a separate "word" for each vital sign.
    """
    def __init__(self, n_features: int, d_model: int, dropout: float = 0.1):
        super().__init__()
        self.W   = nn.Parameter(torch.randn(n_features, d_model) * 0.02)
        self.b   = nn.Parameter(torch.zeros(n_features, d_model))
        self.pos = nn.Parameter(torch.randn(1, n_features, d_model) * 0.01)
        self.norm    = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, F)  →  (B, F, d)"""
        e = x.unsqueeze(-1) * self.W + self.b   # (B, F, d)
        e = e + self.pos
        return self.dropout(self.norm(e))


# ── 2-B  Multi-Head Self-Attention (with attention capture) ──────────────────

class MHSA(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % n_heads == 0
        self.h  = n_heads
        self.dh = d_model // n_heads
        self.Wq = nn.Linear(d_model, d_model, bias=False)
        self.Wk = nn.Linear(d_model, d_model, bias=False)
        self.Wv = nn.Linear(d_model, d_model, bias=False)
        self.Wo = nn.Linear(d_model, d_model)
        self.drop = nn.Dropout(dropout)
        self._attn: Optional[torch.Tensor] = None   # stored for explainability

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, L, D = x.shape
        split = lambda t: t.view(B, L, self.h, self.dh).transpose(1, 2)
        Q, K, V = split(self.Wq(x)), split(self.Wk(x)), split(self.Wv(x))
        sc  = (Q @ K.transpose(-2, -1)) / math.sqrt(self.dh)
        w   = self.drop(F.softmax(sc, dim=-1))
        self._attn = w.detach()
        o   = (w @ V).transpose(1, 2).reshape(B, L, D)
        return self.Wo(o)

    @property
    def attn_weights(self): return self._attn


class TransformerBlock(nn.Module):
    """Pre-LayerNorm Transformer block."""
    def __init__(self, d_model: int, n_heads: int, ffn_dim: int, dropout: float):
        super().__init__()
        self.attn = MHSA(d_model, n_heads, dropout)
        self.ffn  = nn.Sequential(
            nn.Linear(d_model, ffn_dim), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_dim, d_model),
        )
        self.n1   = nn.LayerNorm(d_model)
        self.n2   = nn.LayerNorm(d_model)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        x = x + self.drop(self.attn(self.n1(x)))
        x = x + self.drop(self.ffn(self.n2(x)))
        return x


# ── 2-C  DeepFM Feature Interaction ──────────────────────────────────────────

class DeepFMInteraction(nn.Module):
    """
    Factorization-Machine style 2nd-order feature interactions.

    For every pair (i, j), computes <v_i, v_j> via:
        FM output = 0.5 * ( ||Σ e_i||² − Σ||e_i||² )
    This is O(F·d) instead of O(F²·d) — efficient and expressive.

    Additionally passes the raw embeddings through a DNN for higher-order
    interactions (the "Deep" part of DeepFM).
    """
    def __init__(self, n_features: int, d_model: int, deep_hidden: int, dropout: float):
        super().__init__()
        self.n_features = n_features

        # FM second-order interaction → scalar per sample
        # (we project to d_model to concatenate with backbone later)
        self.fm_proj = nn.Linear(d_model, d_model)

        # DNN for higher-order interactions
        flat_dim = n_features * d_model
        self.deep = nn.Sequential(
            nn.Linear(flat_dim, deep_hidden), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(deep_hidden, deep_hidden), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(deep_hidden, d_model),
        )
        self.norm = nn.LayerNorm(d_model)

    def forward(self, emb: torch.Tensor) -> torch.Tensor:
        """
        emb : (B, F, d)  — feature embeddings from NumericalEmbedding
        returns : (B, d)  — interaction representation
        """
        # ── FM second-order ──────────────────────────────────────────────────
        #   sum_sq = (Σ_i e_i)²   element-wise
        #   sq_sum =  Σ_i (e_i²)
        sum_sq = emb.sum(dim=1) ** 2            # (B, d)
        sq_sum = (emb ** 2).sum(dim=1)          # (B, d)
        fm_out = 0.5 * (sum_sq - sq_sum)        # (B, d)  ← 2nd-order interactions
        fm_out = self.fm_proj(fm_out)

        # ── Deep (DNN) higher-order ──────────────────────────────────────────
        deep_out = self.deep(emb.flatten(start_dim=1))   # (B, d)

        # ── Combine ──────────────────────────────────────────────────────────
        interaction = self.norm(fm_out + deep_out)       # (B, d)
        return interaction


# ── 2-D  GCN Label Correlator ─────────────────────────────────────────────────

class GraphConvLayer(nn.Module):
    """
    One layer of Graph Convolution:
        H' = σ( A_hat · H · W )
    where A_hat = D^{-1/2} (A + I) D^{-1/2}  (symmetric normalisation)
    """
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.W    = nn.Linear(in_dim, out_dim, bias=False)
        self.bias = nn.Parameter(torch.zeros(out_dim))

    def forward(self, H: torch.Tensor, A_hat: torch.Tensor) -> torch.Tensor:
        """
        H     : (n_labels, in_dim)
        A_hat : (n_labels, n_labels)  normalised adjacency
        """
        return F.gelu(A_hat @ self.W(H) + self.bias)


class GCNLabelCorrelator(nn.Module):
    """
    2-layer GCN on the label graph (adjacency = co-occurrence matrix).

    Each drug node starts with a learnable embedding, then aggregates
    information from co-prescribed neighbours.  The resulting node
    representations condition the final per-drug classifier heads,
    making predictions label-correlation-aware.
    """
    def __init__(
        self,
        n_labels           : int,
        d_model            : int,
        cooccurrence_matrix: Optional[torch.Tensor],
        dropout            : float = 0.1,
    ):
        super().__init__()
        self.n_labels = n_labels

        # Node features: learnable drug embeddings
        self.node_emb = nn.Embedding(n_labels, d_model)

        # Build symmetric normalised adjacency A_hat from co-occurrence
        if cooccurrence_matrix is not None:
            A = cooccurrence_matrix.float().clone()
        else:
            A = torch.eye(n_labels)
        A = (A + A.T) / 2                     # symmetrise
        A = A + torch.eye(n_labels)           # add self-loop
        D_inv_sqrt = A.sum(dim=1).clamp(min=1e-8) ** -0.5
        A_hat = D_inv_sqrt.unsqueeze(1) * A * D_inv_sqrt.unsqueeze(0)
        self.register_buffer("A_hat", A_hat)

        # GCN layers
        self.gc1  = GraphConvLayer(d_model, d_model)
        self.gc2  = GraphConvLayer(d_model, d_model)
        self.norm = nn.LayerNorm(d_model)
        self.drop = nn.Dropout(dropout)

        # Fusion: backbone (B,d) ⊕ label_node (L,d)  →  (B,L,d)
        self.fuse = nn.Linear(d_model * 2, d_model)

    def forward(self, backbone: torch.Tensor) -> torch.Tensor:
        """
        backbone : (B, d)
        returns  : (B, n_labels, d)   per-label contextualised representations
        """
        B = backbone.shape[0]
        idx   = torch.arange(self.n_labels, device=backbone.device)
        H     = self.node_emb(idx)                      # (L, d)

        # 2-layer GCN
        H1 = self.drop(self.gc1(H,  self.A_hat))        # (L, d)
        H2 = self.norm(self.gc2(H1, self.A_hat) + H)    # (L, d) + residual

        # Fuse with backbone
        bb = backbone.unsqueeze(1).expand(B, self.n_labels, -1)    # (B, L, d)
        hh = H2.unsqueeze(0).expand(B, self.n_labels, -1)         # (B, L, d)
        out = F.gelu(self.fuse(torch.cat([bb, hh], dim=-1)))       # (B, L, d)
        return out


# ── 2-E  Full Model ───────────────────────────────────────────────────────────

class AdvancedCDS(nn.Module):
    """
    Advanced Clinical Decision Support Model

    Full forward pass:
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Input  (B, F)                                                       │
    │   ↓  NumericalEmbedding                                             │
    │ (B, F, d)  ← one token per vital sign                              │
    │   ├──→  TabTransformer × N_layers     attention over features       │
    │   │     (B, F, d)                                                   │
    │   └──→  DeepFM Interaction            2nd-order feature crosses     │
    │         (B, d)                                                      │
    │   ↓  Concat Transformer-pool + DeepFM  →  Shared Backbone (B, d)   │
    │   ↓  GCN Label Correlator             graph message passing         │
    │ (B, 50, d)  ← per-drug node representations                        │
    │   ↓  50 Independent Linear Heads                                    │
    │ (B, 50)  ← logits  (BCEWithLogitsLoss / Focal)                     │
    └─────────────────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        n_features          : int   = 15,
        n_labels            : int   = 50,
        d_model             : int   = 64,
        n_heads             : int   = 4,
        n_transformer_layers: int   = 3,
        ffn_dim             : int   = 256,
        deep_hidden         : int   = 128,
        backbone_dim        : int   = 64,
        dropout             : float = 0.15,
        cooccurrence_matrix : Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.n_labels = n_labels

        # ① Feature Embedding
        self.embedding = NumericalEmbedding(n_features, d_model, dropout)

        # ② TabTransformer
        self.transformer = nn.ModuleList([
            TransformerBlock(d_model, n_heads, ffn_dim, dropout)
            for _ in range(n_transformer_layers)
        ])
        self.transformer_pool_norm = nn.LayerNorm(d_model)

        # ③ DeepFM Interaction
        self.deepfm = DeepFMInteraction(n_features, d_model, deep_hidden, dropout)

        # Shared backbone: fuse Transformer + DeepFM outputs
        # Transformer gives (B, F, d) → mean-pool → (B, d)
        # DeepFM gives (B, d)
        # Concat: (B, 2d) → Linear → (B, backbone_dim)
        self.backbone = nn.Sequential(
            nn.Linear(d_model * 2, backbone_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.LayerNorm(backbone_dim),
        )

        # ④ GCN Label Correlator
        self.gcn = GCNLabelCorrelator(n_labels, backbone_dim, cooccurrence_matrix, dropout)

        # ⑤ 50 Independent Heads (one Linear per drug)
        #    We implement as a single Linear(d, 1) applied over the L-dim
        #    (equivalent to 50 independent heads with shared weight init,
        #     but label-specific because each node embedding is different)
        self.head = nn.Linear(backbone_dim, 1)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None: nn.init.zeros_(m.bias)
            elif isinstance(m, nn.LayerNorm):
                nn.init.ones_(m.weight); nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, 0, 0.02)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict]:
        # ① Embed
        emb = self.embedding(x)               # (B, F, d)

        # ② Transformer
        h = emb
        attn_maps = []
        for block in self.transformer:
            h = block(h)
            attn_maps.append(block.attn.attn_weights)   # (B, H, F, F)
        h_pool = self.transformer_pool_norm(h).mean(dim=1)   # (B, d)  mean-pool

        # ③ DeepFM on original embeddings (not transformer-modified)
        fm_out = self.deepfm(emb)             # (B, d)

        # Shared backbone
        bb = self.backbone(torch.cat([h_pool, fm_out], dim=-1))   # (B, backbone_dim)

        # ④ GCN label correlation
        label_repr = self.gcn(bb)             # (B, 50, backbone_dim)

        # ⑤ Per-drug logits
        logits = self.head(label_repr).squeeze(-1)   # (B, 50)

        aux = {
            "attn_maps"  : attn_maps,
            "backbone"   : bb,
            "label_repr" : label_repr,
            "fm_out"     : fm_out,
        }
        return logits, aux


# ─────────────────────────────────────────────────────────────────────────────
#  3.  LOSS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

class FocalLoss(nn.Module):
    """
    Multi-label Focal Loss.
    FL(p_t) = −α_t · (1−p_t)^γ · log(p_t)

    Forces the model to focus on hard, rare positive examples.
    Critical for clinical data where most drugs are NOT needed.
    """
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce  = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        prob = torch.sigmoid(logits)
        p_t  = prob * targets + (1 - prob) * (1 - targets)
        a_t  = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        loss = a_t * (1 - p_t) ** self.gamma * bce
        return loss.mean()


class AsymmetricFocalLoss(nn.Module):
    """
    Asymmetric Focal Loss (ASL) — 2021 SOTA for multi-label imbalance.
    Uses different γ for positives and negatives, + probability shift.
    """
    def __init__(self, gamma_pos: float = 0.0, gamma_neg: float = 4.0, clip: float = 0.05):
        super().__init__()
        self.gp   = gamma_pos
        self.gn   = gamma_neg
        self.clip = clip

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        prob = torch.sigmoid(logits)
        prob_m = (prob - self.clip).clamp(min=0) if self.clip else prob

        log_p  = torch.log(prob.clamp(min=1e-8))
        log_1p = torch.log((1 - prob_m).clamp(min=1e-8))

        loss_p = (1 - prob) ** self.gp * log_p
        loss_n = prob_m ** self.gn * log_1p

        loss = -targets * loss_p - (1 - targets) * loss_n
        return loss.mean()


def compute_pos_weights(Y: np.ndarray, clip_max: float = 20.0) -> torch.Tensor:
    n_pos = Y.sum(axis=0).clip(min=1)
    n_neg = (1 - Y).sum(axis=0).clip(min=1)
    return torch.tensor(np.clip(n_neg / n_pos, 1.0, clip_max), dtype=torch.float32)


def compute_cooccurrence(Y: np.ndarray) -> torch.Tensor:
    """C[i,j] = P(label_j = 1 | label_i = 1)"""
    n = Y.shape[1]
    C = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        mask = Y[:, i] == 1
        C[i] = Y[mask].mean(axis=0) if mask.sum() > 0 else 0.0
        C[i, i] = 1.0
    return torch.tensor(C)


# ─────────────────────────────────────────────────────────────────────────────
#  4.  TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def train_epoch(
    model    : nn.Module,
    loader   : DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device   : torch.device,
    clip_grad: float = 1.0,
) -> float:
    model.train()
    total = 0.0
    for Xb, Yb in loader:
        Xb, Yb = Xb.to(device), Yb.to(device)
        optimizer.zero_grad()
        logits, _ = model(Xb)
        loss = criterion(logits, Yb)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), clip_grad)
        optimizer.step()
        total += loss.item()
    return total / len(loader)


# ─────────────────────────────────────────────────────────────────────────────
#  5.  EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def evaluate(
    model    : nn.Module,
    loader   : DataLoader,
    device   : torch.device,
    threshold: float = 0.5,
) -> Dict:
    model.eval()
    logit_list, target_list = [], []
    for Xb, Yb in loader:
        lg, _ = model(Xb.to(device))
        logit_list.append(lg.cpu())
        target_list.append(Yb)
    logits  = torch.cat(logit_list,  dim=0)
    targets = torch.cat(target_list, dim=0)
    probs   = torch.sigmoid(logits).numpy()
    preds   = (probs >= threshold).astype(int)
    tnp     = targets.numpy()

    valid = tnp.sum(axis=0) > 0
    try:
        auc = roc_auc_score(tnp[:, valid], probs[:, valid], average="macro")
    except ValueError:
        auc = float("nan")

    return {
        "roc_auc"   : auc,
        "f1_macro"  : f1_score(tnp, preds, average="macro",    zero_division=0),
        "precision" : precision_score(tnp, preds, average="macro", zero_division=0),
        "recall"    : recall_score(tnp, preds, average="macro",    zero_division=0),
        "_probs"    : probs,
        "_targets"  : tnp,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  6.  EXPLAINABILITY
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def get_attention_map(model, X, layer=-1, device=torch.device("cpu")):
    model.eval()
    x = torch.tensor(X[:64], dtype=torch.float32).to(device)
    _, aux = model(x)
    w = aux["attn_maps"][layer]              # (B, H, F, F)
    return w.mean(dim=(0, 1)).cpu().numpy()  # (F, F)


def gradient_importance(model, X, device, n=200):
    model.eval()
    Xt = torch.tensor(X[:n], dtype=torch.float32, device=device, requires_grad=True)
    logits, _ = model(Xt)
    logits.sum().backward()
    imp = Xt.grad.abs().mean(dim=0).cpu().numpy()
    return imp / (imp.sum() + 1e-9)


# ─────────────────────────────────────────────────────────────────────────────
#  7.  VISUALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def plot_all(history, attn_map, importance, probs, feature_names, save=True):
    """4-panel dashboard."""
    fig = plt.figure(figsize=(20, 16))
    fig.patch.set_facecolor("#0f1117")
    gs  = fig.add_gridspec(2, 2, hspace=0.38, wspace=0.32)
    color_bg = "#0f1117"

    def styled_ax(ax, title):
        ax.set_facecolor("#1a1d27")
        ax.set_title(title, color="#e8e8f0", fontsize=12, fontweight="bold", pad=10)
        ax.tick_params(colors="#8888aa")
        for sp in ax.spines.values(): sp.set_color("#2a2d3e")
        return ax

    # ── Panel 1: Training curves ───────────────────────────────────────────
    ax1 = styled_ax(fig.add_subplot(gs[0, 0]), "Training Curves")
    epochs = range(1, len(history["loss"]) + 1)
    ax1.plot(epochs, history["loss"],    color="#e74c3c", lw=2, label="Train Loss", marker="o", ms=4)
    ax1_r = ax1.twinx()
    ax1_r.plot(epochs, history["auc"],   color="#3498db", lw=2, label="ROC-AUC",   marker="s", ms=4)
    ax1_r.plot(epochs, history["f1"],    color="#2ecc71", lw=2, label="F1 Macro",  marker="^", ms=4)
    ax1_r.tick_params(colors="#8888aa")
    ax1.set_xlabel("Epoch", color="#8888aa")
    ax1.set_ylabel("Loss",    color="#e74c3c")
    ax1_r.set_ylabel("Score", color="#3498db")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, facecolor="#1a1d27", labelcolor="#ccccdd", fontsize=9)

    # ── Panel 2: Attention heatmap ─────────────────────────────────────────
    ax2 = styled_ax(fig.add_subplot(gs[0, 1]), "Feature Self-Attention (Last Transformer Layer)")
    fn_short = [f[:4] for f in feature_names]
    im = ax2.imshow(attn_map, cmap="YlOrRd", aspect="auto")
    ax2.set_xticks(range(len(fn_short))); ax2.set_xticklabels(fn_short, rotation=45, ha="right", fontsize=8, color="#aaaacc")
    ax2.set_yticks(range(len(fn_short))); ax2.set_yticklabels(fn_short, fontsize=8, color="#aaaacc")
    for i in range(attn_map.shape[0]):
        for j in range(attn_map.shape[1]):
            ax2.text(j, i, f"{attn_map[i,j]:.2f}", ha="center", va="center",
                     fontsize=5.5, color="black" if attn_map[i,j] > 0.5 else "white")
    plt.colorbar(im, ax=ax2, fraction=0.046, pad=0.04).ax.tick_params(colors="#8888aa")

    # ── Panel 3: Feature importance ────────────────────────────────────────
    ax3 = styled_ax(fig.add_subplot(gs[1, 0]), "Global Feature Importance  |∂logit/∂x|")
    idx = np.argsort(importance)
    cmap = plt.cm.RdYlGn
    colors = [cmap(v) for v in importance[idx] / importance.max()]
    bars = ax3.barh([feature_names[i] for i in idx], importance[idx],
                    color=colors, edgecolor="#0f1117", linewidth=0.5)
    ax3.axvline(1/len(feature_names), color="#888", ls="--", lw=1, alpha=0.5)
    for bar, v in zip(bars, importance[idx]):
        ax3.text(v + 0.001, bar.get_y() + bar.get_height()/2,
                 f"{v:.3f}", va="center", color="#ccccdd", fontsize=8)
    ax3.set_xlabel("Normalized Importance", color="#8888aa")
    ax3.tick_params(axis="y", labelsize=9, colors="#ccccdd")

    # ── Panel 4: Drug probability heatmap ──────────────────────────────────
    ax4 = styled_ax(fig.add_subplot(gs[1, 1]), "Predicted Drug Probabilities (30 patients × 50 drugs)")
    data = probs[:30]
    im2  = ax4.imshow(data, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax4.set_xlabel("Drug Index", color="#8888aa")
    ax4.set_ylabel("Patient",    color="#8888aa")
    ax4.set_xticks(range(0, 50, 5))
    ax4.set_xticklabels(range(0, 50, 5), fontsize=8, color="#aaaacc")
    plt.colorbar(im2, ax=ax4, fraction=0.046, pad=0.04, label="P(prescribe)").ax.tick_params(colors="#8888aa")

    fig.suptitle(
        "Advanced CDS · TabTransformer + DeepFM + GCN  —  Drug Recommendation Dashboard",
        color="#e8e8f0", fontsize=14, fontweight="bold", y=0.98
    )
    if save:
        plt.savefig("cds_dashboard.png", dpi=150, bbox_inches="tight", facecolor=color_bg)
    plt.show()
    if save: print("  ✓ Saved → cds_dashboard.png")


# ─────────────────────────────────────────────────────────────────────────────
#  8.  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    CFG = dict(
        n_samples            = 4000,
        n_features           = 15,
        n_labels             = 50,
        # Model
        d_model              = 64,
        n_heads              = 4,
        n_transformer_layers = 3,
        ffn_dim              = 256,
        deep_hidden          = 256,
        backbone_dim         = 64,
        dropout              = 0.15,
        # Training
        batch_size           = 64,
        n_epochs             = 50,
        lr                   = 3e-4,
        weight_decay         = 1e-4,
        clip_grad            = 1.0,
        warmup_epochs        = 5,
        # Loss:  "focal" | "asl" | "bce"
        loss_type            = "asl",
        threshold            = 0.40,   # lower threshold for high recall in clinical setting
        seed                 = 42,
    )

    torch.manual_seed(CFG["seed"])
    np.random.seed(CFG["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    banner = "=" * 68
    print(banner)
    print("  Advanced CDS  ·  TabTransformer + DeepFM + GCN")
    print(f"  Device  : {device}  |  Loss : {CFG['loss_type'].upper()}")
    print(banner)

    # ── Data ─────────────────────────────────────────────────────────────────
    print("\n[1/5] Generating synthetic clinical data …")
    X, Y = generate_clinical_data(CFG["n_samples"], CFG["n_features"], CFG["n_labels"], CFG["seed"])
    X_tr, X_te, Y_tr, Y_te = train_test_split(X, Y, test_size=0.2, random_state=CFG["seed"])
    print(f"      Train {X_tr.shape}  |  Test {X_te.shape}")
    print(f"      Mean label positive rate : {Y_tr.mean():.3f}")

    cooc = compute_cooccurrence(Y_tr)

    train_dl = DataLoader(ClinicalDataset(X_tr, Y_tr), CFG["batch_size"], shuffle=True,  num_workers=0)
    test_dl  = DataLoader(ClinicalDataset(X_te, Y_te), CFG["batch_size"], shuffle=False, num_workers=0)

    # ── Model ─────────────────────────────────────────────────────────────────
    print("\n[2/5] Building model …")
    model = AdvancedCDS(
        n_features           = CFG["n_features"],
        n_labels             = CFG["n_labels"],
        d_model              = CFG["d_model"],
        n_heads              = CFG["n_heads"],
        n_transformer_layers = CFG["n_transformer_layers"],
        ffn_dim              = CFG["ffn_dim"],
        deep_hidden          = CFG["deep_hidden"],
        backbone_dim         = CFG["backbone_dim"],
        dropout              = CFG["dropout"],
        cooccurrence_matrix  = cooc,
    ).to(device)
    print(f"      Parameters : {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    # ── Loss ──────────────────────────────────────────────────────────────────
    if CFG["loss_type"] == "focal":
        criterion = FocalLoss(alpha=0.25, gamma=2.0)
    elif CFG["loss_type"] == "asl":
        criterion = AsymmetricFocalLoss(gamma_pos=0.0, gamma_neg=4.0, clip=0.05)
    else:
        pw = compute_pos_weights(Y_tr).to(device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pw)

    # ── Optimizer + Scheduler ─────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(model.parameters(), lr=CFG["lr"], weight_decay=CFG["weight_decay"])
    # Warmup + cosine decay
    def lr_lambda(ep):
        if ep < CFG["warmup_epochs"]:
            return (ep + 1) / CFG["warmup_epochs"]
        progress = (ep - CFG["warmup_epochs"]) / max(CFG["n_epochs"] - CFG["warmup_epochs"], 1)
        return 0.5 * (1 + math.cos(math.pi * progress))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ── Training ──────────────────────────────────────────────────────────────
    print(f"\n[3/5] Training for {CFG['n_epochs']} epochs …")
    print("-" * 68)
    print(f"{'Ep':>4}  {'Loss':>8}  {'AUC':>8}  {'F1':>7}  {'Prec':>7}  {'Rec':>7}  {'LR':>9}")
    print("-" * 68)

    history   = {"loss": [], "auc": [], "f1": []}
    best_auc  = 0.0
    best_ckpt = None

    for ep in range(1, CFG["n_epochs"] + 1):
        loss = train_epoch(model, train_dl, optimizer, criterion, device, CFG["clip_grad"])
        scheduler.step()
        cur_lr = optimizer.param_groups[0]["lr"]

        if ep % 5 == 0 or ep == 1:
            m = evaluate(model, test_dl, device, CFG["threshold"])
            history["loss"].append(loss)
            history["auc"].append(m["roc_auc"])
            history["f1"].append(m["f1_macro"])
            print(f"{ep:4d}  {loss:8.4f}  {m['roc_auc']:8.4f}  "
                  f"{m['f1_macro']:7.4f}  {m['precision']:7.4f}  "
                  f"{m['recall']:7.4f}  {cur_lr:9.2e}")
            if m["roc_auc"] > best_auc:
                best_auc  = m["roc_auc"]
                best_ckpt = {k: v.clone() for k, v in model.state_dict().items()}

    print("-" * 68)
    print(f"  Best ROC-AUC : {best_auc:.4f}")

    # ── Final eval ────────────────────────────────────────────────────────────
    print("\n[4/5] Final evaluation (best checkpoint) …")
    if best_ckpt: model.load_state_dict(best_ckpt)
    final = evaluate(model, test_dl, device, CFG["threshold"])
    print(f"  ROC-AUC   : {final['roc_auc']:.4f}")
    print(f"  F1 (macro): {final['f1_macro']:.4f}")
    print(f"  Precision : {final['precision']:.4f}")
    print(f"  Recall    : {final['recall']:.4f}")

    # Per-drug AUC top/bottom 5
    valid  = final["_targets"].sum(axis=0) > 0
    aucs   = []
    for j in range(CFG["n_labels"]):
        if valid[j]:
            try:  aucs.append((DRUG_NAMES[j], roc_auc_score(final["_targets"][:, j], final["_probs"][:, j])))
            except: aucs.append((DRUG_NAMES[j], float("nan")))
    aucs.sort(key=lambda t: -t[1])
    print("\n  Top-5 Drug AUCs  :", [(n, f"{v:.3f}") for n, v in aucs[:5]])
    print("  Bot-5 Drug AUCs  :", [(n, f"{v:.3f}") for n, v in aucs[-5:]])

    # ── Explainability ────────────────────────────────────────────────────────
    print("\n[5/5] Explainability & visualization …")
    attn_map   = get_attention_map(model, X_te, layer=-1, device=device)
    importance = gradient_importance(model, X_te, device)

    print("\n  Feature Importance Ranking:")
    for rank, (name, score) in enumerate(
        sorted(zip(FEATURE_NAMES[:CFG["n_features"]], importance), key=lambda t: -t[1]), 1
    ):
        bar = "█" * int(score * 300)
        print(f"    {rank:2d}. {name:<15} {score:.4f}  {bar}")

    plot_all(history, attn_map, importance, final["_probs"],
             FEATURE_NAMES[:CFG["n_features"]])

    # ── Example inference ─────────────────────────────────────────────────────
    print("\n── Example Inference ─────────────────────────────────────────")
    sample = torch.tensor(X_te[:1], dtype=torch.float32).to(device)
    model.eval()
    with torch.no_grad():
        logits, _ = model(sample)
        probs_ex  = torch.sigmoid(logits).squeeze().cpu().numpy()

    top5_idx = np.argsort(probs_ex)[-5:][::-1]
    print("  Top-5 recommended drugs for this patient:")
    for rank, idx in enumerate(top5_idx, 1):
        print(f"    {rank}. {DRUG_NAMES[idx]:<12}  p = {probs_ex[idx]:.3f}")

    print(f"\n✓ Done.  Dashboard saved → cds_dashboard.png\n")
    return model, final, history


if __name__ == "__main__":
    model, metrics, history = main()
