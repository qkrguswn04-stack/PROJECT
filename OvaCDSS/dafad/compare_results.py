"""
============================================================
Compare tuning results from 3 team members
============================================================

Reads:
  - xgboost_best.json
  - lightgbm_best.json
  - mlp_best.json

Prints a side-by-side comparison and saves comparison_summary.json.
Files that are missing are skipped with a warning.

Usage: python compare_results.py
============================================================
"""
import json
from pathlib import Path

FILES = {
    "XGBoost":  Path("xgboost_best.json"),
    "LightGBM": Path("lightgbm_best.json"),
    "MLP":      Path("mlp_best.json"),
}

results = {}
for name, fp in FILES.items():
    if fp.exists():
        with open(fp, encoding="utf-8") as f:
            results[name] = json.load(f)
    else:
        print(f"  [warn] {fp} not found — skipping {name}")

if not results:
    raise SystemExit("No result files found. Each team member must run their tune_*.py first.")

print("=" * 70)
print("MODEL COMPARISON")
print("=" * 70)
print(f"  {'Model':10s}  {'CV-AUC':>16s}  {'CV-AUPRC':>10s}  "
      f"{'Trials':>7s}  {'Time(s)':>8s}")
for name, r in results.items():
    auc = f"{r['cv_auc_mean']:.4f} ± {r['cv_auc_std']:.4f}"
    print(f"  {name:10s}  {auc:>16s}  {r['cv_auprc']:>10.4f}  "
          f"{r['n_trials']:>7d}  {r['elapsed_sec']:>8.1f}")

# Per-fold breakdown
print("\n" + "=" * 70)
print("PER-FOLD AUC")
print("=" * 70)
max_folds = max(len(r['per_fold_auc']) for r in results.values())
print(f"  {'Model':10s}  " + "  ".join(f"Fold {i}" for i in range(max_folds)))
for name, r in results.items():
    cells = [f"{a:.4f}" for a in r['per_fold_auc']]
    while len(cells) < max_folds:
        cells.append("  -   ")
    print(f"  {name:10s}  " + "  ".join(cells))

# Winner
best = max(results.items(), key=lambda kv: kv[1]['cv_auc_mean'])
print("\n" + "=" * 70)
print(f"  Winner: {best[0]} (CV-AUC = {best[1]['cv_auc_mean']:.4f})")
print("=" * 70)

# Best params per model
print("\nBest params:")
for name, r in results.items():
    print(f"\n  {name}:")
    for k, v in r['best_params'].items():
        print(f"    {k}: {v}")

# Save consolidated
with open("comparison_summary.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\nSaved: comparison_summary.json")
