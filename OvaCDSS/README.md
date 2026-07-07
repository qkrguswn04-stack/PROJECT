# OvarianCDSS

난소암 스크리닝/CDSS 웹 애플리케이션. 프론트엔드(Next.js) + 백엔드(FastAPI) + 팀 공용 PostgreSQL(mimic) 구조.

## 사전 준비

- Node.js, Python 3.10+
- `backend/.env`에 DB 접속 정보 등 환경 변수 필요 (`.env.example` 참고)
- DB는 팀 공용 서버(`192.168.0.33:5432`)를 사용하므로 별도 DB 설치 불필요


- ### node_modules 설치

프로젝트를 처음 받은 후 또는 SVN 업데이트 후에는 반드시 다음 명령어를 실행해서 의존성을 설치해야 합니다.

```bash
npm install
```

**중요**: `node_modules` 디렉토리는 SVN에 포함되지 않으므로, 프로젝트를 받으면 위 명령어로 자동 생성됩니다. SVN에 `node_modules`를 커밋하지 마세요.

## 백엔드 실행 (포트 8001)

```bash
cd backend
pip install -r requirements.txt   # 최초 1회
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

## 프론트엔드 실행 (포트 3003)

```bash
npm install   # 최초 1회
npm run dev
```

`package.json`의 `dev` 스크립트에 포트(3003)가 고정되어 있어 별도 옵션 없이 실행하면 됩니다.


## 프론트엔드 실행 (포트 3003)

```bash
npm install   # 최초 1회 (또는 의존성 업데이트 후)
npm run dev
```

**참고**: `node_modules`는 SVN에 포함되지 않습니다. 프로젝트를 처음 받거나 `package-lock.json`이 변경되면 반드시 `npm install`을 실행하세요.

`package.json`의 `dev` 스크립트에 포트(3003)가 고정되어 있어 별도 옵션 없이 실행하면 됩니다.

## 접속

- 프론트엔드: http://localhost:3003
- 백엔드 API: http://localhost:8001

## 환경 변수

- `.env` (프론트엔드 루트): `NEXT_PUBLIC_API_URL=http://localhost:8001`
- `backend/.env`: DB 접속 문자열 등 (`postgresql+psycopg://...`)

자세한 DB 스키마 구조, 알려진 데이터 특이사항, 작업 로그는 [CLAUDE.md](CLAUDE.md) 참고합니다.

---

# 프로젝트 상세 정보

## 프로젝트 개요

OVA-LINK는 1차 의료기관에서 난소암을 조기에 발견하고, 환자를 3차 의료기관으로 신속하게 연결하는 AI 기반 임상 의사결정 지원 시스템(CDSS)입니다.

**개발 기간**: 2026년 5월 11일 ~ 2026년 7월 9일 (60일)

**핵심 기능**: 초음파 이미지와 혈액검사 데이터를 결합하여 난소암 위험도를 자동으로 판정하고, 의료진의 의료 의사결정을 지원합니다.

---

## 주요 기능

### 환자 관리 (Patients)
- 신규 환자 등록 (간호사)
- 환자 검색 및 조회
- PACS 서버에서 자동으로 초음파 이미지 매핑

### 초음파 분석 (PACS)
- PACS 서버(Orthanc)에 저장된 초음파 이미지 뷰어
- AI 자동 탐지: 종양 위치 및 경계 박스 표시
- Grad-CAM 히트맵으로 집중도 시각화

### CDSS 판정 (Clinical Decision Support System)
- 초음파 AI 결과 (악성확률, FIGO 병기)
- 혈액검사 분석 결과 (TyG Index, CA-125)
- RMI 점수 자동 계산
- 최종 위험도 판정 (저/중/고)
- 상급전원 버튼 활성화

### 리포트 생성
- 분석 결과를 PACS 이미지와 함께 PDF 리포트 생성
- 의료진과 환자가 확인 가능한 형태로 제공

---

## 기술 스택

**Backend**
- FastAPI (Python 3.10)
- PostgreSQL
- Uvicorn

**Frontend**
- Next.js 14 (JavaScript/React)
- Tailwind CSS
- Node.js

**AI/ML**
- PyTorch (Deep Learning)
- YOLOv8n + RT-DETR (Object Detection)
- DenseNet121 + Swin Transformer (Image Classification)
- XGBoost (Tabular Data Analysis)

**Medical Infrastructure**
- Orthanc PACS Server (DICOM 표준)
- MIMIC-IV (임상 데이터)
- MMOTU (초음파 데이터)

---

## 폴더 구조

```
ovariancdss/
├── backend/                          # FastAPI 백엔드
│   ├── main.py                       # 메인 서버 진입점
│   ├── auth.py                       # 인증 처리
│   ├── config.py                     # 설정 파일
│   ├── db.py                         # 데이터베이스 연결
│   ├── patients.py                   # 환자 정보 조회 (PACS 연동)
│   ├── predict.py                    # AI 분석 요청
│   ├── rmi.py                        # RMI 점수 계산
│   ├── inference.py                  # 추론 로직
│   ├── gpu_inference_server.py        # GPU 서버 연동
│   ├── final_xgboost_tyg_model.pkl    # 혈액검사 XGBoost 모델
│   ├── requirements.txt               # Python 의존성
│   └── __pycache__/                  # 컴파일된 파이썬 파일
│
├── src/                              # Next.js 프론트엔드
│   ├── app/                          # Next.js 앱 라우터
│   │   ├── layout.jsx                # 루트 레이아웃
│   │   ├── page.jsx                  # 메인 페이지
│   │   ├── globals.css               # 글로벌 스타일
│   │   ├── middleware.ts             # 미들웨어
│   │   ├── login/page.jsx            # 로그인 페이지
│   │   └── (dashboard)/              # 대시보드 영역
│   │       ├── layout.jsx
│   │       ├── cdss/page.jsx         # CDSS 의료진 판정 화면
│   │       ├── pacs/page.jsx         # 초음파 이미지 뷰어
│   │       ├── patients/             # 환자 관리
│   │       │   ├── register/page.jsx # 환자 등록
│   │       │   └── [id]/page.jsx     # 환자 상세 조회
│   │       ├── screening/page.jsx    # 스크리닝 결과
│   │       ├── rmi/page.jsx          # RMI 점수 조회
│   │       └── reports/page.jsx      # 분석 리포트
│   │
│   ├── components/                   # React 재사용 컴포넌트
│   │   ├── Header.jsx                # 헤더
│   │   ├── Sidebar.jsx               # 사이드바
│   │   ├── BboxOverlay.jsx           # 초음파 이미지 박스 오버레이
│   │   ├── PrivateRoute.jsx          # 인증 라우트
│   │   ├── RegisterDrawer.jsx        # 환자 등록 드로어
│   │   ├── DateRangePicker.jsx       # 날짜 선택기
│   │   └── RiskBadge.jsx             # 위험도 배지
│   │
│   └── lib/                          # 유틸리티 및 설정
│       ├── api.js                    # API 호출 함수
│       ├── AuthContext.jsx           # 인증 상태 관리 (Context API)
│       └── mockData.js               # 테스트 데이터
│
├── public/                           # 정적 파일
│   ├── favicon.svg                   # 브라우저 탭 아이콘
│   ├── ovacdss_logo.png              # OVA-LINK 로고
│   ├── ovacdss_logo_01.png           # OVA-LINK 로고 (변형)
│   └── sample_labs.csv               # 샘플 혈액검사 데이터
│
├── node_modules/                     # Node.js 의존성 (자동 생성)
├── workspace_pth/                    # AI 모델 가중치 (폐쇄망 AI-HUB)
├── package.json                      # Node.js 의존성 정의
├── next.config.mjs                   # Next.js 설정
├── jsconfig.json                     # JavaScript 설정
├── postcss.config.mjs                # PostCSS 설정
├── .env                              # 환경 변수 (미포함)
├── .env.example                      # 환경 변수 템플릿
├── .gitignore                        # Git 무시 파일
├── README.md                         # 이 파일
└── batch_infer.py                    # 배치 추론 스크립트
```
## GPU 추론 서버 설정

### 서버 정보
- 주소: http://192.168.0.47:9001
- 호스트명: server301
- 사용자: team2
- GPU: RTX 5090 × 2
- CUDA: 12.8
- PyTorch: 2.12.0

### Conda 환경
- 환경명: team2_sono2
- Python: 3.10
- 활성화: `conda activate team2_sono2`

### 모델 가중치 경로 (GPU 서버)

**탐지 모델 (Detection)**
- YOLOv8n: `/home/team2/ova-cdss/models/runs/yolov8n_aihub/weights/best.pt`
- RT-DETR: `/home/team2/ova-cdss/models/runs/rtdetr_aihub-2/weights/best.pt`

**분류 모델 (Classification)**
- 악성/양성 판정: `/home/team2/ova-cdss/models/runs/classification_densenet_swin_3class_seed{1-5}/best_auc.pth`
- 양성 서브타입: `/home/team2/ova-cdss/models/runs/classification_densenet_swin_3class_seed{1-5}_benign/best_auc.pth`
- 악성 서브타입: `/home/team2/ova-cdss/models/runs/classification_densenet_swin_3class_seed{1-5}_malignant/best_auc.pth`

### 추론 서버 실행
```bash
conda activate team2_sono2
cd /home/team2/ova-cdss
python gpu_inference_server.py
```

---

## 팀원 역할 분담

### 박현주 - 초음파 AI (Deep Learning)
- 초음파 이미지 탐지 모델 (YOLOv8n + RT-DETR WBF Ensemble)
- 분류 모델 (DenseNet121 + Swin Transformer Early-fusion)
- 데이터 전처리 및 모델 성능 검증
- 프로젝트 매니저 및 AI 리드

### 송대영 - 혈액검사 분석 (Machine Learning)
- XGBoost 기반 위험도 예측 모델
- TyG Index 분석 및 통계적 유의성 검증
- MIMIC-IV 기반 메타데이터 분석

### 이다영 - 시스템 개발 (Backend/Frontend)
- FastAPI 백엔드: API 설계, PACS 연동, RMI 계산
- Next.js 프론트엔드: UI/UX 구현, 사용자 인증
- PostgreSQL 데이터베이스 설계 및 관리

---

## 모델 정보

### 초음파 AI 모델

**탐지 모델 (Detection): YOLOv8n + RT-DETR (WBF Ensemble)**
- YOLOv8n 가중치: `workspace_pth/pth_file/runs/yolov8n_aihub/weights/best.pt`
- RT-DETR 가중치: `workspace_pth/pth_file/runs/rtdetr_aihub-2/weights/best.pt`
- 성능: Recall 95.47%, F1 Score 0.900
- 학습 데이터: 14,130장 초음파 이미지

**분류 모델 (Classification): DenseNet121 + Swin Transformer (Early-fusion)**
- 악성/양성 판정: `workspace_pth/pth_file/runs/classification_densenet_swin_3class_seed{1-5}/best_auc.pth`
  - 성능: AUC 0.9553, Sensitivity 85.69%
  - FIGO Stage 분류: 1-2기 vs 3-4기

- 양성 서브타입 분류: `workspace_pth/pth_file/runs/classification_densenet_swin_3class_seed{1-5}_benign/best_auc.pth`
- 악성 서브타입 분류: `workspace_pth/pth_file/runs/classification_densenet_swin_3class_seed{1-5}_malignant/best_auc.pth`

### 혈액검사 분석 모델

**XGBoost 모델**
- 파일: `backend/final_xgboost_tyg_model.pkl`
- PR-AUC: 0.9784 (TyG Index 포함)
- 주요 피처: CA-125, TyG Index, 나이, 폐경 여부
- 학습 데이터: MIMIC-IV 임상 데이터

### 모델 로드 방식

초음파 AI 모델은 `gpu_inference_server.py`에서 관리합니다.
- GPU 추론 서버: http://192.168.0.47:9001
- 모델 가중치: 위 경로에서 자동으로 로드
- 실시간 추론: FastAPI 백엔드에서 요청 시 GPU 서버로 전달

### 검증 데이터셋

- **MMOTU**: 공개 난소 초음파 데이터 (1,639장)
- **MIMIC-IV**: 임상 메타데이터 기반 RMI 재검증

---

## 주요 API 엔드포인트

### 환자 정보
- `GET /api/patients/{pt_id}`: 환자 정보 조회
- `POST /api/patients/register`: 새 환자 등록

### AI 분석
- `POST /api/predict`: 초음파 AI 분석 요청
- `POST /api/xgboost/predict`: XGBoost 혈액검사 분석

### RMI 계산
- `POST /api/rmi/calculate`: RMI 점수 계산

### PACS 연동
- `GET /api/pacs/{pt_id}/images`: 환자 초음파 이미지 조회
- `POST /api/pacs/upload`: 새 DICOM 파일 업로드

---

## 시스템 아키텍처

### 데이터 흐름

```
의료진 입력 (환자번호)
    ↓
PACS 자동 매핑 (환자 ID 기준)
    ↓
FastAPI 백엔드 (orchestration)
    ├─ 초음파 AI 분석 (GPU Server)
    └─ XGBoost 분석
    ↓
RMI 점수 계산
    ↓
최종 위험도 판정
    ↓
의료진 CDSS 화면 표시
```

### 주요 컴포넌트

- **Frontend (Next.js)**: 사용자 인터페이스
- **Backend (FastAPI)**: API 서버 및 오케스트레이션
- **GPU Server**: 초음파 AI 모델 추론
- **PostgreSQL**: 환자 데이터 및 분석 결과 저장
- **PACS (Orthanc)**: 의료 이미지 저장소

---

## 한계점 및 향후 개선 방향

### 한계점 01: 환자 단위 데이터 분리 미적용
- **설명**: 현재는 이미지 단위로 train/val을 분리하여 같은 환자의 이미지가 양쪽에 포함될 수 있습니다.
- **개선방향**: 환자 ID 기준으로 완전히 독립적으로 분할하여 검증 신뢰도를 확보합니다.

### 한계점 02: 기기 특화 학습
- **설명**: AI-HUB 데이터가 특정 초음파 기계에서만 수집되었습니다.
- **개선방향**: 여러 병원의 다양한 초음파 기계 데이터로 재학습하여 기기 독립적인 일반화 성능을 확보합니다.

### 한계점 03: 악성 서브타입 성능 불안정
- **설명**: 악성 조기 데이터(768장) 부족 및 Val 극소로 인한 성능 편차가 발생합니다.
- **개선방향**: AI-HUB에서 추가 데이터를 신청하고 불균형 데이터 증강을 진행합니다.

### 한계점 04: 경계 종양 미분류
- **설명**: 현재는 양성/악성만 판정하고 경계 종양 카테고리가 없습니다.
- **개선방향**: 경계 종양 클래스를 추가하여 4분류 또는 5분류로 확장합니다.

### 한계점 05: 모델 해석가능성 부족
- **설명**: "왜 이 부위가 위험한가"를 의료 용어로 설명하지 못합니다.
- **개선방향**: Grad-CAM을 "종양 경계 불규칙", "내부 에코 이상" 등 임상 용어로 해석하여 제공합니다.

---

## 문의 및 지원

프로젝트에 관한 문의사항은 다음을 참고하세요:

- **프로젝트 매니저**: 박현주
- **개발 팀**: 송대영, 이다영
- **GitHub**: https://github.com/qkrguswn04/ovariancdss

---

## 라이선스

이 프로젝트는 미래융합교육원 4기 교육 프로젝트입니다.

**저작권**

© 2026 Team 3inyong
- 박현주 (AI Lead, Project Manager) - qkrguswn04@gmail.com
- 송대영 (Machine Learning) - snow8832@naver.com
- 이다영 (Backend/Frontend Development) - dy4591@naver.com

이 프로젝트의 모든 코드, 모델, 문서의 저작권은 위 팀원들에게 있습니다.

**사용 및 문의**

프로젝트 사용 또는 협업에 대한 문의사항은 위 팀원들에게 이메일로 연락 주시기 바랍니다.

---

---

## 감사의 말

- 멘토 : 건양대학교병원 의료데이터센터 황필동 박사님
- 미래융합교육원 (이앞길 선생님)
- MMOTU 초음파 데이터셋
- MIMIC-IV 임상 데이터셋
- AI-HUB 난소암 데이터