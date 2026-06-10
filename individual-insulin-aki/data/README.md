## 📊 Data Access & Cohort Extraction Guide

본 프로젝트에서 사용한 데이터는 미국 MIT의 **MIMIC-IV(Medical Information Mart for Intensive Care v2.2)** 비식별화 중환자 데이터베이스입니다. 
PhysioNet의 데이터 보호 정책에 따라 실제 데이터셋(CSV)은 저장소에 업로드하지 않으며, 동일한 환경을 재현할 수 있는 **추출 쿼리 및 데이터 명세**를 공유합니다.


### 🔍 코호트 정의 및 데이터 추출 조건
* **대상 환자군**: MIMIC-IV 데이터베이스 내 18세 이상의 성인 제2형 당뇨병(T2DM) 중환자 고호트.
* **추출 소스 테이블**:
  * `mimiciv_icu.icustays`, `mimiciv_hosp.patients` (인구통계학적 특성 및 입원 정보)
  * `mimiciv_icu.inputevents` (인슐린 주입 용량 및 시점)
  * `mimiciv_hosp.labevents` (혈청 크레아티닌 검사 결과)


### 📋 추출 피처 명세 (Data Dictionary)
| 변수명 (Column) | 데이터 타입 | 설명 (Description) |
| :--- | :--- | :--- |
| `stay_id` | Integer | 중환자실(ICU) 고유 입원 번호 (Key) |
| `charttime` | DateTime | 의료 행위 및 검사가 기록된 타임스탬프 |
| `age` | Integer | 환자의 입원 당시 나이 (기저 공변량) |
| `gender_male` | Binary | 환자의 생물학적 성별 (Male=1, Female=0) |
| `insulin_dosage` | Float | 12시간 구간 내 연속 정맥 주입 인슐린(Insulin - Infusion, itemid=223258) |
| `creatinine` | Float | 혈청 크레아티닌 수치 (mg/dL) (결과 변수) |


### 🚀 재현 방법 (How to Reproduce)
1. [PhysioNet](https://physionet.org/)에서 MIMIC-IV 데이터 접근 권한을 취득합니다.
2. Google BigQuery 또는 로컬 PostgreSQL에 데이터베이스를 구축합니다.
3. 본 폴더에 첨부된 `query_extract_cohort.sql` 스크립트를 실행하여 원천 데이터를 CSV 형태로 다운로드한 후, `/notebooks` 파이프라인의 입력값으로 활용합니다.
