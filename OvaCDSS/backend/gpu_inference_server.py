"""
OVA-LINK GPU 추론 서버
- 메인 백엔드(main.py)가 호출하는 별도 API. GPU 서버(Ubuntu)에 단독으로 띄워서 사용.
- 로직은 inference.py와 동일, DEVICE만 cuda로, MODEL_BASE만 Ubuntu 경로로 변경.

실행 방법 (GPU 서버, Ubuntu):
    pip install fastapi uvicorn python-multipart torch torchvision timm pydicom \
                opencv-python-headless ultralytics ensemble-boxes pillow numpy matplotlib
    uvicorn gpu_inference_server:app --host 0.0.0.0 --port 9001

메인 백엔드(main.py)에서 호출하는 쪽:
    POST http://<GPU서버IP>:9001/infer
    multipart/form-data, key="file" (DICOM 바이너리)
    → main.py의 run_inference()가 로컬 run_pipeline() 대신
      requests.post(GPU_SERVER_URL + "/infer", files={"file": dcm_bytes}) 로 바꿔야 함
"""

import os
import io
import base64
import tempfile
import numpy as np
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import pydicom
import timm
import cv2

from fastapi import FastAPI, UploadFile, File, HTTPException

from ultralytics import YOLO  # YOLOv8
from ensemble_boxes import weighted_boxes_fusion

# ============================================================
# 설정
# ============================================================
DEVICE = "cuda"  # GPU 서버이므로 cuda 고정 (GPU 없으면 "cpu"로)

MODEL_BASE = "/home/team2/ova-cdss/models/runs"

# Detection 가중치
YOLO_WEIGHT   = f"{MODEL_BASE}/yolov8n_aihub/weights/best.pt"
RTDETR_WEIGHT = f"{MODEL_BASE}/rtdetr_aihub-2/weights/best.pt"

# Classification seeds
CLS_SEEDS     = [1, 2, 3, 4, 5]
BENIGN_SEEDS  = [1, 2, 3, 4, 5]
MALIGNANT_SEEDS = [2, 4, 7, 8, 9]

# 클래스 정의
BENIGN_CLASSES  = ["teratoma", "endometrioid", "mucinous", "serous", "etc"]
MALIGNANT_CLASSES = ["serous", "clear_cell", "endometrioid", "mucinous", "etc"]

IMG_SIZE = 224

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
    ds = pydicom.dcmread(dicom_path)
    pixel_array = ds.pixel_array.astype(np.float32)

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
    img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = img_np.shape[:2]

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

    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    img_np = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

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
# DenseNet + Swin Early-fusion 모델
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
        fused_dim = densenet_dim + swin_dim

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
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ============================================================
# 모델 로드 (앙상블용 여러 seed)
# ============================================================
def load_ensemble_models(weight_paths: list, num_classes: int) -> list:
    models = []
    for wp in weight_paths:
        if not os.path.exists(wp):
            print(f"⚠️  가중치 없음: {wp}")
            continue
        model = DenseNetSwinFusion(num_classes=num_classes)
        state = torch.load(wp, map_location=DEVICE)
        if "model_state_dict" in state:
            state = state["model_state_dict"]
        model.load_state_dict(state, strict=False)
        model.to(DEVICE)
        model.eval()
        models.append(model)
        print(f"✅ 로드 완료: {wp}")
    return models

def ensemble_predict(models: list, tensor: torch.Tensor) -> np.ndarray:
    probs_list = []
    with torch.no_grad():
        for model in models:
            logits = model(tensor)
            probs  = F.softmax(logits, dim=1).cpu().numpy()
            probs_list.append(probs)
    return np.mean(probs_list, axis=0)[0]

# ============================================================
# Detection (YOLOv8 + RT-DETR WBF 앙상블)
# ============================================================
_yolo_model   = None
_rtdetr_model = None

def get_detection_models():
    global _yolo_model, _rtdetr_model
    if _yolo_model is None:
        _yolo_model   = YOLO(YOLO_WEIGHT)
        _rtdetr_model = YOLO(RTDETR_WEIGHT)
    return _yolo_model, _rtdetr_model

def run_detection(img: Image.Image) -> dict:
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

        boxes  = results[0].boxes.xyxyn.cpu().numpy().tolist()
        scores = results[0].boxes.conf.cpu().numpy().tolist()
        labels = results[0].boxes.cls.cpu().numpy().tolist()

        boxes_list.append(boxes)
        scores_list.append(scores)
        labels_list.append(labels)

    if not any(boxes_list):
        return {"detected": False, "bbox": None, "confidence": 0.0, "size_cm": None}

    fused_boxes, fused_scores, _ = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        iou_thr=0.5, skip_box_thr=0.3
    )

    if len(fused_boxes) == 0:
        return {"detected": False, "bbox": None, "confidence": 0.0, "size_cm": None}

    best_idx  = np.argmax(fused_scores)
    best_box  = fused_boxes[best_idx]
    best_conf = float(fused_scores[best_idx])

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

    cam_resized = Image.fromarray((cam * 255).astype(np.uint8)).resize(
        img.size, Image.BILINEAR
    )
    cam_np = np.array(cam_resized) / 255.0

    heatmap = mpl_cm.jet(cam_np)[:, :, :3]
    heatmap = (heatmap * 255).astype(np.uint8)
    heatmap_img = Image.fromarray(heatmap)

    overlay = Image.blend(img.convert("RGB"), heatmap_img, alpha=0.4)
    return pil_to_base64(overlay)

# ============================================================
# 메인 파이프라인
# ============================================================
def run_pipeline(dicom_path: str) -> dict:
    img = load_dicom(dicom_path)
    img_base64 = pil_to_base64(img)
    img_preprocessed = preprocess_for_detection(img)
    det = run_detection(img_preprocessed)

    tensor = TRANSFORM(img_preprocessed).unsqueeze(0).to(DEVICE)
    cls_probs = ensemble_predict(get_cls_models(), tensor)
    benign_prob    = round(float(cls_probs[0]) * 100, 1)
    malignant_prob = round((float(cls_probs[1]) + float(cls_probs[2])) * 100, 1)

    # ✅ pred_class/stage를 먼저 계산 (Subtype 분기보다 위로 이동)
    if float(cls_probs[0]) >= float(cls_probs[1]) + float(cls_probs[2]):
        pred_class = 0
        stage = None
        stage_conf = None
    elif float(cls_probs[1]) >= float(cls_probs[2]):
        pred_class = 1
        stage = "early"
        stage_conf = round(float(cls_probs[1]) * 100, 1)
    else:
        pred_class = 2
        stage = "late"
        stage_conf = round(float(cls_probs[2]) * 100, 1)

    # ✅ 이제 pred_class가 정의된 상태에서 Subtype 분기
    if pred_class == 0:
        sub_probs   = ensemble_predict(get_benign_models(), tensor)
        subtype_idx = int(np.argmax(sub_probs))
        subtype     = BENIGN_CLASSES[subtype_idx]
        sub_conf    = round(float(sub_probs[subtype_idx]) * 100, 1)
    else:
        sub_probs   = ensemble_predict(get_malignant_models(), tensor)
        subtype_idx = int(np.argmax(sub_probs))
        subtype     = MALIGNANT_CLASSES[subtype_idx]
        sub_conf    = round(float(sub_probs[subtype_idx]) * 100, 1)

    gradcam_b64 = None
    try:
        cls_model_0 = get_cls_models()[0]
        gradcam_b64 = generate_gradcam_image(img_preprocessed, cls_model_0, pred_class)
    except Exception as e:
        print(f"⚠️  Grad-CAM 생성 실패: {e}")

    return {
        "original_image": img_base64,
        "detected":    det["detected"],
        "bbox":        det.get("bbox"),
        "tumor_size_w":   det.get("size_w"),
        "tumor_size_h":   det.get("size_h"),
        "tumor_size_max": det.get("size_max"),
        "tumor_location": None,
        "benign_prob":    benign_prob,
        "malignant_prob": malignant_prob,
        "subtype":            subtype,
        "subtype_confidence": sub_conf,
        "stage":            stage,
        "stage_confidence": stage_conf,
        "multilocular": subtype in ["mucinous", "serous", "borderline"],
        "solid_areas": subtype in ["clear_cell", "endometrioid", "serous", "dermoid"] or pred_class != 0,
        "bilateral":      stage == "late",
        "ascites":        stage == "late",
        "peritoneal_mets": stage == "late",
        "gradcam_url": gradcam_b64,
    }

# ============================================================
# FastAPI 앱
# ============================================================
app = FastAPI(title="OVA-LINK GPU Inference Server", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "cuda_available": torch.cuda.is_available()}

@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    """
    메인 백엔드가 DICOM 파일을 multipart/form-data로 전송 → 추론 결과 JSON 반환
    """
    dcm_bytes = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".dcm", delete=False) as tmp:
        tmp.write(dcm_bytes)
        tmp_path = tmp.name

    try:
        result = run_pipeline(tmp_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
