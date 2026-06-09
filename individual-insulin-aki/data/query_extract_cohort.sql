-- ==============================================================================
-- query_extract_cohort.sql (Version 2.0 - Fully Controlled Clinical Cohort)
-- MIMIC-IV 데이터베이스 기반 제2형 당뇨 환자의 인슐린 투여 및 AKI 유발 요인 추출
-- ==============================================================================

WITH icu_base AS (
    -- 1. 성인 환자(18세 이상) 중 최초 입원(First Admission) 데이터만 추출 (재입원으로 인한 기저 상태 교란 차단)
    SELECT 
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime,
        ie.outtime,
        pa.gender,
        pa.anchor_age AS age,
        ROW_NUMBER() OVER (PARTITION BY ie.subject_id ORDER BY ie.intime) as admission_seq
    FROM mimiciv_icu.icustays ie
    INNER JOIN mimiciv_hosp.patients pa
        ON ie.subject_id = pa.subject_id
    WHERE pa.anchor_age >= 18
),

diabetic_cohort AS (
    -- 2. ICD-10 진단 코드 기반 제2형 당뇨병(T2DM) 환자만 정밀 필터링 (E11 계열 코드)
    SELECT DISTINCT 
        ib.stay_id,
        ib.hadm_id,
        ib.age,
        ib.gender,
        ib.intime,
        ib.outtime
    FROM icu_base ib
    INNER JOIN mimiciv_hosp.diagnoses_icd diag
        ON ib.hadm_id = diag.hadm_id
    WHERE ib.admission_seq = 1 -- 첫 번째 입원만 포함
      AND (diag.icd_code LIKE 'E11%' OR diag.icd_code LIKE '250%') -- ICD-10 및 ICD-9 당뇨 코드 매칭
),

insulin_treatment AS (
    -- 3. ICU 입원 기간 중 투여된 연속성/간헐적 인슐린(처치 변수) 용량 및 시점 추출
    SELECT 
        stay_id,
        charttime,
        SUM(amount) AS insulin_dosage
    FROM mimiciv_icu.inputevents
    WHERE itemid IN (
        225152, -- Insulin - Regular
        225153, -- Insulin - Glargine
        225155, -- Insulin - Humalog
        223258  -- Insulin - Infusion
    ) AND amount > 0
    GROUP BY stay_id, charttime
),

fluid_intake AS (
    -- 4. 신장 여과 기능에 직접적인 교란을 주는 주입된 총 수액량(Fluid Input) 추출
    SELECT 
        stay_id,
        charttime,
        SUM(amount) AS fluid_input
    FROM mimiciv_icu.inputevents
    WHERE itemid IN (
        225158, -- NaCl 0.9%
        225828, -- Dextrose 5%
        225943  -- Sterile Water
    ) AND amount > 0
    GROUP BY stay_id, charttime
),

diuretic_treatment AS (
    -- 5. 크레아티닌 배설 및 체액량에 강한 영향을 주는 이뇨제(Diuretics) 투여 여부 마킹
    SELECT DISTINCT
        stay_id,
        charttime,
        1 AS diuretic_infusion
    FROM mimiciv_icu.inputevents
    WHERE itemid IN (
        221794, -- Furosemide (Lasix)
        228340  -- Bumetanide (Bumex)
    ) AND amount > 0
),

creatinine_labs AS (
    -- 6. 혈청 크레아티닌(결과 변수) 수치 추출
    SELECT 
        hadm_id,
        charttime,
        valuenum AS creatinine
    FROM mimiciv_hosp.labevents
    WHERE itemid = 50912 -- Serum Creatinine
        AND valuenum IS NOT NULL 
),

timeline_anchor AS (
    -- 7. 모든 의료 행위(검사, 처방, 처치)의 시점을 타임라인 기준으로 통합 유니온
    SELECT stay_id, charttime FROM insulin_treatment
    UNION DISTINCT
    SELECT stay_id, charttime FROM fluid_intake
    UNION DISTINCT
    SELECT stay_id, charttime FROM diuretic_treatment
    UNION DISTINCT
    -- Lab 데이터는 hadm_id 기준이므로 stay_id와 매칭하기 위해 코호트 테이블 참조 조인 시점 통합
    SELECT dc.stay_id, cl.charttime FROM creatinine_labs cl 
    INNER JOIN diabetic_cohort dc ON cl.hadm_id = dc.hadm_id
)

-- 8. 최종 타임라인 메인 쿼리 빌드 및 공변량 바인딩
SELECT 
    ta.stay_id,
    ta.charttime,
    dc.age,
    CASE WHEN dc.gender = 'M' THEN 1 ELSE 0 END AS gender_male,
    COALESCE(ins.insulin_dosage, 0) AS insulin_dosage,
    COALESCE(fl.fluid_input, 0) AS fluid_input,
    COALESCE(di.diuretic_infusion, 0) AS diuretic_infusion,
    lab.creatinine
FROM timeline_anchor ta
INNER JOIN diabetic_cohort dc 
    ON ta.stay_id = dc.stay_id
LEFT JOIN insulin_treatment ins 
    ON ta.stay_id = ins.stay_id AND ta.charttime = ins.charttime
LEFT JOIN fluid_intake fl 
    ON ta.stay_id = fl.stay_id AND ta.charttime = fl.charttime
LEFT JOIN diuretic_treatment di 
    ON ta.stay_id = di.stay_id AND ta.charttime = di.charttime
LEFT JOIN creatinine_labs lab 
    ON dc.hadm_id = lab.hadm_id AND ta.charttime = lab.charttime
WHERE ta.charttime BETWEEN dc.intime AND dc.outtime -- ICU 입원 기간 내의 기록만 한정
ORDER BY ta.stay_id, ta.charttime;
