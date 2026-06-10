# ==============================================================================
# 02_ipw_propensity_score.py
# 성향 점수(Propensity Score) 산출 → IPW 가중치 계산 → 공변량 균형 진단
# 입력: sip_step1_final.csv
# 출력: sip_step2_ipw.csv
# ==============================================================================

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LogisticRegression

# ─────────────────────────────────────────────
# STEP 1. 데이터 로드
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1. 01단계 정제 데이터 로드")
print("=" * 60)

df = pd.read_csv('sip_step1_final.csv')
print(f"로드 완료: {df.shape}")
print(f"컬럼: {list(df.columns)}")


# ─────────────────────────────────────────────
# STEP 2. 처치 변수 이진화
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2. 처치 변수 이진화 (인슐린 투여 여부)")
print("=" * 60)

# 인슐린 용량 > 0 이면 처치군(1), 아니면 대조군(0)
# ※ 이진화는 IPW 성향 점수 추정 용도. 실제 모델 학습엔 연속형 insulin_dosage 사용
df['treatment_binary'] = (df['insulin_dosage'] > 0).astype(int)

treated = df['treatment_binary'].sum()
control = len(df) - treated
print(f"처치군(인슐린 투여): {treated:,}행 ({treated/len(df)*100:.1f}%)")
print(f"대조군(미투여):       {control:,}행 ({control/len(df)*100:.1f}%)")


# ─────────────────────────────────────────────
# STEP 3. 성향 점수(Propensity Score) 산출
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3. 성향 점수 산출 (로지스틱 회귀)")
print("=" * 60)

# 공변량: 의사가 인슐린 처방을 결정할 때 현재 시점에서 관찰 가능한 변수들
# ※ creatinine = 현재 크레아티닌 (공변량) — next_creatinine이 타깃이므로 역인과 없음
confounder_cols = ['time_step', 'age', 'gender_male',
                   'creatinine', 'fluid_input', 'diuretic_infusion']

X_ps = df[confounder_cols]
y_ps = df['treatment_binary']

ps_model = LogisticRegression(max_iter=1000, random_state=42)
ps_model.fit(X_ps, y_ps)

df['propensity_score'] = ps_model.predict_proba(X_ps)[:, 1]

print(f"성향 점수 산출 완료")
print(f"  최솟값: {df['propensity_score'].min():.4f}")
print(f"  최댓값: {df['propensity_score'].max():.4f}")
print(f"  평균:   {df['propensity_score'].mean():.4f}")


# ─────────────────────────────────────────────
# STEP 4. IPW 가중치 산출 및 Trimming
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4. IPW 가중치 산출 및 99% Trimming")
print("=" * 60)

# ATE(Average Treatment Effect) 가중치 공식
# 처치군: 1 / P(T=1|X),  대조군: 1 / P(T=0|X) = 1 / (1 - PS)
df['ipw_weight'] = np.where(
    df['treatment_binary'] == 1,
    1.0 / df['propensity_score'],
    1.0 / (1.0 - df['propensity_score'])
)

# 상위 99% 에서 클리핑 (극단적 가중치 폭발 방지)
upper_bound          = df['ipw_weight'].quantile(0.99)
df['ipw_trimmed']    = np.clip(df['ipw_weight'], a_min=None, a_max=upper_bound)

print(f"Raw IPW   — 최댓값: {df['ipw_weight'].max():.2f},  평균: {df['ipw_weight'].mean():.2f}")
print(f"Trimmed IPW — 최댓값: {df['ipw_trimmed'].max():.2f},  평균: {df['ipw_trimmed'].mean():.2f}")


# ─────────────────────────────────────────────
# STEP 5. 공변량 균형 진단 (SMD)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5. 공변량 균형 진단 — SMD (Standardized Mean Difference)")
print("=" * 60)
print("※ |SMD| < 0.1 이면 두 집단이 충분히 균형 잡혀 있다고 판단\n")

smd_results = []
for col in confounder_cols:
    treated_vals = df[df['treatment_binary'] == 1][col]
    control_vals = df[df['treatment_binary'] == 0][col]
    pooled_std   = np.sqrt((treated_vals.std() ** 2 + control_vals.std() ** 2) / 2)
    smd          = (treated_vals.mean() - control_vals.mean()) / pooled_std if pooled_std > 0 else 0.0
    smd_results.append({'공변량': col, 'SMD': round(smd, 4),
                        '균형 여부': '✅ 균형' if abs(smd) < 0.1 else '⚠️  불균형'})

smd_df = pd.DataFrame(smd_results)
print(smd_df.to_string(index=False))

# SMD 시각화
plt.figure(figsize=(8, 4))
colors = ['#059669' if abs(v) < 0.1 else '#DC2626' for v in smd_df['SMD']]
plt.barh(smd_df['공변량'], smd_df['SMD'].abs(), color=colors, height=0.5)
plt.axvline(x=0.1, color='gray', linestyle='--', linewidth=1, label='Threshold (0.1)')
plt.xlabel('|SMD|')
plt.title('Covariate Balance: Standardized Mean Difference')
plt.legend()
plt.tight_layout()
plt.savefig('covariate_balance_smd.png', dpi=150)
plt.close()
print("\n균형 진단 차트 저장: covariate_balance_smd.png")


# ─────────────────────────────────────────────
# STEP 6. 저장
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6. IPW 가중치 적용 데이터셋 저장")
print("=" * 60)

df.to_csv('sip_step2_ipw.csv', index=False)
print("✅ 저장 완료: sip_step2_ipw.csv")
print(f"   최종 셰이프: {df.shape}")
print(f"   추가 컬럼:   treatment_binary, propensity_score, ipw_weight, ipw_trimmed")
