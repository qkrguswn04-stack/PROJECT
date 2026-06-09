WITH icu_cohort AS (
    -- 1. 중환자실(ICU) 입원 환자 중 기본 성인 코호트 정의
    SELECT 
        ie.subject_id,
        ie.hadm_id,
        ie.stay_id,
        ie.intime,
        ie.outtime,
        pa.gender,
        pa.anchor_age AS age
    FROM mimiciv_icu.icustays ie
    INNER JOIN mimiciv_hosp.patients pa
        ON ie.subject_id = pa.subject_id
    WHERE pa.anchor_age >= 18
),

insulin_treatment AS (
    -- 2. ICU 입원 기간 중 투여된 인슐린(처치 변수) 용량 및 시점 추출
    SELECT 
        stay_id,
        charttime,
        amount AS insulin_dosage
    FROM mimiciv_icu.inputevents
    WHERE itemid IN (
        225152, -- Insulin - Regular (정규 인슐린)
        225153  -- Insulin - Glargine (장기 지속형 인슐린)
    ) AND amount > 0
),

creatinine_labs AS (
    -- 3. 환자의 혈청 크레아티닌(타깃/결과 변수) 검사 수치 및 시점 추출
    SELECT 
        hadm_id,
        charttime,
        valuenum AS creatinine
    FROM mimiciv_hosp.labevents
    WHERE itemid = 50912 -- Serum Creatinine ItemID
        AND valuenum IS NOT NULL 
        AND valuenum < 150 -- 극단적 기입 오류 1차 필터링
)

-- 4. 최종 타임라인 기준 변수 동적 결합
SELECT 
    co.stay_id,
    COALESCE(ins.charttime, lab.charttime) AS charttime,
    co.age,
    CASE WHEN co.gender = 'M' THEN 1 ELSE 0 END AS gender_male,
    COALESCE(ins.insulin_dosage, 0) AS insulin_dosage,
    lab.creatinine
FROM icu_cohort co
LEFT JOIN insulin_treatment ins 
    ON co.stay_id = ins.stay_id
LEFT JOIN creatinine_labs lab 
    ON co.hadm_id = lab.hadm_id 
    AND COALESCE(ins.charttime, lab.charttime) BETWEEN co.intime AND co.outtime
ORDER BY co.stay_id, charttime;
