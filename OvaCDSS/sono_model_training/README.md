# 🔬 OVA-LINK 초음파 AI 모델 학습 코드

난소암 조기진단을 위한 초음파 AI 모델 학습 코드. **탐지(Detection) → 분류(Classification)**의 2단계 계층적 파이프라인.

---

## 📁 폴더 구조

```
sono_model_training/
├── detection/              # 종양 탐지 모델
│   ├── train_yolov8.py     # YOLOv8n 학습
│   ├── train_rtdetr.py     # RT-DETR 학습
│   └── train_ensemble.py   # YOLOv8n + RT-DETR WBF 앙상블
│
├── classification/         # 종양 분류 모델
│   ├── densenet_swin_3.py         # DenseNet121 + Swin (최종 선택)
│   ├── swin_1.py                  # Swin Transformer 단독
│   └── classification_densenet_swin_malignant.py
│
├── utils/                  # 유틸리티
│   ├── label_utils.py      # 라벨 처리 함수
│   ├── build_labels.py     # 라벨 빌드
│   └── data.yaml           # 데이터 설정
│
├── data_check/             # 데이터 검증
├── requirements_aihub.txt  # AI-HUB 환경 의존성
└── README.md
```

---

## 🚀 학습 순서

### 1단계: 종양 탐지 (Detection)

```bash
cd detection/

# 베이스라인: YOLOv8n
python train_yolov8.py

# RT-DETR (Transformer 기반)
python train_rtdetr.py

# 최종: 앙상블
python train_ensemble.py
```

**결과**: Recall 95.47%, F1 0.9004

### 2단계: 종양 분류 (Classification)

```bash
cd classification/

# Swin Transformer 단독
python swin_1.py

# DenseNet121 + Swin Early-fusion (최종 선택)
python densenet_swin_3.py
```

**결과**: AUC 0.9553, Sensitivity 82.76%

---

## 📋 환경 설정

```bash
# AI-HUB 폐쇄망 환경 (권장)
conda create -n sonography_1 python=3.10
conda activate sonography_1

pip install -r requirements_aihub.txt
```

**주요 라이브러리**:
- PyTorch 2.5.1+cu121
- YOLOv8, RT-DETR
- DenseNet121, Swin Transformer

---

## 📊 데이터 설정

`utils/data.yaml` 파일에서 데이터 경로 설정:

```yaml
path: /path/to/dataset
train: images/train
val: images/val
nc: 1  # 클래스 수
names: ['tumor']
```

---

## 🎯 최종 모델

| 단계 | 모델 | 성능 |
|------|------|------|
| 탐지 | YOLOv8n + RT-DETR WBF | Recall 95.47%, F1 0.9004 |
| 분류 | DenseNet121 + Swin | AUC 0.9553, Sensitivity 82.76% |

---

## 💡 핵심 포인트

- **도메인 가중치의 중요성**: MMOTU 1,639장 (Recall 22.9%) → AI-HUB 도메인 가중치 (Recall 47.2%)
- **계층적 파이프라인**: 탐지 정확도가 분류 성능에 직접 영향
- **폐쇄망 환경**: 외부 라이브러리 없이 경로·버전 명시적 관리

---

## 🔗 관련 문서

- **프로젝트 전체**: [OVA-LINK GitHub](https://github.com/qkrguswn04-stack/PROJECT/tree/main/OvaCDSS)

---

**개발 기간**: 2026년 5월 11일 ~ 2026년 7월 9일 (60일)
