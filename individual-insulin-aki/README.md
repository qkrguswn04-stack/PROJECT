# individual-insulin-aki — 인과 추론 기반 인슐린 투여량별 신장 기능 변화 예측 시뮬레이터 (CDSS)

* **Core Tech**: MIMIC-IV v2.2, PostgreSQL, Inverse Propensity Weighting (IPW), XGBoost, Streamlit
* **Key Challenge**: 중환자실(ICU) 관측 데이터 특성상 발생하는 의사의 중증도별 처방 편향(Confounding by Indication)으로 인해, 일반 ML 모델이 인슐린의 순수한 치료 효과를 왜곡·과소평가하는 문제 직면.
* **Solution & Impact**:
  * MIMIC-IV v2.2 T2DM 코호트 기반 12시간 격자 시계열 설계 및 Xₜ → Yₜ₊₁ 인과 시차(Lag) 반영으로 역인과(Reverse Causality) 원천 차단.
  * 로지스틱 회귀 기반 **역성향 점수 가중치(IPW)**로 처방 편향 제거 후 Pseudo-RCT 환경 구축. `insulin_dosage` 변수 중요도 **35.6% 상승**, 숨겨진 인과 신호 복원 성공 (MAE 0.1654, R² 0.9408).
  * **플라시보 강건성 검증(Placebo Treatment Refuter)** — 처치 변수 셔플 후 반사실 곡선 평탄화 확인으로 인과 경로의 통계적 유효성 방어.
  * 의사가 가상 처치 용량을 실시간 조절하며 차기 신장 수치를 확인하는 **What-if CDSS 시뮬레이터(Streamlit)** 프로토타입 구현.
 
 **Project Detail** : [https://app.notion.com/p/Safe-Insulin-Pilot-348c849cdbb5808491eeee4e7dcafa65?source=copy_link]
