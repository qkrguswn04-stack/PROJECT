"""
OVA-LINK Inference Pipeline
- DICOM 로드 → 전처리 → Detection → Classification → Grad-CAM
- CPU/GPU 전환: DEVICE 변수 하나로 관리
"""

import os
import io
import base64
import numpy as np
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import pydicom
import timm
import cv2

from ultralytics import YOLO  # YOLOv8
# RT-DETR은 ultralytics에 포함
from ensemble_boxes import weighted_boxes_fusion

# ============================================================
# 설정
# ============================================================
DEVICE = "cpu"  # GPU 전환 시 "cuda" 로 변경

MODEL_BASE = r"D:\dev\workspace_proj\ovariancdss\workspace_pth\pth_file\runs"

# Detection 가중치
YOLO_WEIGHT   = f"{MODEL_BASE}/yolov8n_aihub/weights/best.pt"
RTDETR_WEIGHT = f"{MODEL_BASE}/rtdetr_aihub-2/weights/best.pt"

# Classification seeds
CLS_SEEDS     = [1, 2, 3, 4, 5]
BENIGN_SEEDS  = [1, 2, 3, 4, 5]
MALIGNANT_SEEDS = [2, 4, 7, 8, 9]

# 클래스 정의
CLS_CLASSES = ["benign", "malignant_early", "malignant_late"]
BENIGN_CLASSES  = ["teratoma", "endometrioid", "mucinous", "serous", "etc"]
MALIGNANT_CLASSES = ["serous", "clear_cell", "endometrioid", "mucinous", "etc"]

IMG_SIZE = 224

# ============================================================
# 전처리
# ============================================================
TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# ============================================================
# DICOM 로드 → PIL Image
# ============================================================
def load_dicom(dicom_path: str) -> Image.Image:
    """DICOM 파일 → PIL RGB Image"""
    ds = pydicom.dcmread(dicom_path)
    pixel_array = ds.pixel_array.astype(np.float32)

    # 윈도우 레벨 정규화
    pixel_min = pixel_array.min()
    pixel_max = pixel_array.max()
    if pixel_max > pixel_min:
        pixel_array = (pixel_array - pixel_min) / (pixel_max - pixel_min) * 255
    pixel_array = pixel_array.astype(np.uint8)

    img = Image.fromarray(pixel_array)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

# ============================================================
# 전처리 (Detection용 - 학습 시와 동일)
# ============================================================
def preprocess_for_detection(img: Image.Image) -> Image.Image:
    """학습 시 aihub_preprocessing.py와 동일한 전처리"""
    img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = img_np.shape[:2]

    # STEP 1: 텍스트/마커 제거
    gray_for_marker = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    marker_mask = np.zeros_like(gray_for_marker)
    top_boundary    = int(h * 0.15)
    bottom_boundary = int(h * 0.85)
    _, thresh_top    = cv2.threshold(gray_for_marker[:top_boundary, :],    245, 255, cv2.THRESH_BINARY)
    _, thresh_bottom = cv2.threshold(gray_for_marker[bottom_boundary:, :], 245, 255, cv2.THRESH_BINARY)
    marker_mask[:top_boundary, :]    = thresh_top
    marker_mask[bottom_boundary:, :] = thresh_bottom
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    marker_mask = cv2.dilate(marker_mask, kernel, iterations=1)
    mask_pixel_ratio = (np.sum(marker_mask == 255) / marker_mask.size) * 100
    if mask_pixel_ratio < 4.0:
        img_np = cv2.inpaint(img_np, marker_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

    # STEP 2: 그레이스케일 + CLAHE
    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    img_np = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # STEP 3: Letterbox 패딩 (640x640)
    target = 640
    scale = min(target / w, target / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img_np, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    final_img = np.zeros((target, target, 3), dtype=np.uint8)
    x_off = (target - new_w) // 2
    y_off = (target - new_h) // 2
    final_img[y_off:y_off+new_h, x_off:x_off+new_w] = resized

    return Image.fromarray(cv2.cvtColor(final_img, cv2.COLOR_BGR2RGB))


# ============================================================
# DenseNet + Swin Early-fusion 모델 (학습 코드와 동일)
# ============================================================
class DenseNetSwinFusion(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.densenet = timm.create_model(
            "densenet121", pretrained=False, num_classes=0, global_pool="avg"
        )
        densenet_dim = self.densenet.num_features

        self.swin = timm.create_model(
            "swin_tiny_patch4_window7_224",
            pretrained=False, num_classes=0, global_pool="avg"
        )
        swin_dim = self.swin.num_features
        fused_dim = densenet_dim + swin_dim  # ← 이 줄이 classifier보다 위에 있어야 함

        self.classifier = nn.Sequential(
            nn.LayerNorm(fused_dim),
            nn.Dropout(0.3),
            nn.Linear(fused_dim, 512),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        f_dense = self.densenet(x)
        f_swin  = self.swin(x)
        return self.classifier(torch.cat([f_dense, f_swin], dim=1))

def pil_to_base64(img: Image.Image, fmt="PNG") -> str:
    """PIL Image → base64 문자열 (FE img src용)"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ============================================================
# 모델 로드 (앙상블용 여러 seed)
# ============================================================
def load_ensemble_models(weight_paths: list, num_classes: int) -> list:
    """여러 seed 가중치 로드 → 모델 리스트 반환"""
    models = []
    for wp in weight_paths:
        if not os.path.exists(wp):
            print(f"⚠️  가중치 없음: {wp}")
            continue
        model = DenseNetSwinFusion(num_classes=num_classes)
        state = torch.load(wp, map_location=DEVICE)
        # state_dict 키 정리
        if "model_state_dict" in state:
            state = state["model_state_dict"]
        model.load_state_dict(state, strict=False)
        model.to(DEVICE)
        model.eval()
        models.append(model)
        print(f"✅ 로드 완료: {wp}")
    return models

def ensemble_predict(models: list, tensor: torch.Tensor) -> np.ndarray:
    """앙상블 추론 → 평균 softmax 확률 반환"""
    probs_list = []
    with torch.no_grad():
        for model in models:
            logits = model(tensor)
            probs  = F.softmax(logits, dim=1).cpu().numpy()
            probs_list.append(probs)
    return np.mean(probs_list, axis=0)[0]  # shape: (num_classes,)

# ============================================================
# Detection (YOLOv8 + RT-DETR WBF 앙상블)
# ============================================================
_yolo_model   = None
_rtdetr_model = None

def get_detection_models():
    global _yolo_model, _rtdetr_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model   = YOLO(YOLO_WEIGHT)
        _rtdetr_model = YOLO(RTDETR_WEIGHT)  # RT-DETR도 ultralytics로 로드
    return _yolo_model, _rtdetr_model

def run_detection(img: Image.Image) -> dict:
    """
    YOLOv8 + RT-DETR WBF 앙상블 탐지
    반환: { detected, bbox, confidence, size_cm }
    """
    yolo, rtdetr = get_detection_models()
    w, h = img.size

    boxes_list, scores_list, labels_list = [], [], []

    for model in [yolo, rtdetr]:
        results = model.predict(img, device=DEVICE, verbose=False)
        if len(results[0].boxes) == 0:
            boxes_list.append([])
            scores_list.append([])
            labels_list.append([])
            continue

        boxes  = results[0].boxes.xyxyn.cpu().numpy().tolist()  # 정규화 bbox
        scores = results[0].boxes.conf.cpu().numpy().tolist()
        labels = results[0].boxes.cls.cpu().numpy().tolist()

        boxes_list.append(boxes)
        scores_list.append(scores)
        labels_list.append(labels)

    if not any(boxes_list):
        return {"detected": False, "bbox": None, "confidence": 0.0, "size_cm": None}

    # WBF 앙상블
    fused_boxes, fused_scores, _ = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        iou_thr=0.5, skip_box_thr=0.3
    )

    if len(fused_boxes) == 0:
        return {"detected": False, "bbox": None, "confidence": 0.0, "size_cm": None}

    best_idx  = np.argmax(fused_scores)
    best_box  = fused_boxes[best_idx]   # [x1, y1, x2, y2] normalized
    best_conf = float(fused_scores[best_idx])

    # 픽셀 크기 → cm 변환 (초음파 이미지 기준 약 0.05cm/px 가정)
    px_per_cm = 20.0
    box_w_cm  = round((best_box[2] - best_box[0]) * w / px_per_cm, 1)
    box_h_cm  = round((best_box[3] - best_box[1]) * h / px_per_cm, 1)
    max_cm    = round(max(box_w_cm, box_h_cm), 1)

    return {
        "detected":   True,
        "bbox":       best_box.tolist(),
        "confidence": round(best_conf * 100, 1),
        "size_w":     box_w_cm,
        "size_h":     box_h_cm,
        "size_max":   max_cm,
    }

# ============================================================
# Classification 모델 캐시
# ============================================================
_cls_models      = None
_benign_models   = None
_malignant_models = None

def get_cls_models():
    global _cls_models
    if _cls_models is None:
        paths = [
            f"{MODEL_BASE}/classification_densenet_swin_3class_seed{s}/best_sensitivity.pth"
            for s in CLS_SEEDS
        ]
        _cls_models = load_ensemble_models(paths, num_classes=3)
    return _cls_models

def get_benign_models():
    global _benign_models
    if _benign_models is None:
        paths = [
            f"{MODEL_BASE}/classification_densenet_swin_3class_seed{s}_benign/best_auc.pth"
            for s in BENIGN_SEEDS
        ]
        _benign_models = load_ensemble_models(paths, num_classes=5)
    return _benign_models

def get_malignant_models():
    global _malignant_models
    if _malignant_models is None:
        paths = [
            f"{MODEL_BASE}/classification_densenet_swin_3class_seed{s}_malignant/best_auc.pth"
            for s in MALIGNANT_SEEDS
        ]
        _malignant_models = load_ensemble_models(paths, num_classes=5)
    return _malignant_models

# ============================================================
# Grad-CAM
# ============================================================
class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.gradients = None
        self.activations = None
        target_layer.register_forward_hook(self._save_activation)
        target_layer.register_backward_hook(self._save_gradient)

    def _save_activation(self, module, input, output):
        self.activations = output.detach()

    def _save_gradient(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def generate(self, tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        output = self.model(tensor)
        self.model.zero_grad()
        output[0, class_idx].backward()

        weights = self.gradients.mean(dim=[2, 3], keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        cam = F.interpolate(cam, size=(IMG_SIZE, IMG_SIZE), mode="bilinear", align_corners=False)
        cam = cam.squeeze().cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        return cam

def generate_gradcam_image(img: Image.Image, model: nn.Module, class_idx: int) -> str:
    target_layer = model.densenet.features.denseblock4.denselayer16.conv2
    gradcam = GradCAM(model, target_layer)

    tensor = TRANSFORM(img).unsqueeze(0).to(DEVICE)
    tensor.requires_grad_(True)

    cam = gradcam.generate(tensor, class_idx)

    import matplotlib.cm as mpl_cm

    # CAM을 원본 이미지 크기로 리사이즈
    cam_resized = Image.fromarray((cam * 255).astype(np.uint8)).resize(
        img.size, Image.BILINEAR
    )
    cam_np = np.array(cam_resized) / 255.0

    heatmap = mpl_cm.jet(cam_np)[:, :, :3]
    heatmap = (heatmap * 255).astype(np.uint8)
    heatmap_img = Image.fromarray(heatmap)

    # 원본 이미지와 동일한 크기로 오버레이
    overlay = Image.blend(img.convert("RGB"), heatmap_img, alpha=0.4)
    return pil_to_base64(overlay)

# ============================================================
# 메인 파이프라인
# ============================================================
def run_pipeline(dicom_path: str) -> dict:
    # 1. DICOM 로드
    img = load_dicom(dicom_path)

    # 2. Detection 전처리 (학습 시와 동일)
    img_base64 = pil_to_base64(img)  # ← 원본 DICOM 이미지
    img_preprocessed = preprocess_for_detection(img)

    # 3. Detection (전처리된 이미지 사용)
    det = run_detection(img_preprocessed)

    # 4. Classification (3class)
    tensor = TRANSFORM(img_preprocessed).unsqueeze(0).to(DEVICE)
    cls_probs = ensemble_predict(get_cls_models(), tensor)
    # [benign, borderline, malignant]
    benign_prob    = round(float(cls_probs[0]) * 100, 1)
    malignant_prob = round((float(cls_probs[1]) + float(cls_probs[2])) * 100, 1)
    pred_class     = int(np.argmax(cls_probs))  # 0=benign, 1=malignant_early, 2=malignant_late

    # 5. Subtype 분류
    if pred_class == 0:  # benign
        sub_probs   = ensemble_predict(get_benign_models(), tensor)
        subtype_idx = int(np.argmax(sub_probs))
        subtype     = BENIGN_CLASSES[subtype_idx]
        sub_conf    = round(float(sub_probs[subtype_idx]) * 100, 1)
    elif pred_class == 2:  # malignant
        sub_probs   = ensemble_predict(get_malignant_models(), tensor)
        subtype_idx = int(np.argmax(sub_probs))
        subtype     = MALIGNANT_CLASSES[subtype_idx]
        sub_conf    = round(float(sub_probs[subtype_idx]) * 100, 1)
    else:  # malignant_early (pred_class == 1)
        sub_probs = ensemble_predict(get_malignant_models(), tensor)
        subtype_idx = int(np.argmax(sub_probs))
        subtype = MALIGNANT_CLASSES[subtype_idx]
        sub_conf = round(float(sub_probs[subtype_idx]) * 100, 1)

    # 6. FIGO 병기 (malignant_prob 기반 추정)
    if pred_class == 0:  # benign
        stage = None
        stage_conf = None
    elif pred_class == 1:  # 악성_조기
        stage = "early"
        stage_conf = round(float(cls_probs[1]) * 100, 1)
    else:  # 악성_후기
        stage = "late"
        stage_conf = round(float(cls_probs[2]) * 100, 1)

    # 7. Grad-CAM (3class 모델 첫 번째 seed 사용)
    gradcam_b64 = None
    try:
        cls_model_0 = get_cls_models()[0]
        gradcam_b64 = generate_gradcam_image(img_preprocessed, cls_model_0, pred_class)
    except Exception as e:
        print(f"⚠️  Grad-CAM 생성 실패: {e}")

    # run_pipeline() 내부에 임시 추가
    print(f"pred_class: {pred_class}, stage: {stage}, subtype: {subtype}")

    return {
        # 원본 이미지 (FE 뷰어용)
        "original_image": img_base64,

        # Detection
        "detected":    det["detected"],
        "bbox":        det.get("bbox"),
        "tumor_size_w":   det.get("size_w"),
        "tumor_size_h":   det.get("size_h"),
        "tumor_size_max": det.get("size_max"),
        "tumor_location": None,  # 추후 bbox 위치 기반 추정 가능

        # Classification
        "benign_prob":    benign_prob,
        "malignant_prob": malignant_prob,

        # Subtype
        "subtype":            subtype,
        "subtype_confidence": sub_conf,

        # FIGO
        "stage":            stage,
        "stage_confidence": stage_conf,

        # 역추적 (subtype 기반)
        "multilocular": subtype in ["mucinous", "serous"],        # etc → False
        "solid_areas": subtype in ["clear_cell", "endometrioid", "serous", "dermoid"] or pred_class != 0,  # etc → False
        "bilateral":    stage == "late",
        "ascites":      stage == "late",
        "peritoneal_mets": stage == "late",

        # Grad-CAM
        "gradcam_url": gradcam_b64,
    }
