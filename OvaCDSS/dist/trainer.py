import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, roc_curve, classification_report
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from config import FEATURE_CONFIG, MODEL_CONFIG, ROMA_THRESHOLDS


class OvaTrainer:

    def __init__(self):
        self.models = {
            'Logistic Regression': LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42),
            'Random Forest':       RandomForestClassifier(n_estimators=200, class_weight='balanced', max_depth=6, random_state=42),
            'XGBoost':             XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, scale_pos_weight=3, eval_metric='auc', random_state=42),
            'GBM':                 GradientBoostingClassifier(n_estimators=150, max_depth=4, learning_rate=0.05, random_state=42),
        }
        self.results    = {}
        self.best_model = None
        self.best_name  = None

    def prepare_data(self, df: pd.DataFrame):
        X = df.drop(columns=[FEATURE_CONFIG['target']])
        y = df[FEATURE_CONFIG['target']]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=MODEL_CONFIG['test_size'],
            stratify=y, random_state=MODEL_CONFIG['random_state']
        )

        ratio = y_train.value_counts()
        print(f"[클래스 비율] 음성:{ratio[0]}  양성:{ratio[1]}")

        if ratio[0] / ratio[1] > 2:
            print("[SMOTE] 클래스 불균형 보정 적용")
            X_train, y_train = SMOTE(random_state=42).fit_resample(X_train, y_train)

        return X_train, X_test, y_train, y_test

    def roma_baseline(self, df: pd.DataFrame):
        y_true = df[FEATURE_CONFIG['target']]

        y_pred = df.apply(
            lambda row: 1 if row['roma_score_calc'] > (
                ROMA_THRESHOLDS['post'] if row['menopause'] == 1 else ROMA_THRESHOLDS['pre']
            ) else 0, axis=1
        )

        auc = roc_auc_score(y_true, df['roma_score_calc'])
        print(f"\n📊 ROMA Baseline AUC: {auc:.4f}")
        print(classification_report(y_true, y_pred, target_names=['양성', '악성']))
        return auc

    def train_all(self, X_train, y_train):
        cv = StratifiedKFold(n_splits=MODEL_CONFIG['cv_folds'], shuffle=True, random_state=MODEL_CONFIG['random_state'])

        print(f"\n📋 {MODEL_CONFIG['cv_folds']}-Fold CV 결과")
        for name, model in self.models.items():
            scores = cross_val_score(model, X_train, y_train, cv=cv, scoring='roc_auc')
            self.results[name] = {'cv_mean': scores.mean(), 'cv_std': scores.std(), 'model': model}
            print(f"{name:<25} AUC: {scores.mean():.4f} ± {scores.std():.4f}")

        self.best_name  = max(self.results, key=lambda k: self.results[k]['cv_mean'])
        self.best_model = self.results[self.best_name]['model']
        self.best_model.fit(X_train, y_train)
        print(f"\n✅ 최적 모델: {self.best_name} (AUC={self.results[self.best_name]['cv_mean']:.4f})")
        return self.best_model

    def evaluate(self, X_test, y_test, roma_baseline_auc=None):
        y_prob = self.best_model.predict_proba(X_test)[:, 1]
        y_pred = self.best_model.predict(X_test)
        auc    = roc_auc_score(y_test, y_prob)

        print(f"\n🎯 테스트셋 최종 결과 — {self.best_name}")
        print(f"AUC: {auc:.4f}", end="")
        if roma_baseline_auc:
            diff = auc - roma_baseline_auc
            print(f"  (ROMA 대비 {'+' if diff > 0 else ''}{diff:.4f})")

        print(classification_report(y_test, y_pred, target_names=['양성', '악성']))
        self._plot_roc(y_test, y_prob, auc, roma_baseline_auc)
        return auc

    def _plot_roc(self, y_test, y_prob, auc, roma_auc=None):
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label=f'{self.best_name} (AUC={auc:.3f})', color='steelblue', linewidth=2)
        if roma_auc:
            plt.axhline(y=roma_auc, color='orange', linestyle='--', label=f'ROMA baseline (AUC={roma_auc:.3f})')
        plt.plot([0,1], [0,1], 'k--', alpha=0.4)
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve — MIMIC-Ova ML vs ROMA')
        plt.legend()
        plt.tight_layout()
        plt.savefig('roc_curve.png', dpi=150)
        plt.show()

    def explain_shap(self, X_train):
        explainer   = shap.TreeExplainer(self.best_model)
        shap_values = explainer.shap_values(X_train)
        shap.summary_plot(shap_values, X_train, plot_type='bar', show=False)
        plt.tight_layout()
        plt.savefig('shap_importance.png', dpi=150)
        plt.show()

    def save(self, path='best_model.pkl'):
        joblib.dump(self.best_model, path)
        print(f"[저장] {path}")