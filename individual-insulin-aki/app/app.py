import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ─────────────────────────────────────────────
# 1. 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Safe Insulin Pilot",
    page_icon="💉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 2. 글로벌 CSS (Clean Medical Theme)
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── 전역 폰트 & 배경 ── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', -apple-system, sans-serif !important;
    background-color: #F7F9FC !important;
    color: #1A2740 !important;
}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A3A5C 0%, #1E4976 100%) !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * {
    color: #E8F0FA !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p {
    color: #B8D0EE !important;
    font-size: 0.85rem !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #fff !important;
    border-radius: 8px !important;
}

/* ── 헤더 타이틀 영역 숨김 (커스텀 헤더 사용) ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ── 메인 컨텐츠 패딩 ── */
.block-container {
    padding: 1.5rem 2.5rem 2rem 2.5rem !important;
    max-width: 1400px !important;
}

/* ── 카드 컴포넌트 ── */
.card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 22px 26px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05);
    border: 1px solid #E8EEF5;
    margin-bottom: 16px;
}
.card-blue {
    background: linear-gradient(135deg, #EBF4FF 0%, #F0F7FF 100%);
    border-left: 4px solid #2563EB;
}
.card-green {
    background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF8 100%);
    border-left: 4px solid #059669;
}
.card-amber {
    background: linear-gradient(135deg, #FFFBEB 0%, #FEF9ED 100%);
    border-left: 4px solid #D97706;
}
.card-red {
    background: linear-gradient(135deg, #FFF5F5 0%, #FEF2F2 100%);
    border-left: 4px solid #DC2626;
}

/* ── 섹션 헤더 ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.0rem;
    font-weight: 600;
    color: #1A2740;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 2px solid #E8EEF5;
}
.section-header span.icon {
    font-size: 1.1rem;
}

/* ── 페이지 메인 타이틀 ── */
.app-header {
    background: linear-gradient(135deg, #1A3A5C 0%, #1E5FA0 100%);
    border-radius: 14px;
    padding: 22px 28px;
    margin-bottom: 22px;
    box-shadow: 0 4px 20px rgba(26,58,92,0.18);
}
.app-header h1 {
    color: #FFFFFF !important;
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    margin: 0 0 4px 0 !important;
}
.app-header p {
    color: #B8D4EE !important;
    font-size: 0.88rem !important;
    margin: 0 !important;
    line-height: 1.5 !important;
}

/* ── 환자 정보 테이블 ── */
.info-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
}
.info-table td {
    padding: 9px 12px;
    border-bottom: 1px solid #EEF2F7;
}
.info-table tr:last-child td { border-bottom: none; }
.info-table td:first-child {
    color: #6B7A90;
    font-weight: 500;
    width: 46%;
    white-space: nowrap;
}
.info-table td:last-child {
    color: #1A2740;
    font-weight: 600;
}
.info-table tr:hover td { background: #F7F9FC; }

/* ── 배지 ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-blue  { background: #DBEAFE; color: #1D4ED8; }
.badge-green { background: #D1FAE5; color: #065F46; }
.badge-red   { background: #FEE2E2; color: #991B1B; }

/* ── Metric 카드 오버라이드 ── */
div[data-testid="stMetricValue"] {
    font-size: 2.0rem !important;
    font-weight: 700 !important;
    color: #1A2740 !important;
    line-height: 1.2 !important;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.82rem !important;
    color: #6B7A90 !important;
    font-weight: 500 !important;
}
div[data-testid="stMetricDelta"] svg { display: none !important; }
div[data-testid="stMetricDelta"] > div {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
}

/* ── 슬라이더 ── */
[data-testid="stSlider"] .stSlider > div > div > div > div {
    background: #2563EB !important;
}
[data-testid="stSlider"] label {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Divider ── */
hr {
    border: none !important;
    border-top: 1.5px solid #E8EEF5 !important;
    margin: 18px 0 !important;
}

/* ── 경고 박스 ── */
.warning-box {
    background: #FFF8F0;
    border: 1px solid #FBD38D;
    border-left: 4px solid #D97706;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.82rem;
    color: #7C4A0A;
    line-height: 1.6;
    margin-top: 10px;
}

/* ── 구간 강조 레이블 ── */
.range-label {
    font-size: 0.78rem;
    color: #6B7A90;
    margin-top: 2px;
}

/* ── 사이드바 하단 버전 표시 ── */
.sidebar-footer {
    position: fixed;
    bottom: 1rem;
    font-size: 0.72rem;
    color: rgba(255,255,255,0.35) !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 3. 데이터 로드
# ─────────────────────────────────────────────
@st.cache_resource
def load_assets():
    import os
    from fontTools.ttLib import TTCollection

    _otf_path = os.path.join(os.environ.get('TEMP', 'C:/Temp'), 'NotoSansCJKKR-Regular.otf')

    if not os.path.exists(_otf_path):
        # Windows 시스템 폰트 경로 후보
        _ttc_candidates = [
            r'C:\Windows\Fonts\malgun.ttf',           # 맑은 고딕 (가장 확실)
            r'C:\Windows\Fonts\NotoSansCJK-Regular.ttc',
        ]
        _ttc_path = next((p for p in _ttc_candidates if os.path.exists(p)), None)

        if _ttc_path and _ttc_path.endswith('.ttc'):
            ttc = TTCollection(_ttc_path)
            ttc.fonts[1].save(_otf_path)
        elif _ttc_path and _ttc_path.endswith('.ttf'):
            # ttf는 단일 파일이라 그냥 복사
            import shutil
            shutil.copy(_ttc_path, _otf_path)

    _kr_entry = fm.FontEntry(fname=_otf_path, name='Korean Font')
    fm.fontManager.ttflist.insert(0, _kr_entry)
    plt.rcParams['font.family']        = 'Korean Font'
    plt.rcParams['axes.unicode_minus'] = False

    model    = joblib.load('causal_insulin_model.pkl')
    data     = pd.read_csv('test_data_for_app.csv')
    features = joblib.load('feature_columns.pkl')
    return model, data, features


model, df, feature_cols = load_assets()


# ─────────────────────────────────────────────
# 4. 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style="text-align:center; padding: 6px 0 20px 0;">
            <div style="font-size:2.2rem;">💉</div>
            <div style="font-size:1.0rem; font-weight:700; color:#FFFFFF; letter-spacing:0.3px;">
                Safe Insulin Pilot
            </div>
            <div style="font-size:0.72rem; color:#8AAECE; margin-top:4px;">
                인과추론 기반 인슐린 시뮬레이터
            </div>
        </div>
        <hr style="border-color:rgba(255,255,255,0.15) !important; margin:0 0 20px 0 !important;">
    """, unsafe_allow_html=True)

    st.markdown('<p style="font-size:0.78rem; color:#8AAECE; font-weight:600; letter-spacing:1px; margin-bottom:6px;">환자 선택</p>', unsafe_allow_html=True)
    patient_ids  = df['stay_id'].unique()
    selected_id  = st.selectbox("환자 ID", patient_ids, label_visibility="collapsed")

    # 선택된 환자 간략 상태
    _p = df[df['stay_id'] == selected_id].iloc[0]
    creat = _p['creatinine']
    creat_status = ("정상", "badge-green") if creat < 1.2 else (("경계", "badge-blue") if creat < 2.0 else ("이상", "badge-red"))

    st.markdown(f"""
        <div style="background:rgba(255,255,255,0.08); border-radius:10px; padding:14px 16px; margin-top:14px;">
            <div style="font-size:0.72rem; color:#8AAECE; margin-bottom:8px; font-weight:600;">현재 환자 상태</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.82rem; color:#CBD5E1;">크레아티닌</span>
                <span style="font-size:0.9rem; font-weight:700; color:#fff;">{creat:.2f} <span style="font-size:0.7rem; font-weight:400;">mg/dL</span></span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.82rem; color:#CBD5E1;">현재 인슐린</span>
                <span style="font-size:0.9rem; font-weight:700; color:#fff;">{_p['insulin_dosage']:.1f} <span style="font-size:0.7rem; font-weight:400;">Units</span></span>
            </div>
            <div style="margin-top:8px;">
                <span class="badge {creat_status[1]}" style="font-size:0.75rem;">{creat_status[0]}</span>
            </div>
        </div>
        <div class="sidebar-footer">v1.0.0 · 임상시험용</div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 5. 메인 헤더
# ─────────────────────────────────────────────
patient_data = df[df['stay_id'] == selected_id].iloc[0]

st.markdown(f"""
<div class="app-header">
    <h1>👨‍⚕️ 인슐린-신장기능 인과추론 시뮬레이터</h1>
    <p>ICU 당뇨 환자의 인슐린 처방량 변화가 차기 크레아티닌 수치에 미치는 영향을 실시간으로 시뮬레이션합니다. &nbsp;|&nbsp;
    현재 환자: <strong style="color:#fff;">Stay ID {int(selected_id)}</strong></p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 6. 상단 요약 메트릭 바
# ─────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)

def metric_card(col, icon, label, value, sub="", color="#2563EB"):
    col.markdown(f"""
    <div class="card" style="text-align:center; padding:16px 12px;">
        <div style="font-size:1.5rem;">{icon}</div>
        <div style="font-size:0.75rem; color:#6B7A90; margin:4px 0 2px 0; font-weight:500;">{label}</div>
        <div style="font-size:1.45rem; font-weight:700; color:{color};">{value}</div>
        <div style="font-size:0.72rem; color:#9CA3AF;">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

metric_card(m1, "🪪", "Stay ID",          f"{int(selected_id)}", "환자 식별번호")
metric_card(m2, "👤", "나이 / 성별",
            f"{int(patient_data['age'])}세",
            "남성" if patient_data['gender_male'] == 1 else "여성")
metric_card(m3, "🧪", "현재 크레아티닌",
            f"{patient_data['creatinine']:.2f}",
            "mg/dL", color="#DC2626" if patient_data['creatinine'] >= 2.0 else "#059669")
metric_card(m4, "💉", "현재 인슐린 처방량",
            f"{patient_data['insulin_dosage']:.1f}",
            "Units", color="#2563EB")


# ─────────────────────────────────────────────
# 7. 메인 2열 레이아웃 (전체 영역을 하나의 card로 감싸도록 변경)
# ─────────────────────────────────────────────

col_left, col_right = st.columns([1, 1.7], gap="large")

# ── 왼쪽: 환자 상세 정보 ──────────────────────
with col_left:
    st.markdown("""
        <div class="section-header">
            <span class="icon">📋</span> 환자 상세 정보
        </div>
    """, unsafe_allow_html=True)

    # ── IPW 인과 공변량 (모델이 편향 통제에 사용한 변수) ──
    ipw_fields = {
        'age':            ('나이',              lambda v: f"{int(v)} 세"),
        'gender_male':    ('성별',              lambda v: "남성 ♂" if v == 1 else "여성 ♀"),
        'creatinine':     ('크레아티닌 (현재)', lambda v: f"{v:.2f} mg/dL"),
        'insulin_dosage': ('인슐린 처방량',     lambda v: f"{v:.1f} Units"),
        'fluid_balance':  ('수액 투여량',       lambda v: f"{v:.1f} mL"),
        'diuretic':       ('이뇨제 사용',       lambda v: "사용" if v == 1 else "미사용"),
    }

    # ── 참고 임상 정보 (모델 공변량 외 추가 맥락 정보) ──
    ref_fields = {
        'glucose': ('혈당',       lambda v: f"{v:.1f} mg/dL"),
        'bmi':     ('BMI',        lambda v: f"{v:.1f}"),
        'weight':  ('체중',       lambda v: f"{v:.1f} kg"),
        'gcs':     ('GCS 점수',   lambda v: f"{int(v)}"),
        'lactate': ('젖산',       lambda v: f"{v:.2f} mmol/L"),
    }

    def build_rows(fields):
        html = ""
        for col_key, (label, fmt) in fields.items():
            if col_key in patient_data.index:
                try:
                    html += f"<tr><td>{label}</td><td>{fmt(patient_data[col_key])}</td></tr>"
                except Exception:
                    pass
        return html

    ipw_rows = build_rows(ipw_fields)
    ref_rows = build_rows(ref_fields)

    st.markdown(f"""
        <div style="font-size:0.72rem; font-weight:600; color:#2563EB;
                    letter-spacing:0.5px; margin-bottom:4px; margin-top:2px;">
        </div>
        <table class="info-table" style="margin-bottom:10px;">
            <tbody>{ipw_rows}</tbody>
        </table>
    """, unsafe_allow_html=True)

    if ref_rows:
        with st.expander("참고 임상 정보 보기 (모델 외 변수)"):
            st.markdown(f"""
            <table class="info-table">
                <tbody>{ref_rows}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # 신장 기능 상태 설명 카드
    creat_val = patient_data['creatinine']
    if creat_val < 1.2:
        card_cls, status_txt, desc = "card-green", "✅ 정상 범위", "현재 크레아티닌 수치는 정상 범위입니다."
    elif creat_val < 2.0:
        card_cls, status_txt, desc = "card-amber", "⚠️ 경계 범위", "신장 기능 저하가 진행 중일 수 있습니다. 지속 모니터링이 필요합니다."
    else:
        card_cls, status_txt, desc = "card-red", "🚨 이상 수치", "크레아티닌이 높아 신장 기능 이상이 의심됩니다. 즉각적인 임상 판단이 필요합니다."

    st.markdown(f"""
    <div class="card {card_cls}" style="margin-top:15px; margin-bottom:0;">
        <div style="font-weight:600; font-size:0.88rem; margin-bottom:4px;">{status_txt}</div>
        <div style="font-size:0.82rem; color:#374151; line-height:1.5;">{desc}</div>
        <div class="range-label">정상 기준: 남성 0.7–1.2 mg/dL · 여성 0.5–1.0 mg/dL</div>
    </div>
    """, unsafe_allow_html=True)


# ── 오른쪽: 시뮬레이션 ──────────────────────
with col_right:
    st.markdown("""
        <div class="section-header">
            <span class="icon">🔬</span> 실시간 투여량 시뮬레이션
        </div>
        <p style="font-size:0.85rem; color:#6B7A90; margin-bottom:16px; line-height:1.6;">
            슬라이더를 조작하여 인슐린 처방량을 변경하면, 인과추론 모델이 차기 크레아티닌 수치 변화를 즉시 예측합니다.
        </p>
    """, unsafe_allow_html=True)

    sim_dosage = st.slider(
        "💉 가상 인슐린 처방량 (Units)",
        min_value=0.0, max_value=50.0,
        value=float(patient_data['insulin_dosage']),
        step=0.5,
    )
    st.markdown(f"""
    <div style="font-size:0.75rem; color:#9CA3AF; margin-top:-8px; margin-bottom:8px;">
        현재 처방량 대비 {sim_dosage - patient_data['insulin_dosage']:+.1f} Units
    </div>
    """, unsafe_allow_html=True)

    # 예측 수행
    input_data = pd.DataFrame([patient_data[feature_cols]])
    input_data['insulin_dosage'] = sim_dosage
    predicted_creatinine = model.predict(input_data)[0]
    delta_val = predicted_creatinine - patient_data['creatinine']

    # 예측 결과 카드
    result_card_cls = "card-green" if delta_val < 0 else ("card-amber" if delta_val < 0.3 else "card-red")
    trend_icon = "📉" if delta_val < 0 else ("➡️" if abs(delta_val) < 0.05 else "📈")

    st.markdown(f"""
    <div class="card {result_card_cls}" style="margin-bottom:0; margin-top:15px;">
        <div class="section-header" style="border-bottom-color:rgba(0,0,0,0.07);">
            <span class="icon">{trend_icon}</span> 예측 결과
        </div>
        <div style="display:flex; align-items:flex-end; gap:18px; flex-wrap:wrap;">
            <div>
                <div style="font-size:0.78rem; color:#6B7A90; margin-bottom:2px;">예상 차기 크레아티닌</div>
                <div style="font-size:2.4rem; font-weight:800; color:#1A2740; line-height:1;">
                    {predicted_creatinine:.3f}
                    <span style="font-size:1.0rem; font-weight:500; color:#6B7A90;">mg/dL</span>
                </div>
            </div>
            <div style="padding-bottom:6px;">
                <div style="font-size:0.78rem; color:#6B7A90; margin-bottom:4px;">현재 대비 변화</div>
                <div style="font-size:1.3rem; font-weight:700; color:{'#059669' if delta_val < 0 else '#DC2626'};">
                    {delta_val:+.3f} mg/dL
                </div>
                <div style="font-size:0.75rem; color:#9CA3AF;">
                    현재: {patient_data['creatinine']:.3f} → 예측: {predicted_creatinine:.3f}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True) # <-- 전체를 감싸는 흰색 테두리 카드 종료


# ─────────────────────────────────────────────
# 8. 반사실 예측 곡선 그래프 (크기 최적화 및 한글 깨짐 보완)
# ─────────────────────────────────────────────
st.markdown("""
<div class="card" style="margin-top:4px;">
    <div class="section-header">
        <span class="icon">📈</span> 인슐린 처방량별 신장 수치 예측 곡선 (반사실 분석)
    </div>
    <p style="font-size:0.83rem; color:#6B7A90; margin:-6px 0 14px 0; line-height:1.6;">
        다른 모든 임상 변수를 현재 환자 상태로 고정한 채, 인슐린 처방량만 변화시켰을 때의 크레아티닌 예측값입니다.<br>
        이 곡선은 해당 환자 개인에 특화된 반사실(counterfactual) 곡선입니다.
    </p>
""", unsafe_allow_html=True)

sim_range  = np.arange(0, 51, 0.5)
df_sim     = pd.DataFrame([patient_data[feature_cols]] * len(sim_range))
df_sim['insulin_dosage'] = sim_range
curve_preds = model.predict(df_sim)

# ── 그래프 크기 조절 (가로폭을 줄이고 컴팩트하게 변경) ──
# 가로(figsize)를 기존 10에서 7.5로 줄여 화면에서 너무 과하게 차지하지 않도록 조절했습니다.
fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=140)
fig.patch.set_facecolor('#FFFFFF')
ax.set_facecolor('#FAFBFE')

# 정상 범위 배경 (크레아티닌 0.7~1.2)
ax.axhspan(0.7, 1.2, alpha=0.12, color='#059669', label='정상 범위 (0.7–1.2 mg/dL)')

# 예측 곡선
ax.plot(sim_range, curve_preds, color='#1D4ED8', linewidth=2.0,
        label='반사실 예측 곡선', zorder=3)

# 현재 처방량 수직선
ax.axvline(x=patient_data['insulin_dosage'], color='#6B7A90',
           linestyle=':', linewidth=1.2, label=f"현재 처방량 ({patient_data['insulin_dosage']:.1f} U)", zorder=2)

# 선택된 처방량 포인트
ax.axvline(x=sim_dosage, color='#EA580C', linestyle='--',
           linewidth=1.5, label=f"선택 처방량 ({sim_dosage:.1f} U)", zorder=4)
ax.scatter(sim_dosage, predicted_creatinine,
           color='#EA580C', s=70, zorder=6, edgecolors='white', linewidth=1.2)

# 예측값 레이블 주석
ax.annotate(
    f" {predicted_creatinine:.3f} mg/dL",
    xy=(sim_dosage, predicted_creatinine),
    xytext=(sim_dosage + 1.2, predicted_creatinine),
    fontsize=7.5, color='#EA580C', fontweight='bold',
    va='center',
)

# 축 꾸미기 및 레이블 지정 (한글 깨짐 확인용)
ax.set_xlabel("인슐린 처방량 (Units)", fontsize=8, fontweight='600', color='#475569', labelpad=6)
ax.set_ylabel("예측 크레아티닌 (mg/dL)", fontsize=8, fontweight='600', color='#475569', labelpad=6)
ax.tick_params(labelsize=7.5, colors='#64748B', length=3)
ax.grid(True, linestyle=':', alpha=0.5, color='#CBD5E1')

for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)
for spine in ['left', 'bottom']:
    ax.spines[spine].set_color('#E2E8F0')
    ax.spines[spine].set_linewidth(0.8)

ax.legend(loc='upper right', fontsize=7, frameon=True,
          facecolor='white', edgecolor='#E2E8F0', framealpha=0.95,
          borderpad=0.6, handlelength=1.5)

plt.tight_layout(pad=0.8)

# 레이아웃 내에서 그래프가 너무 꽉 차지 않도록 가로폭 제한을 두고 렌더링
col_layout, _ = st.columns([3, 1]) # 3:1 비율로 나누어 우측에 여백을 줌으로써 시각적 크기 축소
with col_layout:
    st.pyplot(fig, use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 10. 하단 경고 문구
# ─────────────────────────────────────────────
st.markdown("""
<div class="warning-box">
    ⚠️ <strong>임상적 고지 사항</strong> — <br> 
    본 시뮬레이션 결과는 MIMIC-IV 후향적 데이터 기반 인과추론 모델(IPW-XGBoost)의
    예측값입니다. <br>
    개별 환자의 실제 예후를 보장하지 않으며, 전문의의 최종 임상 판단을 대체할 수 없습니다.
</div>
""", unsafe_allow_html=True)
