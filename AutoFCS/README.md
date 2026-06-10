#### AutoFCS 🔬
# Flow Cytometry 자동 전처리 파이프라인
---

## 📌 Overview

Flow Cytometry(유세포분석) 데이터는 분석 전 **Cell Debris 제거**와 **Singlet 추출**이 필수적이지만,
기존에는 FlowJo 등 전문 소프트웨어를 통한 **수동 게이팅(Manual Gating)** 에 의존해왔습니다.

**AutoFCS**는 이 과정을 완전 자동화합니다.
FCS 파일을 웹 브라우저에 업로드하는 것만으로, 데이터 기반 알고리즘이 Debris와 Cell의 경계를 스스로 탐지하고
Dot Plot 결과를 실시간으로 시각화합니다.

---

## ✨ Key Features

- **완전 자동 게이팅** — 사용자가 직접 게이트를 그리지 않아도 됨
- **3중 하이브리드 컷오프 전략** — 다양한 샘플 분포 타입에 유연하게 대응
- **RANSAC 기반 Singlet 추출** — 이상치에 강건한 선형 회귀로 세포 뭉침 제거
- **배치 처리** — 여러 FCS 파일 동시 분석, 글로벌 게이트 일괄 적용
- **정량 검증** — Label 채널 존재 시 Cell Recall / Debris Removal Rate 자동 산출
- **결과 이미지 저장** — File System Access API를 통한 경로 지정 PNG 다운로드

---

## 🧠 Algorithm Design

### Step 1 · Cell Debris Removal

FSC(Forward Scatter) / SSC(Side Scatter) 신호를 분석해 세포 집단의 안전 영역을 자동 산출합니다.

```
FSC 신호 분포
     │     ╭──╮          ╭──╮
     │    /    \         /    \
     │   / Debris\      / Cell \
     │──/──────────\───/────────\──→ FSC-A
                    ↑
              Valley Cutoff (자동 탐지)
```

| 전략 | 적용 조건 | 방법 |
|------|-----------|------|
| Valley Detection | 피크 2개 이상 (PBMC 스타일) | 두 피크 사이 최저점을 컷오프로 설정 |
| Left Flank Descent | 피크 1개 (뭉쳐 있는 경우) | 피크 정상에서 좌측으로 이동, 높이 15% 지점을 컷오프로 설정 |
| Diagonal Gate | 전체 구간 | FSC 구간별 SSC 99.5th / 1st 백분위수로 상·하단 경계 선형 회귀 |

> Gaussian smoothing (σ=3) 전처리로 기계적 노이즈에 의한 가짜 피크 방지

### Step 2 · Singlet Gating

Debris 제거 후 세포 뭉침(Doublet / Multiplet)을 제거합니다.

- FSC-H(Height) vs FSC-A(Area) 관계에서 **RANSAC 회귀**로 단일 세포 선형 궤적 추정
- 잔차(residual)의 `평균 ± 1.5σ` 범위 내 이벤트만 Singlet으로 최종 추출
- 다수 FCS 파일에서 합산 샘플링(최대 3,000개/파일)으로 글로벌 모델 학습 → 배치 일관성 확보

---

## 🛠 Tech Stack

| Category | Library |
|----------|---------|
| Web Framework | Flask |
| FCS Parsing | FlowKit |
| Numerical Computing | NumPy |
| Signal Processing | SciPy (find_peaks, gaussian_filter1d) |
| ML-based Gating | scikit-learn (RANSACRegressor) |
| Visualization | Matplotlib |
| Frontend | HTML5, Vanilla JavaScript |

---

## 🚀 Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/AutoFCS.git
cd AutoFCS
pip install -r requirements.txt
```

### 2. Run

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

### 3. Usage

```
① Upload Files  →  FCS 파일 1개 이상 업로드
② Remove Cell Debris  →  FSC/SSC 스케일 설정 후 [분석하기]
③ Singlet  →  Singlet 분석 실행
```

> FSC/SSC Limit 값은 비워두면 기본값(250,000 / 150,000)으로 자동 적용됩니다.

---

## 📁 Project Structure

```
AutoFCS/
├── app.py                  # Flask 서버 — 라우팅 및 게이팅 알고리즘 전체
├── requirements.txt        # 의존성 패키지
├── README.md
├── .gitignore
│
├── templates/
│   └── index.html          # 3단계 탭 대시보드 UI
│
└── sample_data/            # (선택) 테스트용 FCS 샘플 파일
    └── sample.fcs
```

---

## 📊 Validation (Label 채널 보유 파일)

FCS 파일에 `Label` 채널(정답 라벨)이 포함된 경우, 게이팅 품질을 자동으로 정량 평가합니다.

| Metric | 설명 |
|--------|------|
| **Overall Accuracy** | 전체 이벤트 분류 일치율 |
| **Cell Recall** | 실제 세포를 얼마나 놓치지 않고 포획했는가 |
| **Debris Removal Rate** | 실제 Debris를 얼마나 제거했는가 |

결과는 서버 콘솔에 파일별, 전체 집계 모두 출력됩니다.

---

## ⚠️ Limitations & Future Work

- 현재 FSC/SSC 2채널 기반 — CD4/CD8 등 형광 마커 채널 다중 게이팅 미지원
- 규칙 기반 알고리즘 한계 — 3개 이상 세포 집단이 혼재하는 샘플은 GMM/UMAP 기반 클러스터링으로 고도화 예정
- Label 채널 없는 파일은 외부 Ground Truth와의 비교 검증 필요

---

**Portfolio detail** : [https://app.notion.com/p/AutoFCS-Flow-Cytometry-330c849cdbb580399cf0e115cef9e2f0?source=copy_link]
