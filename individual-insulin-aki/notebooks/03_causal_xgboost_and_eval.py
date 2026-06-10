# ==============================================================================
# 03_causal_xgboost_and_eval.py
# 베이스라인 XGBoost → IPW 가중 인과 모델 학습 → 플라시보 강건성 검증 → 모델 저장
# 입력: sip_step2_ipw.csv
# 출력: causal_insulin_model.pkl, feature_columns.pkl, test_data_for_app.csv
# ==============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ─────────────────────────────────────────────
# STEP 1. 데이터 로드 및 Train/Test 분할
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1. 02단계 IPW 데이터 로드 및 Train/Test 분할")
print("=" * 60)

df = pd.read_csv('sip_step2_ipw.csv')
print(f"로드 완료: {df.shape}")

# 피처 및 타깃 정의
# ※ time_step_end(시각 문자열)는 학습에서 제외, time_step(순서 정수)만 사용
feature_cols = ['time_step', 'age', 'gender_male',
                'insulin_dosage', 'creatinine',
                'fluid_input', 'diuretic_infusion']
target_col   = 'next_creatinine'

# 환자(stay_id) 단위로 분할 — 데이터 누수 방지
unique_ids           = df['stay_id'].unique()
train_ids, test_ids  = train_test_split(unique_ids, test_size=0.2, random_state=42)

df_train = df[df['stay_id'].isin(train_ids)].copy()
df_test  = df[df['stay_id'].isin(test_ids)].copy()

print(f"Train: {len(train_ids)}명 ({len(df_train):,}행)  |  Test: {len(test_ids)}명 ({len(df_test):,}행)")

X_train = df_train[feature_cols];  y_train = df_train[target_col]
X_test  = df_test[feature_cols];   y_test  = df_test[target_col]
w_train = df_train['ipw_trimmed']


# ─────────────────────────────────────────────
# STEP 2. 베이스라인 XGBoost (IPW 미적용) 학습 및 평가
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2. 베이스라인 XGBoost 학습 (IPW 미적용)")
print("=" * 60)

xgb_baseline = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1,
    random_state=42, n_jobs=-1
)
xgb_baseline.fit(X_train, y_train)
y_pred_base = xgb_baseline.predict(X_test)

mae_base  = mean_absolute_error(y_test, y_pred_base)
rmse_base = np.sqrt(mean_squared_error(y_test, y_pred_base))
r2_base   = r2_score(y_test, y_pred_base)

print(f"MAE:  {mae_base:.4f}")
print(f"RMSE: {rmse_base:.4f}")
print(f"R²:   {r2_base:.4f}")

imp_base = pd.DataFrame({
    'Feature':    feature_cols,
    'Baseline':   xgb_baseline.feature_importances_
}).sort_values('Baseline', ascending=False)
print("\n베이스라인 변수 중요도:")
print(imp_base.to_string(index=False))


# ─────────────────────────────────────────────
# STEP 3. IPW 가중 인과 XGBoost 학습 및 평가
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3. IPW 가중 인과 XGBoost 학습")
print("=" * 60)

xgb_causal = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1,
    random_state=42, n_jobs=-1
)
# sample_weight에 IPW 가중치 주입 → Pseudo-RCT 환경에서 학습
xgb_causal.fit(X_train, y_train, sample_weight=w_train)
y_pred_causal = xgb_causal.predict(X_test)

mae_c  = mean_absolute_error(y_test, y_pred_causal)
rmse_c = np.sqrt(mean_squared_error(y_test, y_pred_causal))
r2_c   = r2_score(y_test, y_pred_causal)

print(f"MAE:  {mae_c:.4f}")
print(f"RMSE: {rmse_c:.4f}")
print(f"R²:   {r2_c:.4f}")

imp_causal = pd.DataFrame({
    'Feature':   feature_cols,
    'Causal':    xgb_causal.feature_importances_
}).sort_values('Causal', ascending=False)
print("\n인과 모델 변수 중요도:")
print(imp_causal.to_string(index=False))


# ─────────────────────────────────────────────
# STEP 4. 베이스라인 vs 인과 모델 비교
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4. 베이스라인 vs 인과 모델 성능 비교")
print("=" * 60)

compare = pd.DataFrame({
    '지표':       ['MAE', 'RMSE', 'R²'],
    'Baseline':   [round(mae_base, 4), round(rmse_base, 4), round(r2_base, 4)],
    'Causal IPW': [round(mae_c, 4),    round(rmse_c, 4),    round(r2_c, 4)],
})
print(compare.to_string(index=False))

# 변수 중요도 비교 — insulin_dosage 신호 복원 확인
insulin_base   = imp_base[imp_base['Feature'] == 'insulin_dosage']['Baseline'].values[0]
insulin_causal = imp_causal[imp_causal['Feature'] == 'insulin_dosage']['Causal'].values[0]
signal_gain    = (insulin_causal - insulin_base) / insulin_base * 100
print(f"\ninsulin_dosage 중요도: Baseline {insulin_base:.4f} → Causal {insulin_causal:.4f}")
print(f"인과 신호 복원: {signal_gain:+.1f}%")

# 변수 중요도 시각화
imp_merged = pd.merge(imp_base, imp_causal, on='Feature')
imp_merged = imp_merged.sort_values('Causal', ascending=True)

fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(imp_merged))
ax.barh(x - 0.18, imp_merged['Baseline'], height=0.35, label='Baseline', color='#94A3B8')
ax.barh(x + 0.18, imp_merged['Causal'],   height=0.35, label='Causal IPW', color='#1D4ED8')
ax.set_yticks(x)
ax.set_yticklabels(imp_merged['Feature'])
ax.set_xlabel('Relative Importance')
ax.set_title('Feature Importance: Baseline vs Causal IPW Model')
ax.legend()
plt.tight_layout()
plt.savefig('feature_importance_comparison.png', dpi=150)
plt.close()
print("\n변수 중요도 비교 차트 저장: feature_importance_comparison.png")


# ─────────────────────────────────────────────
# STEP 5. 플라시보 강건성 검증
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5. 플라시보 강건성 검증 (Placebo Treatment Refuter)")
print("=" * 60)
print("인슐린 처치 변수를 무작위 셔플 → 플라시보 모델 학습")
print("→ 반사실 곡선이 평평해지면 인과 모델의 신호가 진짜임을 증명\n")

# 플라시보 모델: 인슐린 처치 변수를 무작위로 섞어 인과 신호 파괴
df_placebo = df_train.copy()
df_placebo['insulin_dosage'] = np.random.permutation(df_placebo['insulin_dosage'].values)

xgb_placebo = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1,
    random_state=42, n_jobs=-1
)
xgb_placebo.fit(
    df_placebo[feature_cols],
    df_placebo[target_col],
    sample_weight=df_placebo['ipw_trimmed']
)
print("플라시보 모델 학습 완료")

# 반사실 시뮬레이션: 샘플 환자 1명 선택
sample_patient  = df_test[df_test['insulin_dosage'] == 0].iloc[0]
sim_dosages     = np.arange(0, 51, 1)
df_sim          = pd.DataFrame([sample_patient[feature_cols]] * len(sim_dosages))
df_sim['insulin_dosage'] = sim_dosages

causal_preds  = xgb_causal.predict(df_sim)
placebo_preds = xgb_placebo.predict(df_sim)

# 시각화
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(sim_dosages, causal_preds,  color='#1D4ED8', linewidth=2.5,
        label='True Causal Model (IPW-XGBoost)')
ax.plot(sim_dosages, placebo_preds, color='#9CA3AF', linewidth=2.5, linestyle='--',
        label='Placebo Model (Shuffled Insulin)')
ax.scatter(sample_patient['insulin_dosage'], sample_patient['next_creatinine'],
           color='#EA580C', s=100, zorder=5, label='Actual Outcome')
ax.set_xlabel('Virtual Insulin Dosage (Units)')
ax.set_ylabel('Predicted Next Creatinine (mg/dL)')
ax.set_title(f'Placebo Robustness Test — Patient {int(sample_patient["stay_id"])}')
ax.grid(True, linestyle=':', alpha=0.5)
ax.legend()
plt.tight_layout()
plt.savefig('placebo_refutation_test.png', dpi=150)
plt.close()
print("플라시보 검증 차트 저장: placebo_refutation_test.png")

# 기울기 차이로 플라시보 통과 여부 수치 확인
causal_slope  = causal_preds[-1]  - causal_preds[0]
placebo_slope = placebo_preds[-1] - placebo_preds[0]
print(f"\n인과 모델 곡선 기울기 (0→50U): {causal_slope:+.4f}")
print(f"플라시보 곡선 기울기 (0→50U):  {placebo_slope:+.4f}")
if abs(placebo_slope) < abs(causal_slope) * 0.2:
    print("✅ 플라시보 검증 PASS: 셔플된 처치에서 인과 신호 소멸 확인")
else:
    print("⚠️  플라시보 곡선이 예상보다 기울어짐 — 모델 점검 필요")


# ─────────────────────────────────────────────
# STEP 6. 모델 및 앱 구동 파일 저장
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6. 모델 및 앱 구동 파일 저장")
print("=" * 60)

joblib.dump(xgb_causal,   'causal_insulin_model.pkl')
joblib.dump(feature_cols, 'feature_columns.pkl')

# 앱에서 환자 선택용 테스트 데이터
df_test.to_csv('test_data_for_app.csv', index=False)

print("✅ 저장 완료")
print("   causal_insulin_model.pkl — 인과 XGBoost 모델")
print("   feature_columns.pkl     — 피처 컬럼 리스트")
print("   test_data_for_app.csv   — Streamlit 앱 테스트 데이터")
