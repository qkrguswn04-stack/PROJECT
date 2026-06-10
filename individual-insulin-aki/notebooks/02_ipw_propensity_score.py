import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# 1. 고유한 stay_id 추출 및 8:2 분할
unique_ids = df_master_fd['stay_id'].unique()
train_ids, test_ids = train_test_split(unique_ids, test_size=0.2, random_state=42)

# 2. 분할된 ID에 해당하는 행들만 필터링
df_train = df_master_fd[df_master_fd['stay_id'].isin(train_ids)].copy()
df_test = df_master_fd[df_master_fd['stay_id'].isin(test_ids)].copy()

print(f"Train 셋 환자 수: {len(train_ids)}명 (행 수: {len(df_train)})")
print(f"Test 셋 환자 수: {len(test_ids)}명 (행 수: {len(df_test)})")

# 3. 모델에 사용할 Feature(X)와 Target(Y) 컬럼 정의
# 식별자(stay_id)와 시간 정보(time_step_end)는 학습에서 제외합니다.
feature_cols = ['time_step', 'age', 'gender_male', 'insulin_dosage', 'creatinine', 'fluid_input', 'diuretic_infusion']
target_col = 'next_creatinine'

X_train = df_train[feature_cols]
y_train = df_train[target_col]

X_test = df_test[feature_cols]
y_test = df_test[target_col]

print("\n학습 준비 완료!")
print(f"X_train 셰이프: {X_train.shape}, y_train 셰이프: {y_train.shape}")

# ──────────────────────────────────────────────────────────────────────────────

import subprocess
subprocess.run(['pip', 'install', 'xgboost'], check=True)
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

print("XGBoost 베이스라인 모델 학습 시작...")

# 1. XGBoost 회귀 모델 정의 및 학습
xgb_model = XGBRegressor(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    random_state=42,
    n_jobs=-1 # 모든 CPU 코어 사용
)

xgb_model.fit(X_train, y_train)
print("학습 완료!")

# 2. Test 셋 예측
y_pred = xgb_model.predict(X_test)

# 3. 예측 성능 평가 지표 계산
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n=== XGBoost Baseline 성능 평가 ===")
print(f"MAE  (평균 절대 오차): {mae:.4f}")
print(f"RMSE (평균 제곱근 오차): {rmse:.4f}")
print(f"R²   (결정 계수): {r2:.4f}")

# 4. 변수 중요도(Feature Importance) 확인
importances = pd.DataFrame({
    'Feature': feature_cols,
    'Importance': xgb_model.feature_importances_
}).sort_values(by='Importance', ascending=False)

print("\n=== 변수 중요도 ===")
print(importances.to_string(index=False))

# ──────────────────────────────────────────────────────────────────────────────

# 현재 데이터셋의 요약 통계량 확인
print(df_master_fd[['insulin_dosage', 'creatinine', 'next_creatinine', 'fluid_input']].describe())

# ──────────────────────────────────────────────────────────────────────────────

# 임상적 가이드라인에 따른 이상치 제거
# 1. 크레아티닌: 0 초과 ~ 15 이하 (15를 넘는 것은 극단적인 이상치 또는 데이터 오류)
# 2. 인슐린 12시간 총량: 0 이상 ~ 150 Units 이하 (12시간 동안 3000은 불가능)
# 3. 수액 12시간 총량: 0 이상 ~ 6000 mL 이하 (6리터)

df_cleaned = df_master_fd[
    (df_master_fd['creatinine'] > 0) & (df_master_fd['creatinine'] <= 15) &
    (df_master_fd['next_creatinine'] > 0) & (df_master_fd['next_creatinine'] <= 15) &
    (df_master_fd['insulin_dosage'] >= 0) & (df_master_fd['insulin_dosage'] <= 150) &
    (df_master_fd['fluid_input'] >= 0) & (df_master_fd['fluid_input'] <= 6000)
].copy()

print(f"정제 전 데이터 행 수: {len(df_master_fd)}")
print(f"정제 후 데이터 행 수: {len(df_cleaned)}")
print(f"제거된 불량 데이터 수: {len(df_master_fd) - len(df_cleaned)}")

# 정제된 데이터의 통계량 재확인
print(df_cleaned[['insulin_dosage', 'creatinine', 'next_creatinine', 'fluid_input']].describe())

# ──────────────────────────────────────────────────────────────────────────────

# 1. 정제된 데이터를 바탕으로 stay_id 추출 및 8:2 분할
unique_ids_cleaned = df_cleaned['stay_id'].unique()
train_ids, test_ids = train_test_split(unique_ids_cleaned, test_size=0.2, random_state=42)

df_train_c = df_cleaned[df_cleaned['stay_id'].isin(train_ids)].copy()
df_test_c = df_cleaned[df_cleaned['stay_id'].isin(test_ids)].copy()

# 2. X, y 재지정
X_train_c = df_train_c[feature_cols]
y_train_c = df_train_c[target_col]
X_test_c = df_test_c[feature_cols]
y_test_c = df_test_c[target_col]

print(f"새로운 Train 행 수: {len(X_train_c)}, Test 행 수: {len(X_test_c)}")

# 3. XGBoost 재학습
xgb_model_cleaned = XGBRegressor(
    n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1
)
xgb_model_cleaned.fit(X_train_c, y_train_c)

# 4. 예측 및 평가
y_pred_c = xgb_model_cleaned.predict(X_test_c)

print("\n=== [이상치 제거 후] XGBoost Baseline 성능 평가 ===")
print(f"MAE  (평균 절대 오차): {mean_absolute_error(y_test_c, y_pred_c):.4f}")
print(f"RMSE (평균 제곱근 오차): {np.sqrt(mean_squared_error(y_test_c, y_pred_c)):.4f}")
print(f"R²   (결정 계수): {r2_score(y_test_c, y_pred_c):.4f}")

# 5. 변수 중요도 재확인
importances_c = pd.DataFrame({
    'Feature': feature_cols,
    'Importance': xgb_model_cleaned.feature_importances_
}).sort_values(by='Importance', ascending=False)

print("\n=== 새로운 변수 중요도 ===")
print(importances_c.to_string(index=False))

# ──────────────────────────────────────────────────────────────────────────────

from sklearn.linear_model import LogisticRegression

# 1. 처치 변수 이진화 (인슐린 투여 여부 플래그 생성)
# 인슐린 용량이 0보다 크면 1(처치군), 0이면 0(대조군)
df_cleaned['treatment_binary'] = (df_cleaned['insulin_dosage'] > 0).astype(int)

# 2. 성향 점수 예측을 위한 Feature(공변량)와 Target 설정
# 의사가 인슐린을 줄지 말지 결정할 때 '현재 시점'에서 본 정보들입니다.
confounder_cols = ['time_step', 'age', 'gender_male', 'creatinine', 'fluid_input', 'diuretic_infusion']

X_ps = df_cleaned[confounder_cols]
y_ps = df_cleaned['treatment_binary']

# 3. 로지스틱 회귀를 이용한 성향 점수(Propensity Score) 모델 학습
ps_model = LogisticRegression(max_iter=1000, random_state=42)
ps_model.fit(X_ps, y_ps)

# 4. 각 행별로 처치를 받을 확률(Propensity Score) 추출
# [:, 1]은 인슐린을 투여받을 확률(1일 확률)을 뜻합니다.
df_cleaned['propensity_score'] = ps_model.predict_proba(X_ps)[:, 1]

print("성향 점수(Propensity Score) 산출 완료!")
print(df_cleaned[['stay_id', 'treatment_binary', 'propensity_score']].head())

# ──────────────────────────────────────────────────────────────────────────────

# 1. IPW 가중치 수식 적용
df_cleaned['ipw_weight'] = np.where(
    df_cleaned['treatment_binary'] == 1,
    1 / df_cleaned['propensity_score'],
    1 / (1 - df_cleaned['propensity_score'])
)

print("IPW 가중치 계산 완료!")
print(df_cleaned[['stay_id', 'treatment_binary', 'propensity_score', 'ipw_weight']].head())

# 2. 앞서 나눈 Train/Test 분할 구조에 가중치 컬럼 매칭하기
# 데이터 누수 방지를 위해 기존에 쪼개둔 분할 방식을 그대로 유지하면서 ipw_weight만 가져옵니다.
df_train_final = df_cleaned[df_cleaned['stay_id'].isin(train_ids)].copy()
df_test_final = df_cleaned[df_cleaned['stay_id'].isin(test_ids)].copy()

# 3. 인과 추론 가중치 모델(Weighted Model) 학습을 위한 준비
X_train_w = df_train_final[feature_cols]
y_train_w = df_train_final[target_col]
w_train = df_train_final['ipw_weight'] # 학습에 사용할 가중치

X_test_w = df_test_final[feature_cols]
y_test_w = df_test_final[target_col]
w_test = df_test_final['ipw_weight']

print("\n=== 가중치 데이터셋 세팅 완료 ===")
print(f"Train 가중치 평균: {w_train.mean():.4f}, 최댓값: {w_train.max():.4f}")
