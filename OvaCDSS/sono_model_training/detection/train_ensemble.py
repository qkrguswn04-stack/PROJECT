# -*- coding: utf-8 -*-
from ultralytics import YOLO, RTDETR
import numpy as np
import os
import glob

def weighted_boxes_fusion(boxes_list, scores_list, labels_list, weights=None, iou_thr=0.5, skip_box_thr=0.0):
    if weights is None:
       weights = [1.0] * len(boxes_list)
       
    all_boxes, all_scores, all_labels, all_weights = [], [], [], []
    
    for i, (boxes, scores, labels) in enumerate(zip(boxes_list, scores_list, labels_list)):
        for box, score, label in zip(boxes, scores, labels):
            if score > skip_box_thr:
                all_boxes.append(box)
                all_scores.append(score * weights[i])
                all_labels.append(label)
                all_weights.append(weights[i])
                
    if not all_boxes:
        return [], [], []
        
    all_boxes = np.array(all_boxes)
    all_scores = np.array(all_scores)
    all_labels = np.array(all_labels)
    
    #IoU 계산 함수
    def iou(box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2-x1) * max(0, y2-y1)
        area1 = (box1[2]-box1[0]) * (box1[3]-box1[1])
        area2 = (box2[2]-box2[0]) * (box2[3]-box2[1])
        return inter / (area1 + area2 - inter + 1e-6)
        
    # 클러스터링 + 가중평균
    used = [False] * len(all_boxes)
    final_boxes, final_scores, final_labels = [], [], []
    
    # score 내림차순 정렬
    order = np.argsort(-all_scores)
    
    for i in order:
        if used[i]:
            continue
        cluster_boxes = [all_boxes[i]]
        cluster_scores = [all_scores[i]]
        cluster_labels = [all_labels[i]]
        used[i] = True
        
        for j in order:
            if used[j]:
                continue
            if all_labels[i] != all_labels[j]:
                continue
            if iou(all_boxes[i], all_boxes[j]) > iou_thr:
                cluster_boxes.append(all_boxes[j])
                cluster_scores.append(all_scores[j])
                cluster_labels.append(all_labels[j])
                used[j] = True
            
        cluster_boxes = np.array(cluster_boxes)
        cluster_scores = np.array(cluster_scores)
    
        #가중 평균
        weights_norm = cluster_scores / cluster_scores.sum()
        fused_box = (cluster_boxes * weights_norm[:, None]).sum(axis=0)
        fused_score = cluster_scores.mean()
        
        final_boxes.append(fused_box.tolist())
        final_scores.append(float(fused_score))
        final_labels.append(float(all_labels[i]))
        
    return final_boxes, final_scores, final_labels
    
                

# 경로 설정 
VAL_IMG_DIR = "/home/ubuntu/project/AI-HUB_preprocess/yolo_dataset/val/images"
VAL_LABEL_DIR = "/home/ubuntu/project/AI-HUB_preprocess/yolo_dataset/val/labels"

MODEL_YOLO_PATH = "/home/ubuntu/project/AI-HUB_preprocess/runs/yolov8n_aihub/weights/best.pt"
MODEL_RTDETR_PATH = "/home/ubuntu/project/AI-HUB_preprocess/runs/rtdetr_aihub-2/weights/best.pt"

# 모델 로드 
print("모델 로드 중..")
model_yolo = YOLO(MODEL_YOLO_PATH)
model_rtdetr = RTDETR(MODEL_RTDETR_PATH)
print("모델 로드 완료!!")

# 평가 
img_list = glob.glob(os.path.join(VAL_IMG_DIR, "*.png"))
print(f"평가 이미지: {len(img_list)}장")

all_pred_boxes = []
all_pred_scores = []
all_pred_labels = []
all_true_boxes = []
all_true_labels = []

WEIGHTS = [0.5, 0.5]
IOU_THR = 0.5
SKIP_BOX_THR = 0.25

for img_path in img_list:
    res_yolo = model_yolo.predict(img_path, device=0, conf=0.25, verbose=False)
    res_rtdetr = model_rtdetr.predict(img_path, device=0, conf=0.25, verbose=False)

    def get_boxes(result):
        if len(result[0].boxes) == 0:
            return np.zeros((0,4)), np.array([]), np.array([])
        boxes = result[0].boxes.xyxyn.cpu().numpy()
        scores = result[0].boxes.conf.cpu().numpy()
        labels = result[0].boxes.cls.cpu().numpy()
        return boxes, scores, labels

    boxes_y, scores_y, labels_y = get_boxes(res_yolo)
    boxes_r, scores_r, labels_r = get_boxes(res_rtdetr)

    boxes_wbf, scores_wbf, labels_wbf = weighted_boxes_fusion(
        [boxes_y.tolist(), boxes_r.tolist()],
        [scores_y.tolist(), scores_r.tolist()],
        [labels_y.tolist(), labels_r.tolist()],
        weights=WEIGHTS,
        iou_thr=IOU_THR,
        skip_box_thr=SKIP_BOX_THR
    )

    all_pred_boxes.append(boxes_wbf)
    all_pred_scores.append(scores_wbf)
    all_pred_labels.append(labels_wbf)

    label_path = img_path.replace('/images/', '/labels/').replace('.png', '.txt')
    true_boxes = []
    true_labels = []
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    cls = int(parts[0])
                    cx, cy, w, h = map(float, parts[1:])
                    x1 = cx - w/2
                    y1 = cy - h/2
                    x2 = cx + w/2
                    y2 = cy + h/2
                    true_boxes.append([x1, y1, x2, y2])
                    true_labels.append(cls)
    all_true_boxes.append(true_boxes)
    all_true_labels.append(true_labels)

# Recall carculation
tp = 0
fn = 0
fp = 0

for pred_boxes, pred_labels, true_boxes, true_labels in zip(
    all_pred_boxes, all_pred_labels, all_true_boxes, all_true_labels):

    matched = [False] * len(true_boxes)
    pred_matched = [False] * len(pred_boxes)
    
    for j, (pb, pl) in enumerate(zip(pred_boxes, pred_labels)):
        for i, (tb, tl) in enumerate(zip(true_boxes, true_labels)):
            if not matched[i] and int(pl) == tl:
                x1 = max(pb[0], tb[0])
                y1 = max(pb[1], tb[1])
                x2 = min(pb[2], tb[2])
                y2 = min(pb[3], tb[3])
                inter = max(0, x2-x1) * max(0, y2-y1)
                area_p = (pb[2]-pb[0]) * (pb[3]-pb[1])
                area_t = (tb[2]-tb[0]) * (tb[3]-tb[1])
                iou = inter / (area_p + area_t - inter + 1e-6)
                if iou >= 0.5:
                    matched[i] = True
                    pred_matched[j] = True
                    tp += 1
                    break
    
    fn += sum(1 for m in matched if not m)
    fp += sum(1 for m in pred_matched if not m)

recall = tp / (tp + fn + 1e-6)
precision = tp / (tp + fp + 1e-6)
f1 = 2 * (precision * recall) / (precision + recall + 1e-6)

print(f"\nWBF앙상블 최종 결과 (YOLOv8n + RT-DETR):")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")
print(f"F1 Score:  {f1:.4f}")
print(f"TP: {tp}, FP: {fp}, FN: {fn}")