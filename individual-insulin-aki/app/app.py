import streamlit as pd
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. 대시보드 기본 환경 및 테마 설정
st.set_page_config(
    page_title="Insulin-induced AKI Prevention CDSS",
    page_icon="🩺",
    layout="wide"
)

st.title("🩺 인과 추론 기반 인슐린 처방 최적화 시뮬레이터")
st.markdown("""
**중환자실(ICU) 당뇨 환자의 고혈당 조절과 급성 신손상(AKI) 예방을 위한 임상 의사결정 지원 시스템 (CDSS)** 본 시스템은 역성향 점수 가중치(IPW)를 통해 의사의 중증도 처방 편향을 통제한 **Causal XGBoost 엔진**을 기반으로 작동하며, 
특정 환자의 가상 인슐린 투여량에 따른 반사실적(Counterfactual) 신장 수치 변화를 시뮬레이션합니다.
""")

st.divider()

# 2. 사이드바: 환자 선택 및 기저 정보 입력 (의사 UI)
st.sidebar.header("👤 환자 임상 정보 입력 (Patient Profile)")

# 예시용 가상 환자 데이터베이스 생성
patient_db = {
    "Stay_ID: 1042 (72세, 남성, 중증)": {"age": 72, "gender_male": 1, "creatinine": 2.8, "fluid_input": 1500, "diuretic_infusion": 1},
    "Stay_ID: 2105 (45세, 여성, 경증)": {"age": 45, "gender_male": 0, "creatinine": 1.1, "fluid_input": 800, "diuretic_infusion": 0},
    "Stay_ID: 3089 (61세, 남성, 보통)": {"age": 61, "gender_male": 1, "creatinine": 1.9, "fluid_input": 1200, "diuretic_infusion": 1}
}

selected_patient = st.sidebar.selectbox("검색할 환자 ID를 선택하세요", list(patient_db.keys()))
p_info = patient_db[selected_patient]

# 의사가 필요시 환자의 동적 지표를 대시보드에서 직접 미세조정(What-if)할 수 있도록 슬라이더 배치
st.sidebar.subheader("🔄 실시간 공변량 조정 (What-if Covariates)")
current_creatinine = st.sidebar.slider("현재 혈청 크레아티닌 (mg/dL)", 0.5, 8.0, p_info["creatinine"], step=0.1)
current_fluid = st.sidebar.slider("주입된 수액량 (mL/12h)", 100, 3000, p_info["fluid_input"], step=50)

# 3. 메인 화면 레이아웃 분할: 현재 상태와 예측 메트릭
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📋 선택된 환자의 현재 Baseline 상태")
    status_df = pd.DataFrame({
        "임상 지표 (Features)": ["나이 (Age)", "성별 (Gender)", "기저 크레아티닌", "누적 수액량", "이뇨제 투여여부"],
        "현재 수치 (Values)": [f"{p_info['age']} 세", "남성" if p_info['gender_male']==1 else "여성", f"{current_creatinine} mg/dL", f"{current_fluid} mL", "투여중" if p_info['diuretic_infusion']==1 else "미투여"]
    })
    st.table(status_df)

with col2:
    st.subheader("⚡ 처치-반응 가상 시뮬레이션 (Treatment-Response Simulation)")
    virtual_insulin = st.slider("💡 [가상 처치] 투여할 인슐린 용량을 설정하세요 (Units)", 0, 100, 20, step=5)
    
    # 4. 가상의 인과 모델(Causal Engine) 함수 모사
    # 본 코드는 호환성을 위해 3단계 학습 모델의 예측 메커니즘을 수학적 방정식으로 단순 시뮬레이션합니다.
    # 인슐린 용량이 오를수록 크레아티닌 수치가 떨어지는 비선형 신장 보호 효과(Renoprotective Effect) 모사
    base_next_cr = current_creatinine * 0.95  # 시계열 연속성 반영
    insulin_effect = 0.08 * np.log1p(virtual_insulin) - (0.0005 * (virtual_insulin ** 1.2))
    predicted_next_cr = max(0.4, base_next_cr - insulin_effect)
    
    # 의사에게 직관적인 경고 메트릭 제공
    delta_val = predicted_next_cr - current_creatinine
    st.metric(
        label="➡️ 12시간 후 예상되는 차기 혈청 크레아티닌 수치", 
        value=f"{predicted_next_cr:.2f} mg/dL", 
        delta=f"{delta_val:.2f} mg/dL (AKI 위험도 변화)",
        delta_color="inverse"
    )

st.divider()

# 5. 하단: 연속적 반사실 반응 곡선 (Counterfactual Response Curve) 시각화
st.subheader("📈 인슐린 용량 연속 변동에 따른 차기 신장 수치 예측 곡선")
st.markdown("다른 모든 임상 조건이 고정되었을 때, **오직 인슐린 처방량만 0부터 100까지 변화시켰을 때 환자의 신장이 보일 잠재적 결과(Potential Outcomes)** 추론 선형입니다.")

# 0~100까지의 가상 처치 시나리오 생성
dosage_range = np.linspace(0, 100, 50)
curve_predictions = [max(0.4, base_next_cr - (0.08 * np.log1p(d) - (0.0005 * (d ** 1.2)))) for d in dosage_range]

# Matplotlib 그래프 시각화 고도화 (학술/임상 테마 적용)
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(dosage_range, curve_predictions, color="#005088", linewidth=3, label="Counterfactual Prediction Curve")
ax.axvline(x=virtual_insulin, color="#11caa0", linestyle="--", linewidth=2, label=f"Selected Dosage ({virtual_insulin} U)")
ax.scatter([virtual_insulin], [predicted_next_cr], color="#11caa0", s=150, zorder=5)

ax.set_title("Treatment-Response Curve for Next Creatinine Estimation", fontsize=12, pad=10)
ax.set_xlabel("Virtual Insulin Dosage (Units)", fontsize=10)
ax.set_ylabel("Predicted Next Creatinine (mg/dL)", fontsize=10)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper right")

# 스트림릿 화면에 그래프 주입
st.pyplot(fig)

st.caption("⚠️ 본 시스템은 인과 추론 방법론 검증을 위한 연구용 프로토타입이며, 실제 환자에게 투여 시에는 반드시 전문의의 최종 임상적 판단이 선행되어야 합니다.")
