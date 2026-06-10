# ==============================================================================
# 01_data_cleaning_and_grid.py
# MIMIC-IV 원천 데이터 로드 → 12시간 시계열 격자 생성 → 인과 Lag 설계 → 이상치 제거
# 출력: sip_step1_final.csv
# ==============================================================================

import pandas as pd
import numpy as np
from tqdm import tqdm

# ─────────────────────────────────────────────
# STEP 1. 원천 데이터 로드
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1. 원천 데이터 로드")
print("=" * 60)

df_insulin  = pd.read_csv('insuline_raw.csv',
                          parse_dates=['icu_intime', 'icu_outtime', 'starttime', 'endtime'])
df_creat    = pd.read_csv('creatinine_raw.csv',
                          parse_dates=['charttime'])
df_baseline = pd.read_csv('patient_baseline.csv')
df_fd       = pd.read_csv('fluid_diuretics_raw.csv',
                          parse_dates=['starttime', 'endtime'])

print(f"인슐린 데이터:      {len(df_insulin):>8,} 행")
print(f"크레아티닌 데이터:  {len(df_creat):>8,} 행")
print(f"기저 정보 데이터:   {len(df_baseline):>8,} 행")
print(f"수액/이뇨제 데이터: {len(df_fd):>8,} 행")


# ─────────────────────────────────────────────
# STEP 2. 결측치 제거 및 타입 정리
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2. 결측치 제거 및 타입 정리")
print("=" * 60)

# 입퇴원 시각 및 투여 시각 결측 행 제거
df_insulin = df_insulin.dropna(subset=['icu_intime', 'icu_outtime', 'starttime'])
df_insulin['icu_intime']  = pd.to_datetime(df_insulin['icu_intime'])
df_insulin['icu_outtime'] = pd.to_datetime(df_insulin['icu_outtime'])
df_insulin['starttime']   = pd.to_datetime(df_insulin['starttime'])
df_creat['charttime']     = pd.to_datetime(df_creat['charttime'])
df_fd['starttime']        = pd.to_datetime(df_fd['starttime'])
df_fd['endtime']          = pd.to_datetime(df_fd['endtime'])

unique_stay_ids = df_insulin['stay_id'].unique()
print(f"결측치 제거 후 분석 가능 환자 수: {len(unique_stay_ids):,}명")


# ─────────────────────────────────────────────
# STEP 3. 환자별 12시간 시계열 격자 생성 + 인슐린/크레아티닌 매칭
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3. 12시간 시계열 격자 생성 및 처치·결과 변수 매칭")
print("=" * 60)

processed_frames = []

for stay_id in tqdm(unique_stay_ids, desc="격자 생성 중"):
    p_insulin = df_insulin[df_insulin['stay_id'] == stay_id]
    intime    = p_insulin['icu_intime'].iloc[0]
    outtime   = p_insulin['icu_outtime'].iloc[0]
    p_creat   = df_creat[df_creat['stay_id'] == stay_id]

    # 12시간 격자 생성 (입원 기간이 12시간 미만이면 최소 2스텝 보장)
    time_grid = pd.date_range(start=intime, end=outtime, freq='12h')
    if len(time_grid) < 2:
        time_grid = pd.date_range(start=intime, periods=2, freq='12h')

    p_df = pd.DataFrame({'time_step_end': time_grid})
    p_df['stay_id']   = stay_id
    p_df['time_step'] = range(1, len(p_df) + 1)

    # 처치 변수(X): 12시간 구간 내 인슐린 투여량 합산
    insulin_amounts = []
    for _, row in p_df.iterrows():
        step_end   = row['time_step_end']
        step_start = step_end - pd.Timedelta(hours=12)
        target     = p_insulin[(p_insulin['starttime'] >= step_start) &
                                (p_insulin['starttime'] <  step_end)]
        insulin_amounts.append(target['amount'].sum())
    p_df['insulin_dosage'] = insulin_amounts

    # 결과 변수(Y): 12시간 구간 내 크레아티닌 평균 (없으면 NaN → ffill/bfill)
    creat_values = []
    for _, row in p_df.iterrows():
        step_end   = row['time_step_end']
        step_start = step_end - pd.Timedelta(hours=12)
        target     = p_creat[(p_creat['charttime'] >= step_start) &
                              (p_creat['charttime'] <  step_end)]
        creat_values.append(target['creatinine'].mean() if not target.empty else np.nan)
    p_df['creatinine'] = creat_values
    p_df['creatinine'] = p_df['creatinine'].ffill().bfill()

    processed_frames.append(p_df)

df_master = pd.concat(processed_frames, ignore_index=True)
df_master = df_master[['stay_id', 'time_step', 'time_step_end', 'insulin_dosage', 'creatinine']]
print(f"\n격자 생성 완료: {df_master.shape}")


# ─────────────────────────────────────────────
# STEP 4. 인과 Lag 설계 — Xₜ → Yₜ₊₁ (역인과 제거)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4. 인과 시차(Time-lag) 반영: Xₜ → next_creatinine(t+1)")
print("=" * 60)

# 환자별 그룹 내에서 크레아티닌을 1스텝 앞으로 당김
df_master['next_creatinine'] = df_master.groupby('stay_id')['creatinine'].shift(-1)

# 마지막 타임스텝(next가 없는 행) 제거
df_final = df_master.dropna(subset=['next_creatinine']).copy()
print(f"Lag 반영 후 데이터셋: {df_final.shape}")


# ─────────────────────────────────────────────
# STEP 5. 기저 공변량 결합 (나이, 성별)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5. 기저 공변량 결합 (나이, 성별)")
print("=" * 60)

df_augmented = pd.merge(df_final, df_baseline, on='stay_id', how='left')
df_augmented['gender_male'] = df_augmented['gender'].map({'M': 1, 'F': 0})

# 기저 정보 결측 행 제거
before = len(df_augmented)
df_augmented = df_augmented.dropna(subset=['age', 'gender_male'])
after  = len(df_augmented)
if before != after:
    print(f"⚠️  기저 정보 결측으로 제거된 행: {before - after:,}개")

df_augmented = df_augmented.drop(columns=['gender'])
df_augmented = df_augmented[['stay_id', 'time_step', 'time_step_end',
                              'age', 'gender_male',
                              'insulin_dosage', 'creatinine', 'next_creatinine']]
print(f"기저 공변량 결합 후: {df_augmented.shape}")


# ─────────────────────────────────────────────
# STEP 6. 동적 공변량 결합 (수액 투여량, 이뇨제 사용 여부)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6. 동적 공변량 결합 (수액 투여량, 이뇨제 사용 여부)")
print("=" * 60)

df_master_fd = df_augmented.copy()
df_master_fd['time_step_end'] = pd.to_datetime(df_master_fd['time_step_end'])

fluid_amounts   = []
diuretic_flags  = []
fd_grouped      = df_fd.groupby('stay_id')

for _, row in tqdm(df_master_fd.iterrows(), total=len(df_master_fd), desc="수액/이뇨제 매칭 중"):
    stay_id    = row['stay_id']
    step_end   = row['time_step_end']
    step_start = step_end - pd.Timedelta(hours=12)

    if stay_id in fd_grouped.groups:
        p_fd      = fd_grouped.get_group(stay_id)
        target_fd = p_fd[(p_fd['starttime'] >= step_start) & (p_fd['starttime'] < step_end)]

        if not target_fd.empty:
            fluid_sum    = target_fd[target_fd['category'] == 'fluid']['amount'].sum()
            has_diuretic = 1 if not target_fd[target_fd['category'] == 'diuretic'].empty else 0
            fluid_amounts.append(fluid_sum)
            diuretic_flags.append(has_diuretic)
        else:
            fluid_amounts.append(0.0)
            diuretic_flags.append(0)
    else:
        fluid_amounts.append(0.0)
        diuretic_flags.append(0)

df_master_fd['fluid_input']        = fluid_amounts
df_master_fd['diuretic_infusion']  = diuretic_flags
print(f"동적 공변량 결합 후: {df_master_fd.shape}")


# ─────────────────────────────────────────────
# STEP 7. 임상 가이드라인 기준 이상치 제거
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 7. 임상 가이드라인 기준 이상치 제거")
print("=" * 60)

# 기준: 크레아티닌 (0, 15], 인슐린 [0, 150], 수액 [0, 6000]
before = len(df_master_fd)
df_cleaned = df_master_fd[
    (df_master_fd['creatinine']      >  0) & (df_master_fd['creatinine']      <= 15) &
    (df_master_fd['next_creatinine'] >  0) & (df_master_fd['next_creatinine'] <= 15) &
    (df_master_fd['insulin_dosage']  >= 0) & (df_master_fd['insulin_dosage']  <= 150) &
    (df_master_fd['fluid_input']     >= 0) & (df_master_fd['fluid_input']     <= 6000)
].copy()
after = len(df_cleaned)

print(f"정제 전: {before:,}행  →  정제 후: {after:,}행  (제거: {before - after:,}행)")
print("\n정제 후 기술통계:")
print(df_cleaned[['insulin_dosage', 'creatinine', 'next_creatinine', 'fluid_input']].describe().round(3))


# ─────────────────────────────────────────────
# STEP 8. 저장
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 8. 최종 데이터셋 저장")
print("=" * 60)

df_cleaned.to_csv('sip_step1_final.csv', index=False)
print("✅ 저장 완료: sip_step1_final.csv")
print(f"   최종 셰이프: {df_cleaned.shape}")
print(f"   컬럼: {list(df_cleaned.columns)}")
