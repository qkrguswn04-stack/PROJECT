# 🚀 Advanced Data Science & Causal Inference Portfolio Hub

본 저장소는 머신러닝 알고리즘과 통계학적 **인과 추론(Causal Inference)** 방법론을 융합하여, 현실의 복잡한 의료 도메인 문제 및 데이터 파이프라인의 한계를 돌파한 4개의 프로젝트(개인 2, 팀 2)를 모아둔 포트폴리오 아카이브입니다.

---

## 📂 프로젝트 디렉토리 안내 (Directory Index)

### 👤 개인 프로젝트 (Individual Projects)

#### 1. `individual-insulin-aki/` — 인과 추론 기반 인슐린 투여량별 신장 기능 변화 예측 시뮬레이터 (CDSS)
* **Core Tech**: MIMIC-IV v2.2, PostgreSQL, Inverse Propensity Weighting (IPW), XGBoost, Streamlit
* **Key Challenge**: 중환자실(ICU) 관측 데이터 특성상 발생하는 의사의 중증도별 처방 편향(Confounding by Indication)으로 인해, 일반 ML 모델이 인슐린의 순수한 치료 효과를 왜곡·과소평가하는 문제 직면.
* **Data**: MIMIC-IV v2.2 기반 T2DM ICU 환자 코호트. ICD-9/10(E11%, 250%) 진단 코드 + 인슐린(itemid=223258) 투여 이력 기준 필터링. 인슐린·크레아티닌·수액·이뇨제·기저 공변량(나이·성별) 총 4개 테이블 추출.
* **Pipeline**:
  * **01 데이터 전처리**: 12시간 격자(Time Grid) 기반 시계열 재구성. 인과 시차(Time-lag) 설계 적용 — Xₜ(인슐린 투여량) → Yₜ₊₁(차기 크레아티닌) 매핑으로 역인과(Reverse Causality) 원천 차단. 임상 가이드라인 기준 이상치 제거(크레아티닌 ≤15, 인슐린 ≤150, 수액 ≤6000).
  * **02 인과 편향 제거**: 로지스틱 회귀 기반 성향 점수(Propensity Score) 산출 후 역성향 점수 가중치(IPW) 적용. 상위 99% Trimming으로 가중치 폭발 방지. Pseudo-RCT 환경 수학적 구축.
  * **03 인과 모델 학습 및 검증**: IPW를 `sample_weight`로 주입한 XGBoost 학습(MAE 0.1654, R² 0.9408). 플라시보 강건성 검증(Placebo Treatment Refuter) — 인슐린 처치 변수 셔플 후 반사실 곡선 평탄화 확인으로 인과 경로의 통계적 유효성 방어.
* **Key Results**:
  * IPW 적용 후 `insulin_dosage` 변수 중요도 **35.6% 상승** — 중증도 편향에 가려진 순수 인과 신호 복원 성공.
  * 플라시보 검증 **PASS** — 셔플된 처치 변수에서 반사실 곡선 평탄화 확인.
  * 의사가 가상 처치 용량을 실시간으로 조절하며 차기 신장 수치 변화를 시뮬레이션하는 **What-if CDSS 프로토타입(Streamlit)** 구현.

#### 2. `individual-fcs-preprocessing/` — FCS 유세포 분석 데이터 전처리 프로그램 개발

**Role**: Data Engineer / Software Developer (개인 프로젝트, 100% 담당)

**Core Tech**: Python, FlowPy/FCSPly, Pandas, NumPy, Automated Gating, Outlier Detection, High-throughput Data Pipeline

**Key Challenge**: 
대용량 FCS(Flow Cytometry Standard) 바이너리 파일 구조의 특성상 수동 게이팅(Gating)과 전처리에 막대한 시간과 연구자 편향이 개입되는 병목 현상 발생. 유세포 분석 실험 후 수백 개 이상의 FCS 파일을 처리할 때 자동화된 파이프라인 부재로 인한 생산성 저하.

**Data**: 
유세포 분석 실험 데이터 (다양한 세포 마커). FCS 3.0 파일 포맷. 멀티 파라미터 유세포(Multi-parameter Flow Cytometry) 원본 데이터.

**Pipeline**:

1. **FCS 파일 로드**
   - FlowPy/FCSPly를 이용한 바이너리 FCS 파일 읽기
   - 파일 메타데이터 추출 및 검증
   - 게이팅 이력(Gating History) 자동 인식

2. **데이터 정제 및 노이즈 필터링**
   - Outlier Detection: Isolation Forest, Local Outlier Factor (LOF) 적용
   - Dead Cell / Debris 자동 제거
   - 강도(Intensity) 기반 노이즈 제거

3. **다차원 특성 추출**
   - Compensation Matrix 자동 적용
   - 로그 변환(Log Transformation) 표준화
   - 다중 마커 조합 특성 생성

4. **배치 처리 및 파이프라인 자동화**
   - 폴더 내 다중 FCS 파일 배치 처리
   - 병렬 처리(Multiprocessing)로 속도 최적화
   - 정제된 데이터 CSV/HDF5 형식 자동 저장

**Key Results**:

- **처리 속도**: 수작업 게이팅 대비 **시간 소요 시간 90% 단축** (파일당 30분 → 3분)
- **일관성 개선**: 연구자 편향 제거로 재현성(Reproducibility) **99.5% 달성**
- **하이쓰루풋 환경 구축**: 한 번의 배치 실행으로 100+ FCS 파일 자동 처리 가능
- **생산성 증대**: 대규모 유세포 실험의 데이터 정제 병목 현상 해소

---

### 👥 팀 프로젝트 (Team Projects)

#### 3. `OVA-LINK/` — 난소암 조기진단 AI 기반 의료진 의사결정 지원 시스템 (CDSS)

**Role**: Project Manager / AI Lead (초음파 AI 모델 100% 개발, 기여도 40% 이상)

**Core Tech**: Next.js, FastAPI, PostgreSQL, PyTorch, YOLOv8n, RT-DETR, DenseNet121, Swin Transformer, XGBoost, DICOM (Orthanc PACS)

**Key Challenge**: 
난소암은 부인암 중 사망률 1위이나, 환자 70%가 3기 이상에서 진단됨. 초기 비특이적 증상으로 인한 진단 지연이 문제. 1차 병원의 초음파 기기와 혈액검사만으로는 의료진의 경험과 직감에 의존한 진단만 가능했음. 초음파 이미지 분석의 도메인 특수성(스펙클 노이즈, 불명확한 경계)을 극복하고, 1차 병원에서도 신뢰할 수 있는 조기 진단 시스템 필요.

**Data**: 
- MMOTU (1,639장, 공개) → AI-HUB (15,694장, 폐쇄망 학습)
- MIMIC-IV 임상 데이터 기반 혈액검사 분석
- 팀 공용 PostgreSQL DB (192.168.0.33)

**Pipeline**:

1. **초음파 AI 탐지 모델 (Detection)**
   - 모델: YOLOv8n + RT-DETR WBF 앙상블
   - 개발 전략: 5가지 모델 비교 후 최적 선택
     - 베이스라인 (YOLOv8n): mAP50 28.8%
     - AI-HUB Fine-tuning: mAP50 50.0% (+21.2%p)
     - SAMUS: Recall ~97% (Data Leakage)
     - Curriculum Learning: mAP50 47.7%
     - **최종 앙상블: Recall 95.47%, F1 0.9004**
   - 선택 이유: 초기 암 진단에서 종양 미탐지는 치명적 → Recall 최우선

2. **초음파 AI 분류 모델 (Classification)**
   - 모델: DenseNet121 + Swin Transformer Early-fusion
   - 개발 전략: 8가지 모델 비교 후 CNN+Transformer 상호보완 구조 선택
     - EfficientNet-B4: AUC 0.8693
     - ResNet-50: AUC 0.8807
     - USF-MAE: AUC 0.8791
     - DenseNet-121: AUC 0.8928
     - Swin 단독: AUC 0.9142
     - **최종 DenseNet+Swin: AUC 0.8932, Sensitivity 74.31%**
   - 성능: AUC 0.9553, Sensitivity 82.76% (조기), 80.27% (진행)
   - 계층적 파이프라인: 양성/악성 판정 → FIGO Stage 분류 → 서브타입 분류

3. **혈액검사 분석**
   - XGBoost 기반 위험도 예측
   - TyG Index 등 신규 바이오마커 분석 (팀원 송대영 담당)
   - PR-AUC: 0.9784

4. **CDSS 통합 및 제품화**
   - FastAPI 백엔드: AI 모델 오케스트레이션, PACS 연동, RMI 점수 계산
   - Next.js 프론트엔드: 의료진 실시간 의사결정 지원 인터페이스
   - PostgreSQL: 환자 데이터 및 분석 결과 저장

**Key Results**:

- **탐지 모델**: Recall 95.47%, F1 Score 0.9004 (초기 암 미탐지 최소화)
- **분류 모델**: AUC 0.9553, Sensitivity 82.76% (조기), 80.27% (진행)
- **도메인 가중치의 가치 입증**: MMOTU 1,639장 (Recall 22.9%) → AI-HUB 도메인 가중치 + fine-tuning (Recall 47.2%, +24.3%p). 데이터 규모보다 도메인 지식이 담긴 가중치의 중요성 실증.
- **폐쇄망 환경 개발 역량**: AI-HUB 폐쇄망 내에서 외부 인터넷 없이 경로·버전·의존성 관리하며 모델 재적응. 에러 분석 및 논리적 디버깅 능력 강화.
- **팀 협업 체계화**: Notion 워크스페이스로 일일 업무일지, 연구 보고서, 성과 추적. PM으로서 기한 내 목표 달성 및 팀원 함께 성장.
- **의료 윤리 준수**: IRB 신청서 및 연구계획서 작성을 통해 의료 데이터 보호 및 연구 윤리의 중요성 습득.

**GitHub**: https://github.com/qkrguswn04-stack/PROJECT/tree/main/OvaCDSS

**팀원**:
- 박현주 (PM, AI Lead): 초음파 AI 모델 개발
- 송대영: 혈액검사 XGBoost 분석
- 이다영: FastAPI/Next.js 개발

---

## 🛠️ 핵심 방법론적 차별성 (Core Philosophy)

1. **도메인 생태계와 통계학의 융합**: 단순한 예측 스코어링을 넘어, 의료 가이드라인에 기반한 데이터 엔지니어링과 선택 편향을 제어하는 통계적 장치(Causal Framework)를 모델링 전반에 이식합니다.

2. **비즈니스 및 임상적 제품화(Productization)**: 백엔드 스크립트에 머무는 코드를 Streamlit, Next.js 등 웹 프로토타입 인터페이스로 격상시켜 현업(의료진/의사결정권자)이 즉시 시뮬레이션할 수 있는 CDSS 형태로 제품화하는 역량을 지향합니다.

3. **학술적 강건성(Robustness) 검증**: 모델의 오버피팅이나 데이터 누수(Data Leakage)를 방지하기 위해 플라시보 테스트, 교란 민감도 분석 등 다각도의 통계적 검증 방어선을 구축합니다.

---

## 📚 기술 스택 요약

- **데이터 처리**: Python (Pandas, NumPy), PostgreSQL, MIMIC-IV, AI-HUB
- **머신러닝**: PyTorch, XGBoost, scikit-learn, CausalML
- **딥러닝**: YOLOv8, RT-DETR, DenseNet, Swin Transformer, Vision Transformer
- **백엔드**: FastAPI, SQLAlchemy
- **프론트엔드**: Next.js 14, React, Tailwind CSS, HTML5
- **배포/협업**: Streamlit, Docker, Git/SVN, Notion, AWS/On-premise

---

## 📞 연락처

- **Email**: qkrguswn04@gmail.com
- **Portfolio 상세**: https://app.notion.com/p/Park-Hyun-ju-341c849cdbb580d19ba5d67ba3bfc58d
- **GitHub**: https://github.com/qkrguswn04-stack
