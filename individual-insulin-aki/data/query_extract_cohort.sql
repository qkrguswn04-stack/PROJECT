-- ==============================================================================
-- query_extract_cohort.sql
-- MIMIC-IV 데이터베이스 기반 제2형 당뇨 ICU 환자 코호트 추출
-- 출력: insuline_raw.csv / creatinine_raw.csv / patient_baseline.csv / fluid_diuretics_raw.csv
-- ==============================================================================


-- ==============================================================================
-- [사전 확인] itemid 조회 (실행 후 확인용, 파이프라인 실행 시 제외)
-- ==============================================================================

-- 인슐린 관련 itemid 확인
SELECT *
FROM mimiciv_icu.d_items di
WHERE lower(label) LIKE '%insulin%';

-- 크레아티닌 관련 itemid 확인
SELECT *
FROM mimiciv_icu.d_items di
WHERE lower(label) LIKE '%creatinine%';


-- ==============================================================================
-- [공통 CTE] 코호트 기반 정의 (하단 4개 추출 쿼리에서 공통 사용)
-- 조건: T2DM 진단(ICD-9/10) + 첫 ICU 입원 + 인슐린(itemid=223258) 투여 이력 존재
-- ==============================================================================

-- ※ 아래 WITH 블록은 각 추출 쿼리마다 반복 사용됩니다.
--   t2dm_patients  : ICD 코드 기반 T2DM 환자 필터링
--   icu_cohort     : 첫 ICU 입원(rn=1) 기준 추출
--   final_cohort   : 인슐린 투여 이력이 있는 최종 코호트


-- ==============================================================================
-- QUERY 1. 인슐린 투여 데이터 추출 → insuline_raw.csv
-- 컬럼: stay_id, icu_intime, icu_outtime, starttime, endtime, amount
-- ==============================================================================

WITH t2dm_patients AS (
    SELECT DISTINCT subject_id, hadm_id
    FROM mimiciv_hosp.diagnoses_icd
    WHERE (icd_version = 10 AND icd_code LIKE 'E11%')
       OR (icd_version = 9  AND icd_code LIKE '250%')
),
icu_cohort AS (
    SELECT
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime  AS icu_intime,
        ie.outtime AS icu_outtime,
        ROW_NUMBER() OVER (PARTITION BY ie.hadm_id ORDER BY ie.intime) AS rn
    FROM mimiciv_icu.icustays ie
    INNER JOIN t2dm_patients p ON ie.hadm_id = p.hadm_id
),
final_cohort AS (
    SELECT DISTINCT c.stay_id, c.icu_intime, c.icu_outtime
    FROM icu_cohort c
    INNER JOIN mimiciv_icu.inputevents t ON c.stay_id = t.stay_id
    WHERE c.rn = 1
      AND t.itemid = 223258  -- Insulin - Infusion
      AND t.amount > 0
)
SELECT
    f.stay_id,
    f.icu_intime,
    f.icu_outtime,
    i.starttime,
    i.endtime,
    i.amount
FROM final_cohort f
INNER JOIN mimiciv_icu.inputevents i ON f.stay_id = i.stay_id
WHERE i.itemid = 223258
  AND i.amount > 0
ORDER BY f.stay_id, i.starttime;


-- ==============================================================================
-- QUERY 2. 크레아티닌 측정 데이터 추출 → creatinine_raw.csv
-- 컬럼: stay_id, charttime, creatinine
-- ※ chartevents(itemid=220615) 기준 추출
-- ※ 시차(Lag) 설계는 Python 파이프라인(01_data_cleaning_and_grid.py)에서 수행
--    Xₜ(인슐린) → Yₜ₊₁(차기 크레아티닌) 매핑은 pandas shift(-1)로 처리
-- ==============================================================================

WITH t2dm_patients AS (
    SELECT DISTINCT subject_id, hadm_id
    FROM mimiciv_hosp.diagnoses_icd
    WHERE (icd_version = 10 AND icd_code LIKE 'E11%')
       OR (icd_version = 9  AND icd_code LIKE '250%')
),
icu_cohort AS (
    SELECT
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime  AS icu_intime,
        ie.outtime AS icu_outtime,
        ROW_NUMBER() OVER (PARTITION BY ie.hadm_id ORDER BY ie.intime) AS rn
    FROM mimiciv_icu.icustays ie
    INNER JOIN t2dm_patients p ON ie.hadm_id = p.hadm_id
),
final_cohort AS (
    SELECT DISTINCT c.stay_id
    FROM icu_cohort c
    INNER JOIN mimiciv_icu.inputevents t ON c.stay_id = t.stay_id
    WHERE c.rn = 1
      AND t.itemid = 223258
      AND t.amount > 0
)
SELECT
    f.stay_id,
    c.charttime,
    c.valuenum AS creatinine
FROM final_cohort f
INNER JOIN mimiciv_icu.chartevents c ON f.stay_id = c.stay_id
WHERE c.itemid = 220615        -- Creatinine (serum)
  AND c.valuenum IS NOT NULL
ORDER BY f.stay_id, c.charttime;


-- ==============================================================================
-- QUERY 3. 환자 기저 정보 추출 → patient_baseline.csv
-- 컬럼: stay_id, gender, age
-- ※ age = ICU 첫 입원 연도 기준으로 anchor_year/anchor_age 보정하여 계산
-- ==============================================================================

WITH t2dm_patients AS (
    SELECT DISTINCT subject_id, hadm_id
    FROM mimiciv_hosp.diagnoses_icd
    WHERE (icd_version = 10 AND icd_code LIKE 'E11%')
       OR (icd_version = 9  AND icd_code LIKE '250%')
),
icu_cohort AS (
    SELECT
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime AS icu_intime,
        ROW_NUMBER() OVER (PARTITION BY ie.hadm_id ORDER BY ie.intime) AS rn
    FROM mimiciv_icu.icustays ie
    INNER JOIN t2dm_patients p ON ie.hadm_id = p.hadm_id
),
final_cohort AS (
    SELECT DISTINCT c.stay_id, c.subject_id, c.icu_intime
    FROM icu_cohort c
    INNER JOIN mimiciv_icu.inputevents t ON c.stay_id = t.stay_id
    WHERE c.rn = 1
      AND t.itemid = 223258
      AND t.amount > 0
)
SELECT
    f.stay_id,
    p.gender,
    (EXTRACT(YEAR FROM f.icu_intime) - p.anchor_year + p.anchor_age) AS age
FROM final_cohort f
INNER JOIN mimiciv_hosp.patients p ON f.subject_id = p.subject_id;


-- ==============================================================================
-- QUERY 4. 수액 및 이뇨제 투여 데이터 추출 → fluid_diuretics_raw.csv
-- 컬럼: stay_id, starttime, endtime, category, amount
-- category: 'fluid' (수액) / 'diuretic' (이뇨제)
-- ==============================================================================

WITH t2dm_patients AS (
    SELECT DISTINCT subject_id, hadm_id
    FROM mimiciv_hosp.diagnoses_icd
    WHERE (icd_version = 10 AND icd_code LIKE 'E11%')
       OR (icd_version = 9  AND icd_code LIKE '250%')
),
icu_cohort AS (
    SELECT
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime,
        ROW_NUMBER() OVER (PARTITION BY ie.hadm_id ORDER BY ie.intime) AS rn
    FROM mimiciv_icu.icustays ie
    INNER JOIN t2dm_patients p ON ie.hadm_id = p.hadm_id
),
final_cohort AS (
    SELECT DISTINCT c.stay_id
    FROM icu_cohort c
    INNER JOIN mimiciv_icu.inputevents t ON c.stay_id = t.stay_id
    WHERE c.rn = 1
      AND t.itemid = 223258
      AND t.amount > 0
)
SELECT
    f.stay_id,
    i.starttime,
    i.endtime,
    CASE
        WHEN i.itemid IN (220949, 221154, 225158, 225828, 225943) THEN 'fluid'
        WHEN i.itemid IN (221794, 228340)                         THEN 'diuretic'
    END AS category,
    i.amount
FROM final_cohort f
INNER JOIN mimiciv_icu.inputevents i ON f.stay_id = i.stay_id
WHERE i.itemid IN (
    220949, 221154, 225158, 225828, 225943,  -- 수액: NaCl, Dextrose 등
    221794, 228340                            -- 이뇨제: Furosemide, Bumetanide
)
  AND i.amount > 0
ORDER BY f.stay_id, i.starttime;
