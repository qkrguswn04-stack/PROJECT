import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

print("IPW 가중치 반영 XGBoost 모델 학습 시작...")

# 1. 가중치 반영 모델 정의
xgb_causal = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
)

# 2. fit 함수에 sample_weight 파라미터를 추가하여 학습 진행
xgb_causal.fit(X_train_c, y_train_c, sample_weight=w_train)
print("학습 완료!")

# 3. Test 셋 예측 (평가는 가중치 없이 실제 정답 수치와 비교합니다)
y_pred_causal = xgb_causal.predict(X_test_c)

print("\n=== [Step 4] IPW Causal XGBoost 성능 평가 ===")
print(f"MAE  (평균 절대 오차): {mean_absolute_error(y_test_c, y_pred_causal):.4f}")
print(f"RMSE (평균 제곱근 오차): {np.sqrt(mean_squared_error(y_test_c, y_pred_causal)):.4f}")
print(f"R²   (결정 계수): {r2_score(y_test_c, y_pred_causal):.4f}")

# 4. 인과 모델의 변수 중요도 확인
importances_causal = pd.DataFrame({
    'Feature': feature_cols,
    'Causal_Importance': xgb_causal.feature_importances_
}).sort_values(by='Causal_Importance', ascending=False)

print("\n=== 인과 모델 변수 중요도 ===")
print(importances_causal.to_string(index=False))

# ──────────────────────────────────────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────────────────────────────────────

import matplotlib.pyplot as plt
import seaborn as sns

# 1. 테스트셋에서 인슐린을 전혀 맞지 않았고(dosage=0), 신장 수치가 다소 높은 환자의 샘플 하나 선택
# 시뮬레이션 효과를 극적으로 확인하기 위해 특정 행을 지정합니다.
sample_patient = df_test_final[df_test_final['insulin_dosage'] == 0].iloc[10]

print("=== 시뮬레이션 대상 환자 실제 정보 ===")
print(f"환자 ID (stay_id): {sample_patient['stay_id']}")
print(f"현재 크레아티닌 (creatinine): {sample_patient['creatinine']:.2f}")
print(f"실제 투여된 인슐린 (insulin_dosage): {sample_patient['insulin_dosage']:.2f}")
print(f"실제 다음 크레아티닌 (next_creatinine): {sample_patient['next_creatinine']:.2f}")

# 2. 가상 시나리오 생성: 인슐린 용량을 0부터 50까지 변화시킴
sim_dosages = np.arange(0, 51, 1)

# 가상 데이터를 담을 데이터프레임 복사 생성
df_sim = pd.DataFrame([sample_patient[feature_cols]] * len(sim_dosages))
df_sim['insulin_dosage'] = sim_dosages # 인슐린 용량만 가상으로 변경

# 3. 인과 모델을 통한 가상 결과(Counterfactual) 예측
sim_preds = xgb_causal.predict(df_sim)

# 4. 가상 시뮬레이션 곡선 시각화
plt.figure(figsize=(10, 6))
plt.plot(sim_dosages, sim_preds, color='b', linewidth=2.5, label='Counterfactual Curve')
plt.axvline(x=sample_patient['insulin_dosage'], color='r', linestyle='--', label=f"Actual Dosage ({sample_patient['insulin_dosage']})")
plt.scatter(sample_patient['insulin_dosage'], sample_patient['next_creatinine'], color='red', s=100, zorder=5, label='Actual Outcome')

plt.title(f"Counterfactual Simulation for Patient {int(sample_patient['stay_id'])}", fontsize=14, pad=15)
plt.xlabel("Virtual Insulin Dosage (Units)", fontsize=12)
plt.ylabel("Predicted Next Creatinine (mg/dL)", fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(fontsize=11)
plt.show()

# ──────────────────────────────────────────────────────────────────────────────

print("플라시보 강건성 검증(Placebo Test) 시작...")

# 1. 인슐린 처치 변수를 무작위로 뒤섞어(Shuffle) 환자 상태와 상관없는 가짜 변수 생성
df_placebo = df_train_final.copy()
df_placebo['insulin_dosage'] = np.random.permutation(df_placebo['insulin_dosage'].values)

# 2. 가짜 데이터로 플라시보 모델 학습
X_train_p = df_placebo[feature_cols]
y_train_p = df_placebo[target_col]
w_train_p = df_placebo['ipw_weight']

xgb_placebo = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
)
xgb_placebo.fit(X_train_p, y_train_p, sample_weight=w_train_p)
print("플라시보 모델 학습 완료!")

# 3. 동일한 환자(30006118)에 대해 플라시보 모델로 가상 시뮬레이션 수행
placebo_preds = xgb_placebo.predict(df_sim)

# 4. 진짜 인과 모델 결과와 플라시보 모델 결과 비교 시각화
plt.figure(figsize=(12, 6))
plt.plot(sim_dosages, sim_preds, color='b', linewidth=2.5, label='True Causal Model (Insulin)')
plt.plot(sim_dosages, placebo_preds, color='gray', linestyle='--', linewidth=2.5, label='Placebo Model (Shuffled Insulin)')
plt.scatter(sample_patient['insulin_dosage'], sample_patient['next_creatinine'], color='red', s=100, zorder=5, label='Actual Outcome')

plt.title(f"Robustness Test (Placebo) for Patient {int(sample_patient['stay_id'])}", fontsize=14, pad=15)
plt.xlabel("Virtual Insulin Dosage (Units)", fontsize=12)
plt.ylabel("Predicted Next Creatinine (mg/dL)", fontsize=12)
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(fontsize=11)
plt.show()

# ──────────────────────────────────────────────────────────────────────────────

import joblib

# 1. 학습된 인과 모델 저장
joblib.dump(xgb_causal, 'causal_insulin_model.pkl')

# 2. 대시보드에서 불러올 테스트 데이터셋 저장 (환자 선택용)
df_test_final.to_csv('test_data_for_app.csv', index=False)

# 3. 모델이 사용하는 피처 리스트 저장
joblib.dump(feature_cols, 'feature_columns.pkl')

print("대시보드 구축용 파일 저장 완료!")

# ──────────────────────────────────────────────────────────────────────────────

import matplotlib.pyplot as plt
import seaborn as sns

# 변수 중요도 데이터프레임 생성
importances = pd.DataFrame({
    'Feature': feature_cols,
    'Importance': xgb_causal.feature_importances_
}).sort_values(by='Importance', ascending=True) # 시각화를 위해 오름차순 정렬

# 가로 바 차트 시각화
plt.figure(figsize=(10, 6))
sns.barplot(x='Importance', y='Feature', data=importances, palette='mako')
plt.title("XGBoost Feature Importance (IPW Weighted)", fontsize=14, pad=15)
plt.xlabel("Relative Importance Score")
plt.ylabel("Features")
plt.grid(True, axis='x', linestyle=':', alpha=0.6)
plt.show()

# ──────────────────────────────────────────────────────────────────────────────

# Train 데이터셋의 각 컬럼별 데이터 타입 확인
print("=== 컬럼별 데이터 타입 ===")
print(X_train_c.dtypes)

# 문자열(object) 타입으로 되어 있는 컬럼이 있는지 필터링
object_cols = X_train_c.select_dtypes(include=['object']).columns
print(f"\n문자열 타입으로 의심되는 컬럼: {list(object_cols)}")

