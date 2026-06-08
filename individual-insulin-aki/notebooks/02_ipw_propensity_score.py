import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

def compute_propensity_score_and_ipw(df):
    """
    환자의 공변량을 바탕으로 인슐린 처방 확률(성향 점수)을 계산하고,
    이를 이용해 선택 편향을 통제할 역성향 점수 가중치(IPW)를 수립합니다.
    """
    print("⚖️ [Propensity Score] 의사 처방 경향성을 반영한 성향 점수 모델링 시작...")
    
    # 1. 처치 변수 이진화 (인슐린 투여 여부: Treatment Group vs Control Group)
    # 연속형 용량을 다루기 전, 기저 배경 균형을 맞추기 위한 이진 처치(Binary Treatment) 정의
    df['treatment'] = np.where(df['insulin_dosage'] > 0, 1, 0)
    
    # 성향 점수 계산에 사용할 배경 공변량 정의 (혼란 변수 통제)
    confounder_cols = ['age', 'gender_male', 'fluid_input', 'diuretic_infusion', 'creatinine']
    
    X_confounders = df[confounder_cols]
    y_treatment = df['treatment']
    
    # 2. 로지스틱 회귀 모델을 통한 성향 점수(Propensity Score) 산출
    ps_model = LogisticRegression(max_iter=1000, random_state=42)
    ps_model.fit(X_confounders, y_treatment)
    
    # 환자별 처치군에 속할 확률(Propensity Score) 저장
    df['propensity_score'] = ps_model.predict_proba(X_confounders)[:, 1]
    
    print("✅ 성향 점수 산출 완료 (최저: {:.4f}, 최고: {:.4f})".format(
        df['propensity_score'].min(), df['propensity_score'].max()
    ))
    
    # 3. 역성향 점수 가중치(IPW) 산출
    print("⏳ [IPW Calculation] 잠재 결과 추론을 위한 가중치 계산 중...")
    df['ipw'] = np.where(
        df['treatment'] == 1,
        1.0 / df['propensity_score'],
        1.0 / (1.0 - df['propensity_score'])
    )
    
    # 4. 극단적 가중치로 인한 모형 불안정 방지 (Trimming 기법 적용)
    # 가중치 폭발을 막기 위해 상위 99% 선에서 클리핑(Trimming) 수행
    upper_bound = df['ipw'].quantile(0.99)
    df['ipw_trimmed'] = np.clip(df['ipw'], a_min=None, a_max=upper_bound)
    
    print("✅ IPW 가중치 수립 완료 (Trimmed Max Bound: {:.2f}, 평균 가중치: {:.2f})".format(
        df['ipw_trimmed'].max(), df['ipw_trimmed'].mean()
    ))
    
    return df

if __name__ == "__main__":
    # 1단계 파이프라인 아웃풋 데이터 가정 (테스트용 가상 데이터 연동)
    # 실제 환경에서는 01단계의 최종 데이터프레임이 인풋으로 들어옵니다.
    np.random.seed(42)
    mock_grid_df = pd.DataFrame({
        'stay_id': np.repeat(np.arange(1000, 1100), 5),
        'time_step': np.tile(np.arange(5), 100),
        'creatinine': np.random.uniform(0.8, 4.5, 500),
        'insulin_dosage': np.random.choice([0, 10, 20, 30], 500, p=[0.4, 0.3, 0.2, 0.1]),
        'age': np.random.randint(30, 85, 500),
        'gender_male': np.random.choice([0, 1], 500),
        'fluid_input': np.random.uniform(200, 1500, 500),
        'diuretic_infusion': np.random.choice([0, 1], 500),
        'next_creatinine': np.random.uniform(0.8, 4.5, 500)
    })
    
    # IPW 파이프라인 실행
    ipw_output_df = compute_propensity_score_and_ipw(mock_grid_df)
    
    print("
[IPW Output Preview]")
    print(ipw_output_df[['stay_id', 'treatment', 'propensity_score', 'ipw_trimmed']].head())
