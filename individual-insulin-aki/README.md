# 🚀 Advanced Data Science & Causal Inference Portfolio Hub

본 저장소는 머신러닝 알고리즘과 통계학적 **인과 추론(Causal Inference)** 방법론을 융합하여, 현실의 복잡한 의료 도메인 문제 및 데이터 파이프라인의 한계를 돌파한 4개의 프로젝트(개인 2, 팀 2)를 모아둔 포트폴리오 아카이브입니다.

---

## 📂 프로젝트 디렉토리 안내 (Directory Index)

### 👤 개인 프로젝트 (Individual Projects)

#### 1. `individual-insulin-aki/` — 인과 추론 기반 인슐린 투여량별 AKI 예방 시뮬레이터 (CDSS)
* **Core Tech**: MIMIC-IV v2.2, PostgreSQL, Inverse Propensity Weighting (IPW), XGBoost, Streamlit
* **Key Challenge**: 중환자실(ICU) 관측 데이터 특성상 발생하는 의사의 중증도별 처방 편향(Selection Bias)으로 인해 일반 ML 모델이 약물의 순수한 치료 효과를 왜곡·과소평가하는 문제 직면.
* **Solution & Impact**: 
  * 로지스틱 회귀 기반 **역성향 점수 가중치(IPW)**를 적용하여 배경 공변량이 정렬된 가상의 무작위 임상시험 환경(Pseudo-RCT)을 수학적으로 구축.
  * Causal XGBoost 모델을 통해 **인슐린 변수 중요도를 기존 대비 35.6% 급증**시키며 숨겨진 인과 신호(True Causal Signal) 복원 성공.
  * 의사가 가상 처치 용량을 조절하며 차기 신장 수치 변화를 확인하는 **What-if 시뮬레이터(Streamlit)** 프로토타입 구현.
  * **플라시보 검증(Placebo Treatment Refuter)** 알고리즘을 도입하여 도출된 인과 곡선이 통계적 환각이 아닌 강건한 인과 경로임을 학술적으로 방어.

#### 2. `individual-fcs-preprocessing/` — FCS 유세포 분석 데이터 전처리 프로그램 개발
* **Core Tech**: Python, FlowPy/FCSPly, Automated Gating, Outlier Detection, High-throughput Data Pipeline
* **Key Challenge**: 대용량 FCS(Flow Cytometry Standard) 바이너리 파일 구조의 특성상 수동 게이팅(Gating)과 전처리에 막대한 시간과 연구자 편향이 개입되는 병목 현상 발생.
* **Solution & Impact**: 파이썬 기반의 대용량 FCS 파일 자동 로드, 노이즈 필터링 및 다차원 특성 추출 파이프라인을 구축하여 데이터 정제 속도를 획기적으로 개선하고 하이쓰루풋(High-throughput) 분석 환경 표준화 기틀 마련.

---

### 👥 팀 프로젝트 (Team Projects)

#### 3. `team-ovarian-cancer-cdss/` — 난소암 초음파 이미지 기반 임상 의사결정 지원 시스템(CDSS) 개발
* **Role**: Lead Data Scientist (AI 모델링 및 평가지표 설계 주도)
* **Core Tech**: PyTorch, Convolutional Neural Networks (CNN), Grad-CAM, Medical Image Augmentation
* **Summary**: 난소암 의심 환자의 골반 초음파 영상을 분석하여 양성/악성 종양을 분류하는 정밀 딥러닝 아키텍처 설계. Grad-CAM 기반의 시각적 설명 가능성(XAI)을 결합하여 초음파 내 변변 부위를 하이라이팅함으로써 현장 의료진의 진단 수용성과 신뢰도를 극대화함.

#### 4. `team-project-4/` — [네 번째 프로젝트 제목 입력란]
* **Role**: Data Engineer / Analyst
* **Core Tech**: [핵심 기술 스택 예: Apache Spark, Fast API, Docker]
* **Summary**: [해당 팀 프로젝트의 대략적인 문제 해결 중심의 성과 1~2줄 요약 입력]

---

## 🛠️ 핵심 방법론적 차별성 (Core Philosophy)

1. **도메인 생태계와 통계학의 융합**: 단순한 예측 스코어링을 넘어, 의료 가이드라인에 기반한 데이터 엔지니어링과 선택 편향을 제어하는 통계적 장치(Causal Framework)를 모델링 전반에 이식합니다.
2. **비즈니스 및 임상적 제품화(Productization)**: 백엔드 스크립트에 머무는 코드를 Streamlit 등 웹 프로토타입 인터페이스로 격상시켜 현업(의료진/의사결정권자)이 즉시 시뮬레이션할 수 있는 CDSS 형태로 제품화하는 역량을 지향합니다.
3. **학술적 강건성(Robustness) 검증**: 모델의 오버피팅이나 데이터 누수(Data Leakage)를 방지하기 위해 플라시보 테스트, 교란 민감도 분석 등 다각도의 통계적 검증 방어선을 구축합니다.

---
📧 **Contact**: `qkrguswn04@gmail.com` | 🔗 **Portfolio Details**: [https://app.notion.com/p/Safe-Insulin-Pilot-348c849cdbb5808491eeee4e7dcafa65?source=copy_link]
