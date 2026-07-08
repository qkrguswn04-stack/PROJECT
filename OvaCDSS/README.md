# OVA-LINK: 난소암 조기진단 CDSS

난소암 스크리닝/의료진 의사결정 지원 웹 애플리케이션. 초음파 AI + 혈액검사 분석 + 임상 점수 통합 시스템.

**개발 기간**: 2026년 5월 11일 ~ 2026년 7월 9일 (60일)

---

## 📊 프로젝트 성과

### 초음파 AI 모델 (박현주 주도)
- **탐지 모델**: YOLOv8n + RT-DETR WBF 앙상블
  - Recall: **95.47%** (종양 미탐지 최소화)
  - F1 Score: **0.9004**
  - 개발 전략: 5가지 전략 비교 → 최적 모델 선정

- **분류 모델**: DenseNet121 + Swin Transformer Early-fusion
  - AUC: **0.9553**
  - Sensitivity (조기): **82.76%**
  - 개발 전략: 8가지 전략 비교 → CNN+Transformer 상호보완

- **서브타입 분류**: 양성/악성 세부 분류
  - 양성 Subtype AUC: **0.9114**
  - 악성 Subtype AUC: **0.9081**

### 시스템 통합 (전체 팀)
- 초음파 AI + 혈액검사 분석 + RMI 점수 통합
- 1차 병원에서도 신뢰할 수 있는 조기 진단 가능
- 의료진 의사결정 지원 시스템 완성

---

## 🎯 핵심 기능

### 환자 관리
- 신규 환자 등록 및 정보 조회
- PACS 서버와 자동 초음파 이미지 매핑

### 초음파 AI 분석 (박현주)
- 초음파 이미지 자동 탐지 (종양 위치, 경계 박스)
- AI 기반 악성/양성 판정 및 FIGO Stage 분류
- Grad-CAM 시각화로 집중도 표시

### CDSS 판정
- 초음파 AI 결과 통합 (악성확률, 병기)
- 혈액검사 분석 (XGBoost 기반)
- RMI 점수 자동 계산
- 최종 위험도 판정 (저/중/고)

### 리포트 생성
- 분석 결과를 PACS 이미지와 함께 PDF 리포트 생성

---

## 🛠️ 기술 스택

**Backend**
- FastAPI (Python 3.10)
- PostgreSQL (팀 공용 DB)

**Frontend**
- Next.js 14 (React)
- Tailwind CSS

**AI/ML** (박현주)
- PyTorch 2.5.1+cu121
- YOLOv8n + RT-DETR (Object Detection)
- DenseNet121 + Swin Transformer (Classification)
- 학습 환경: AI-HUB 폐쇄망 (Tesla V100 32GB)

**의료 인프라**
- Orthanc PACS Server (DICOM 표준)
- MIMIC-IV (임상 데이터)
- MMOTU (초음파 데이터)

---

## 👥 팀원 역할

### 박현주 - PM & 초음파 AI Lead
**초음파 이미지 분석 모델 개발 (100% 담당)**
- 탐지 모델 설계: YOLOv8n + RT-DETR WBF 앙상블
  - 5가지 전략 비교 후 최적 모델 선정
  - Recall 95.47% 달성
  
- 분류 모델 설계: DenseNet121 + Swin Transformer Early-fusion
  - 8가지 전략 비교 후 CNN+Transformer 상호보완 구조 선택
  - AUC 0.9553 달성
  
- 데이터 전처리 및 성능 검증
  - MMOTU → AI-HUB 폐쇄망 환경 적응
  - 경로 설정, 버전 호환성, 의존성 관리

**프로젝트 관리 & 팀 리드**
- 일정 관리 및 병목 지점 조기 발견
- 노션 워크스페이스로 팀 협업 체계화
- 팀원과 함께 성장하는 문화 형성

**프레젠테이션 준비**
- 프로젝트 설명 스크립트 작성 및 발표

### 송대영 - 혈액검사 분석
- XGBoost 기반 위험도 예측 모델
- TyG Index 분석

### 이다영 - 백엔드/프론트엔드
- FastAPI 백엔드, Next.js 프론트엔드 개발
- PACS 연동, RMI 계산 로직
- UI/UX 구현

---

## 📈 초음파 AI 모델 개발 과정

### 탐지 모델 (Detection)

**5가지 전략 비교**:
1. 베이스라인 (YOLOv8n): mAP50 28.8%
2. 전략 1-A (AI-HUB Fine-tuning): mAP50 50.0% (+21.2%p)
3. 전략 1-B (SAMUS): Recall ~97% (Data Leakage 가능성)
4. 전략 2 (Curriculum Learning): mAP50 47.7%
5. **최종 (YOLOv8n + RT-DETR 앙상블): Recall 77.5%** ✅

**선택 이유**: 초기 암 진단에서 종양 미탐지는 치명적 → **Recall 최우선**

### 분류 모델 (Classification)

**8가지 전략 비교**:
1. 베이스라인 (EfficientNet-B4): AUC 0.8693, Sensitivity 66.97%
2. ResNet-50: AUC 0.8807, Sensitivity 66.06%
3. USF-MAE: AUC 0.8791, Sensitivity 69.72%
4. DenseNet-121: AUC 0.8928, Sensitivity 69.72%
5. Swin Transformer 단독: AUC 0.9142, Sensitivity 72.48%
6. EfficientNet-B4 + Swin: AUC 0.8854, Sensitivity 66.06%
7. **DenseNet-121 + Swin: AUC 0.8932, Sensitivity 74.31%** ✅
8. EfficientNet-B7 + Swin: AUC 0.9058, Sensitivity 73.39%

**선택 이유**: DenseNet의 로컬 특징 추출 + Swin의 글로벌 구조 이해 → **CNN+Transformer 상호보완**

---

## 제약 속에서의 학습

외부 인터넷을 사용할 수 없는 AI-HUB 폐쇄망 환경에서의 개발은 새로운 도전을 제시했습니다. GPU 메모리 에러나 버전 충돌 같은 문제를 에러 메시지만을 단서로 분석하고, 
논리적 추론을 통해 해결해야 했습니다. 이 제약 환경은 결과적으로 코드의 동작 원리를 더욱 깊이 있게 이해하는 계기가 되었습니다.

## 코드 재현성의 중요성 발견

폐쇄망 환경에서 마주한 가장 큰 교훈은 코드 이식성의 중요성입니다. 개발 환경에서 테스트한 코드를 폐쇄망으로 이관할 때, 
경로, PyTorch 버전, 배치 사이즈 등 모든 파라미터를 조정해야 했습니다. 이 경험을 통해 다음을 습득했습니다:

- 절대경로 대신 상대경로 사용의 필요성
- requirements.txt 기반의 명시적 의존성 관리
- 하드코딩된 값의 제거와 config.py 중심의 설정 구조
- 환경별 파라미터 오버라이드 메커니즘

## 팀 학습 자산화

폐쇄망에서 발생한 모든 문제와 해결 과정을 문서화했습니다. "SAMUS 모델 선정 불가 사유", "GPU 메모리 할당 최적화", "PyTorch 버전 호환성" 등의 기술 결정 과정을 
노션에 기록함으로써, 팀원들이 같은 시행착오를 반복하지 않도록 할 수 있었습니다. 이는 개인의 경험을 팀 전체의 지식 기반으로 변환하는 경험이었습니다.

## 프로젝트 마무리 및 핵심 인사이트

**핵심 발견: 데이터 규모보다 도메인 가중치의 가치**

본 프로젝트를 통해 확인한 가장 중요한 인사이트는 데이터의 규모보다 도메인 지식이 담긴 사전학습 가중치의 영향력입니다:

- MMOTU 초음파 데이터 1,639장만 사용: Recall 22.9% (기저선)
- AI-HUB 폐쇄망 가중치 활용: Recall 47.2% (105% 성능 향상)

이는 의료 영상 도메인의 특수성을 반영한 사전학습의 가치를 정량적으로 입증합니다.

**팀 협업의 성과**

PM으로서 60일간의 개발 기간 내에 다음을 달성했습니다:

- YOLOv8n + RT-DETR WBF 앙상블 (Sensitivity 95.5%)
- DenseNet121 + Swin Transformer Early-fusion (AUC 0.9553)
- XGBoost 기반 혈액검사 분석 (PR-AUC 0.9784, TyG Index 신규 발견)
- 최종 RMI 기반 위험도 판정 시스템 완성

특히 폐쇄망 환경이라는 제약 속에서 팀원들과 체계적으로 문제를 해결하면서, 각자의 시행착오가 팀 전체의 학습 자산이 될 수 있음을 경험했습니다. 
이러한 협업 방식과 투명한 문제 해결 과정이 제한된 리소스 속에서도 목표 달성을 가능하게 한 핵심 요소였습니다.

---

## 📁 폴더 구조

```
ovariancdss/
├── backend/                              # FastAPI 백엔드
│   ├── main.py                           # 메인 서버 진입점
│   ├── auth.py                           # 인증 처리
│   ├── config.py                         # 설정
│   ├── db.py                             # 데이터베이스 연결
│   ├── patients.py                       # 환자 정보 조회
│   ├── predict.py                        # AI 분석 요청
│   ├── gpu_inference_server.py           # GPU 서버 연동
│   ├── requirements.txt
│   │
│   ├── ultrasound/                       # 초음파 AI 모듈
│   │   ├── detection/
│   │   │   ├── yolov8n_inference.py
│   │   │   ├── rtdetr_inference.py
│   │   │   └── wbf_ensemble.py           # Weighted Box Fusion
│   │   ├── classification/
│   │   │   ├── densenet_swin.py
│   │   │   └── inference.py
│   │   └── utils.py
│   │
│   └── dist/                        # 혈액검사 XGBoost 모듈
│       ├── trainer.py                    # XGBoost 훈련
│       ├── clinical_advanced.py          # 전처리 (TyG Index)
│       ├── preprocessor.py               # 정규화
│       ├── inference.py                  # 추론
│       ├── models/
│       │   └── final_xgboost_tyg_model.pkl
│       ├── data/
│       │   ├── chemo_training_dataset.csv
│       │   └── ovarian_cancer_note_normalization35.csv
│       └── requirements.txt
│
├── src/                                  # Next.js 프론트엔드
│   ├── app/
│   │   ├── layout.jsx
│   │   ├── page.jsx
│   │   ├── globals.css
│   │   ├── login/page.jsx
│   │   └── (dashboard)/
│   │       ├── layout.jsx
│   │       ├── cdss/page.jsx             # CDSS 판정 화면
│   │       ├── pacs/page.jsx             # 초음파 뷰어
│   │       ├── patients/
│   │       │   ├── register/page.jsx
│   │       │   └── [id]/page.jsx
│   │       ├── rmi/page.jsx
│   │       └── reports/page.jsx
│   │
│   ├── components/
│   │   ├── Header.jsx
│   │   ├── Sidebar.jsx
│   │   ├── BboxOverlay.jsx               # 초음파 박스 오버레이
│   │   ├── PrivateRoute.jsx
│   │   └── RiskBadge.jsx
│   │
│   └── lib/
│       ├── api.js
│       ├── AuthContext.jsx
│       └── mockData.js
│
├── workspace_pth/                        # AI 모델 가중치 (폐쇄망)
│   ├── yolov8n_best.pt
│   ├── rtdetr_best.pt
│   ├── classification_best_auc.pth
│   ├── benign_subtype_best.pth
│   └── malignant_subtype_best.pth
│
├── node_modules/                         # Node 의존성 (자동 생성)
├── package.json
├── package-lock.json
├── next.config.mjs
├── jsconfig.json
├── postcss.config.mjs
├── .env                                  # 환경 변수 (미포함)
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 실행 방법

### 사전 준비
- Node.js, Python 3.10+
- `.env.example` 참고해서 환경 변수 설정

### 백엔드 실행 (포트 8001)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 프론트엔드 실행 (포트 3003)
```bash
npm install
npm run dev
```

### 접속
- 프론트엔드: http://localhost:3003
- 백엔드 API: http://localhost:8001

---

## 📊 모델 정보

### 초음파 AI 모델 (박현주)

**탐지 모델**: YOLOv8n + RT-DETR (WBF Ensemble)
- 성능: Recall 95.47%, F1 0.900
- 학습 데이터: 14,130장 초음파 이미지
- 개발 전략: 5가지 모델 비교 후 앙상블 선택

**분류 모델**: DenseNet121 + Swin Transformer (Early-fusion)
- 성능: AUC 0.9553, Sensitivity 82.76%
- 개발 전략: 8가지 모델 비교 후 CNN+Transformer 상호보완 구조 선택
- FIGO Stage 분류: 1-2기 vs 3-4기

**서브타입 분류**
- 양성 Subtype AUC: 0.9114 (Teratoma, Serous, Mucinous 등)
- 악성 Subtype AUC: 0.9081 (Serous, Clear-cell 등)

### 혈액검사 분석 모델

**XGBoost 모델** (송대영)
- PR-AUC: 0.9784 (TyG Index 포함)
- 주요 피처: CA-125, TyG Index, 나이, 폐경 여부

---

## GPU 추론 서버 (박현주 설계)

**서버**: http://192.168.0.47:9001
- GPU: RTX 5090 × 2
- CUDA: 12.8
- Conda: team2_sono2 (Python 3.10)

**모델 가중치 경로**
- 탐지: `/home/team2/ova-cdss/models/runs/yolov8n_aihub/weights/best.pt`
- 분류: `/home/team2/ova-cdss/models/runs/classification_densenet_swin_3class_seed{1-5}/best_auc.pth`

---

## 시스템 아키텍처 (박현주 PM 설계)

```
의료진 입력
    ↓
PACS 자동 매핑
    ↓
FastAPI 오케스트레이션 (박현주 설계)
    ├─ 초음파 AI (GPU Server)
    │   └─ 탐지 → 분류 → 서브타입 (계층적 파이프라인)
    └─ XGBoost 분석
    ↓
RMI 점수 계산
    ↓
최종 위험도 판정 (저/중/고)
    ↓
의료진 CDSS 화면
```

---

## 📚 모델 선택 근거 (참고 논문)

1. MICCAI 2024: SAMUS (Segment Anything Model for Ultrasound)
2. CVPR 2024: RT-DETR (Real-Time Detection Transformer)
3. Frontiers in AI 2025: 난소암 초음파 AI 감지 메타분석 (44편 통합)

---

## 한계점 및 향후 개선

1. **환자 단위 데이터 분리**: 이미지 단위 → 환자 ID 기준으로 완전 분리
2. **기기 특화 학습**: 여러 초음파 기계 데이터 추가 학습
3. **악성 서브타입**: 데이터 부족 → AI-HUB 추가 데이터 신청
4. **경계 종양**: 별도 클래스 추가 (4분류 → 5분류)
5. **모델 해석가능성**: Grad-CAM을 임상 용어로 해석 제공

---

## 📞 문의

- **박현주** (PM, AI Lead): qkrguswn04@gmail.com
- **송대영** (ML): snow8832@naver.com
- **이다영** (BE/FE): dy4591@naver.com

- **Project Detail** : https://app.notion.com/p/OVA-LINK-CDSS-34fc849cdbb580e0a47fd3cee06a3977?source=copy_link

---

## 라이선스

© 2026 Team 3inyong. 미래융합교육원 4기 교육 프로젝트.

**멘토**: 건양대학교병원 의료데이터센터 황필동 박사님

**감사의 말**: MMOTU, MIMIC-IV, AI-HUB 데이터셋 제공
