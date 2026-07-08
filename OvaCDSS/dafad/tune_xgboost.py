"""
============================================================
XGBoost — Optuna Hyperparameter Tuning
Owner: <팀원 이름 적기>
============================================================

Task   : Binary classification — has_chemo (chemo start at RMI timepoint)
Input  : chemo_training_dataset.csv  (same directory)
Output : xgboost_best.json           (best params + CV score + history)

Usage  : python tune_xgboost.py

Requirements:
  pip install pandas numpy scikit-learn xgboost optuna joblib

What you can tune (CONFIG section below):
  - N_TRIALS         : number of Optuna trials (default 50)
  - N_SPLITS         : K for cross-validation (default 3)
  - SEARCH_SPACE     : hyperparameter ranges for each parameter
  - SEED             : random seed for reproducibility
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

try:
    import xgboost as xgb
except ImportError:
    sys.exit("Missing dependency. Run:\n  "
             "pip install pandas numpy scikit-learn xgboost optuna joblib")

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.INFO)   # set WARNING to silence

# =============================================================================
# CONFIG  (edit freely)
# =============================================================================
DATA_FILE = Path("chemo_training_dataset.csv")
OUT_FILE  = Path("xgboost_best.json")

SEED      = 42
N_TRIALS  = 50      # try 100~200 if you have time
N_SPLITS  = 3       # 3 is safer here (only 15/68 patients receive chemo)

# Hyperparameter search space — edit ranges as you like
def define_search_space(trial: optuna.Trial) -> dict:
    return dict(
        n_estimators=trial.suggest_int("n_estimators", 50, 500),
        max_depth=trial.suggest_int("max_depth", 2, 8),
        learning_rate=trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
        subsample=trial.suggest_float("subsample", 0.5, 1.0),
        colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
        min_child_weight=trial.suggest_int("min_child_weight", 1, 10),
        gamma=trial.suggest_float("gamma", 0, 5),
        reg_alpha=trial.suggest_float("reg_alpha", 1e-8, 10, log=True),
        reg_lambda=trial.suggest_float("reg_lambda", 1e-8, 10, log=True),
        # Fixed
        tree_method="hist",
        eval_metric="auc",
        random_state=SEED,
        n_jobs=1,
        verbosity=0,
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
# Data + CV setup (do not modify unless you know why)
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
    # Stratify by patient-level 'chemo ever' so every fold has positives
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
        m = xgb.XGBClassifier(**params)
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
    print(f"XGBoost — Optuna Tuning ({N_TRIALS} trials, {N_SPLITS}-fold CV)")
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

    # Re-evaluate best params for AUPRC + std + per-fold
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
        m = xgb.XGBClassifier(**full_params); m.fit(X_tr, y_tr)
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
        "model": "XGBoost",
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
