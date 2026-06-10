import pandas as pd
import numpy as np

# 데이터 로드
df_insulin = pd.read_csv('insuline_raw.csv', parse_dates=['icu_intime', 'icu_outtime', 'starttime', 'endtime'])
df_creat = pd.read_csv('creatinine_raw.csv', parse_dates=['charttime'])

print(f"인슐린 데이터 행 수: {len(df_insulin)}")
print(f"크레아티닌 데이터 행 수: {len(df_creat)}")

# ──────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np
from tqdm import tqdm  # 진행 상황을 보기 위한 라이브러리

# [수정 추가] 입퇴원 시각 및 투여 시각에 결측치가 있는 행을 제거합니다.
df_insulin = df_insulin.dropna(subset=['icu_intime', 'icu_outtime', 'starttime'])

# 정상적으로 datetime 타입으로 변환되었는지 재확인 (혹시 모를 문자열 타입 방지)
df_insulin['icu_intime'] = pd.to_datetime(df_insulin['icu_intime'])
df_insulin['icu_outtime'] = pd.to_datetime(df_insulin['icu_outtime'])
df_insulin['starttime'] = pd.to_datetime(df_insulin['starttime'])

df_creat['charttime'] = pd.to_datetime(df_creat['charttime'])

# 결측치가 제거된 안전한 stay_id 리스트만 다시 추출
unique_stay_ids = df_insulin['stay_id'].unique()

print(f"결측치 제거 후 분석 가능한 총 환자 수: {len(unique_stay_ids)}명")

# 1. 빈 리스트 생성 (최종 결과를 담을 그릇)
processed_frames = []

# 2. 고유한 stay_id 리스트 추출
unique_stay_ids = df_insulin['stay_id'].unique()

print("환자별 12시간 단위 시계열 격자 생성 및 데이터 병합 시작...")

for stay_id in tqdm(unique_stay_ids):
    # 해당 환자의 인슐린 및 기본 입퇴원 시간 추출
    p_insulin = df_insulin[df_insulin['stay_id'] == stay_id]
    intime = p_insulin['icu_intime'].iloc[0]
    outtime = p_insulin['icu_outtime'].iloc[0]

    # 해당 환자의 크레아티닌 데이터 추출
    p_creat = df_creat[df_creat['stay_id'] == stay_id]

    # [핵심] 입원시점부터 퇴원시점까지 12시간 간격의 시간 격자(Timestamp) 생성
    time_grid = pd.date_range(start=intime, end=outtime, freq='12h')

    # 만약 입원 기간이 12시간 미만이라 격자가 안 만들어지면 최소 2개의 스텝은 생성
    if len(time_grid) < 2:
        time_grid = pd.date_range(start=intime, periods=2, freq='12h')

    # 환자별 기본 시계열 데이터프레임 틀 만들기
    p_df = pd.DataFrame({'time_step_end': time_grid})
    p_df['stay_id'] = stay_id
    p_df['time_step'] = range(1, len(p_df) + 1)

    # --- 처치 변수(X) 인슐린 매칭 ---
    # 각 12시간 구간에 포함되는 인슐린 투여량의 총합 계산
    insulin_amounts = []
    for i, row in p_df.iterrows():
        step_end = row['time_step_end']
        step_start = step_end - pd.Timedelta(hours=12)

        # 인슐린의 starttime이 해당 12시간 구간 안에 들어오는 경우의 amount 합산
        # (더 정밀하게는 구간 오버랩을 계산할 수 있으나, 첫 파이프라인은 시작 시점 기준으로 단순화)
        target_insulin = p_insulin[(p_insulin['starttime'] >= step_start) & (p_insulin['starttime'] < step_end)]
        insulin_amounts.append(target_insulin['amount'].sum())

    p_df['insulin_dosage'] = insulin_amounts

    # --- 결과 변수(Y) 크레아티닌 매칭 ---
    creat_values = []
    for i, row in p_df.iterrows():
        step_end = row['time_step_end']
        step_start = step_end - pd.Timedelta(hours=12)

        target_creat = p_creat[(p_creat['charttime'] >= step_start) & (p_creat['charttime'] < step_end)]
        if not target_creat.empty:
            creat_values.append(target_creat['creatinine'].mean())
        else:
            creat_values.append(np.nan)

    p_df['creatinine'] = creat_values

    # 크레아티닌 빈칸 채우기 (Forward-fill: 직전 수치 유지, 만약 첫 칸이 비면 후속 값으로 bfill)
    p_df['creatinine'] = p_df['creatinine'].ffill().bfill()

    processed_frames.append(p_df)

# 3. 모든 환자의 데이터프레임 하나로 통합
df_master = pd.concat(processed_frames, ignore_index=True)

# 4. 컬럼 순서 정돈
df_master = df_master[['stay_id', 'time_step', 'time_step_end', 'insulin_dosage', 'creatinine']]
print("\n병합 완료!")
print(f"최종 마스터 데이터프레임 셰이프: {df_master.shape}")

# ──────────────────────────────────────────────────────────────────────────────

print(df_master.head(10))

# ──────────────────────────────────────────────────────────────────────────────

# 환자별로 그룹을 묶은 뒤, 크레아티닌 수치를 한 칸씩 위로 당깁니다. (즉, 현재 인슐린 -> 다음 스텝의 크레아티닌)
# t 시점의 처치에 대한 결과물로 t+1 시점의 수치를 매칭하는 과정입니다.
df_master['next_creatinine'] = df_master.groupby('stay_id')['creatinine'].shift(-1)

# 마지막 타임스텝은 '다음 스텝의 결과'가 존재하지 않으므로 결측치(NaN)가 됩니다.
# 인과 추론 지도학습을 위해 이 결측치가 생긴 행들을 제거합니다.
df_final = df_master.dropna(subset=['next_creatinine']).copy()

print("인과적 시차(Time-lag) 반영 완료!")
print(f"필터링 후 최종 데이터셋 셰이프: {df_final.shape}")

# 상위 10개 행 확인
print(df_final.head(10))

# ──────────────────────────────────────────────────────────────────────────────

# 다음 단계에서 바로 불러올 수 있도록 최종 정렬된 데이터를 CSV로 저장합니다.
df_final.to_csv('sip_step1_cleansed_data.csv', index=False)
print("저장 완료!")

# ──────────────────────────────────────────────────────────────────────────────

# 1. 기저 정보 데이터 로드
df_baseline = pd.read_csv('patient_baseline.csv')

# 2. 기존 시계열 데이터프레임(df_final)과 stay_id 기준으로 결합 (Left Join)
df_augmented = pd.merge(df_final, df_baseline, on='stay_id', how='left')

# 3. 범주형 변수(Gender) 수치화 (M -> 1, F -> 0)
df_augmented['gender_male'] = df_augmented['gender'].map({'M': 1, 'F': 0})

# 결측치가 있거나 매칭이 안 된 행이 있는지 최종 확인
if df_augmented['age'].isnull().any() or df_augmented['gender_male'].isnull().any():
    print("경고: 일부 환자의 기저 정보에 결측치가 존재합니다. 결측치를 제거합니다.")
    df_augmented = df_augmented.dropna(subset=['age', 'gender_male'])

# 불필요해진 기존 문자열 gender 컬럼 제거 및 순서 정돈
df_augmented = df_augmented.drop(columns=['gender'])
df_augmented = df_augmented[['stay_id', 'time_step', 'time_step_end', 'age', 'gender_male', 'insulin_dosage', 'creatinine', 'next_creatinine']]

print("기저 공변량 결합 및 인코딩 완료!")
print(f"새로운 데이터셋 셰이프: {df_augmented.shape}")

# 상위 5개 행으로 확인
print(df_augmented.head())

# ──────────────────────────────────────────────────────────────────────────────

df_fd = pd.read_csv('fluid_diuretics_raw.csv', parse_dates=['starttime', 'endtime'])
print(f"수액/이뇨제 데이터 행 수: {len(df_fd)}")

# ──────────────────────────────────────────────────────────────────────────────

# 0. 데이터프레임 시간 타입 변환 및 준비
df_fd['starttime'] = pd.to_datetime(df_fd['starttime'])
df_fd['endtime'] = pd.to_datetime(df_fd['endtime'])

# 기존 증강 데이터프레임 복사 및 시간 타입 재확인
df_master_fd = df_augmented.copy()
df_master_fd['time_step_end'] = pd.to_datetime(df_master_fd['time_step_end'])

print("수액 및 이뇨제 시계열 격자 병합 시작 (약 1~2분 소요)...")

fluid_amounts = []
diuretic_flags = []

# stay_id 단위로 그룹화하여 탐색 속도 최적화
fd_grouped = df_fd.groupby('stay_id')

for idx, row in tqdm(df_master_fd.iterrows(), total=len(df_master_fd)):
    stay_id = row['stay_id']
    step_end = row['time_step_end']
    step_start = step_end - pd.Timedelta(hours=12)

    # 해당 환자의 수액/이뇨제 기록이 있는지 확인
    if stay_id in fd_grouped.groups:
        p_fd = fd_grouped.get_group(stay_id)

        # 주입 시작 시간(starttime)이 해당 12시간 구간에 포함되는 기록 필터링
        target_fd = p_fd[(p_fd['starttime'] >= step_start) & (p_fd['starttime'] < step_end)]

        if not target_fd.empty:
            # 1) 수액 총량 계산
            fluid_sum = target_fd[target_fd['category'] == 'fluid']['amount'].sum()
            fluid_amounts.append(fluid_sum)

            # 2) 이뇨제 투여 여부 플래그 (있으면 1, 없으면 0)
            has_diuretic = 1 if not target_fd[target_fd['category'] == 'diuretic'].empty else 0
            diuretic_flags.append(has_diuretic)
        else:
            fluid_amounts.append(0.0)
            diuretic_flags.append(0)
    else:
        fluid_amounts.append(0.0)
        diuretic_flags.append(0)

# 최종 컬럼 추가
df_master_fd['fluid_input'] = fluid_amounts
df_master_fd['diuretic_infusion'] = diuretic_flags

print("\n모든 동적 공변량 병합 완료!")
print(f"최종 전처리 데이터셋 셰이프: {df_master_fd.shape}")

# 상위 5개 행 확인
print(df_master_fd.head())

# ──────────────────────────────────────────────────────────────────────────────

# 최종 증강된 마스터 데이터셋을 CSV로 저장
df_master_fd.to_csv('sip_step2_augmented_data.csv', index=False)
print("Step 2 최종 데이터셋 저장 완료!")
