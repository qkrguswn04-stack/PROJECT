"""
============================================================
MLP (sklearn MLPClassifier) — Optuna Hyperparameter Tuning
Owner: <팀원 이름 적기>
============================================================

Task   : Binary classification — has_chemo (chemo start at RMI timepoint)
Input  : chemo_training_dataset.csv  (same directory)
Output : mlp_best.json                (best params + CV score + history)

Usage  : python tune_mlp.py

Requirements:
  pip install pandas numpy scikit-learn optuna joblib

What you can tune (CONFIG section below):
  - N_TRIALS         : number of Optuna trials (default 50)
  - N_SPLITS         : K for cross-validation (default 3)
  - SEARCH_SPACE     : hyperparameter ranges for each parameter
  - SEED             : random seed for reproducibility

NOTE: sklearn's MLPClassifier does NOT support dropout. Regularization is via
      L2 weight decay (alpha). If you need real dropout, switch to PyTorch/Keras.
============================================================
"""
from __future__ import annotations
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import optuna
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.INFO)

# =============================================================================
# CONFIG  (edit freely)
# =============================================================================
DATA_FILE = Path("chemo_training_dataset.csv")
OUT_FILE  = Path("mlp_best.json")

SEED      = 42
N_TRIALS  = 50
N_SPLITS  = 3

# Hyperparameter search space — edit ranges as you like
def define_search_space(trial: optuna.Trial) -> dict:
    n_layers = trial.suggest_int("n_layers", 1, 3)
    hidden = tuple(
        trial.suggest_int(f"units_l{i}", 16, 128) for i in range(n_layers)
    )
    return dict(
        hidden_layer_sizes=hidden,
        activation=trial.suggest_categorical("activation", ["relu", "tanh"]),
        alpha=trial.suggest_float("alpha", 1e-6, 1e-1, log=True),
        learning_rate_init=trial.suggest_float("lr", 1e-4, 1e-2, log=True),
        batch_size=trial.suggest_categorical("batch_size", [32, 64, 128]),
        # Fixed
        solver="adam",
        max_iter=500,
        early_stopping=True,         # validation_fraction=0.1, n_iter_no_change=10 (defaults)
        validation_fraction=0.1,
        n_iter_no_change=10,
        random_state=SEED,
    )

FEATURES = [
    "ca125","age","menopause_p","hb","wbc","plt","cr","bun",
    "alb","ast","alt","bili_total","pt_inr","is_inpatient",
    "has_ovarian_cancer","has_metastasis","has_diabetes",
    "has_hypertension","has_ckd","has_liver_disease","has_anemia",
]
TARGET = "has_chemo"
GROUP  = "subject_id"


# =============================================================================
# Data + CV setup
# =============================================================================
def load_data():
    if not DATA_FILE.exists():
        sys.exit(f"ERROR: {DATA_FILE} not found.")
    df = pd.read_csv(DATA_FILE)
    miss = [c for c in FEATURES + [TARGET, GROUP] if c not in df.columns]
    if miss:
        sys.exit(f"ERROR: missing columns: {miss}")
    X = df[FEATURES].copy()
    X["is_inpatient"] = X["is_inpatient"].astype(int)
    y = df[TARGET].astype(int).values
    groups = df[GROUP].values
    patient_chemo_ever = df.groupby(GROUP)[TARGET].max()
    strat = df[GROUP].map(patient_chemo_ever).astype(int).values
    return df, X, y, groups, strat


def cv_score(params: dict, X, y, splits) -> tuple[float, float]:
    aucs, aprs = [], []
    for tr, va in splits:
        X_tr, X_va = X.iloc[tr].copy(), X.iloc[va].copy()
        y_tr, y_va = y[tr], y[va]
        if y_va.sum() == 0 or y_va.sum() == len(y_va) or y_tr.sum() == 0:
            continue
        imp = SimpleImputer(strategy="median").set_output(transform="pandas")
        X_tr = imp.fit_transform(X_tr)
        X_va = imp.transform(X_va)
        # MLP requires scaling
        sc = StandardScaler().set_output(transform="pandas")
        X_tr = sc.fit_transform(X_tr)
        X_va = sc.transform(X_va)
        m = MLPClassifier(**params)
        m.fit(X_tr, y_tr)
        prob = m.predict_proba(X_va)[:, 1]
        aucs.append(roc_auc_score(y_va, prob))
        aprs.append(average_precision_score(y_va, prob))
    if not aucs:
        return 0.5, 0.0
    return float(np.mean(aucs)), float(np.mean(aprs))


# =============================================================================
# Main
# =============================================================================
def main():
    print("=" * 60)
    print(f"MLP — Optuna Tuning ({N_TRIALS} trials, {N_SPLITS}-fold CV)")
    print("=" * 60)

    df, X, y, groups, strat = load_data()
    print(f"  rows={len(X)}, patients={df[GROUP].nunique()}, "
          f"positives={y.sum()}/{len(y)} ({y.mean()*100:.1f}%)")

    cv = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    splits = list(cv.split(X, strat, groups))

    def objective(trial):
        params = define_search_space(trial)
        auc, _ = cv_score(params, X, y, splits)
        return auc

    t0 = time.time()
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=SEED),
    )
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)
    elapsed = time.time() - t0

    best = study.best_params
    full_params = define_search_space(optuna.trial.FixedTrial(best))
    aucs, aprs = [], []
    for tr, va in splits:
        X_tr, X_va = X.iloc[tr].copy(), X.iloc[va].copy()
        y_tr, y_va = y[tr], y[va]
        if y_va.sum() == 0 or y_va.sum() == len(y_va) or y_tr.sum() == 0:
            continue
        imp = SimpleImputer(strategy="median").set_output(transform="pandas")
        X_tr = imp.fit_transform(X_tr); X_va = imp.transform(X_va)
        sc = StandardScaler().set_output(transform="pandas")
        X_tr = sc.fit_transform(X_tr); X_va = sc.transform(X_va)
        m = MLPClassifier(**full_params); m.fit(X_tr, y_tr)
        p = m.predict_proba(X_va)[:, 1]
        aucs.append(roc_auc_score(y_va, p))
        aprs.append(average_precision_score(y_va, p))

    auc_mean, auc_std = float(np.mean(aucs)), float(np.std(aucs))
    auprc = float(np.mean(aprs))

    print(f"\n  Done in {elapsed:.1f}s")
    print(f"  Best CV-AUC   : {auc_mean:.4f} ± {auc_std:.4f}")
    print(f"  Best CV-AUPRC : {auprc:.4f}")
    print(f"  Per-fold AUC  : {[round(a, 4) for a in aucs]}")
    print(f"  Best params   :")
    for k, v in best.items():
        print(f"    {k}: {v}")

    history = [
        {"trial": t.number, "value": t.value, "params": t.params}
        for t in study.trials if t.value is not None
    ]
    output = {
        "model": "MLP",
        "n_trials": N_TRIALS,
        "n_splits": N_SPLITS,
        "seed": SEED,
        "elapsed_sec": round(elapsed, 1),
        "cv_auc_mean": auc_mean,
        "cv_auc_std":  auc_std,
        "cv_auprc":    auprc,
        "per_fold_auc": [round(a, 4) for a in aucs],
        "best_params": best,
        "history": history,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {OUT_FILE}")


if __name__ == "__main__":
    main()
