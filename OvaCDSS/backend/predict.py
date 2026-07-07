"""
predict.py — TyG XGBoost 모델 예측

입력 피처 순서 (모델 학습 시 고정):
  alb, alt, ast, bun, hb, hdl, plt, pt_inr, wbc, ca125, tyg_index

tyg_index = ln(TG × Glucose) / 2
"""

from __future__ import annotations

import math
import os
import pickle
from pathlib import Path

import numpy as np
from sqlalchemy import text

from db import engine, _CORE, _OVA

# ── 모델 로딩 (서버 시작 시 1회) ─────────────────────────────────────────────

_MODEL_PATH = Path(__file__).parent / "final_xgboost_tyg_model.pkl"

def _load_model():
    """모델이 학습 당시보다 더 최신 xgboost로 로드되면 XGBClassifier에
    gpu_id/use_label_encoder 등 신규 속성이 빠져 predict_proba가 AttributeError로
    죽는다. 새 인스턴스에 기존 __dict__를 덮어써 누락 속성을 기본값으로 채운다."""
    from xgboost import XGBClassifier

    with open(_MODEL_PATH, "rb") as f:
        loaded = pickle.load(f)

    model = XGBClassifier()
    model.__dict__.update(loaded.__dict__)
    return model

_model = _load_model()

# ── d_labitems label → 피처 키 매핑 ─────────────────────────────────────────
# 각 항목의 최신 valuenum을 가져와 피처로 사용

_LABEL_TO_FEAT = {
    "Albumin":                          "alb",
    "Alanine Aminotransferase (ALT)":   "alt",
    "Aspartate Aminotransferase (AST)": "ast",
    "Urea Nitrogen (BUN)":              "bun",
    "Hemoglobin":                       "hb",
    "HDL Cholesterol":                  "hdl",
    "Platelet Count":                   "plt",
    "INR(PT)":                          "pt_inr",
    "White Blood Cells":                "wbc",
    "CA-125":                           "ca125",
    "Triglycerides":                    "_tg",     # tyg_index 계산용 (직접 피처 아님)
    "Glucose":                          "_glucose", # tyg_index 계산용
}

_NEEDED_LABELS = list(_LABEL_TO_FEAT.keys())
_FEAT_ORDER    = ["alb", "alt", "ast", "bun", "hb", "hdl", "plt", "pt_inr", "wbc", "ca125", "tyg_index"]

# ova_lab_uploads 짧은 이름 → 피처 키 (신규 등록 환자 폴백용)
_UPLOAD_TO_FEAT = {
    "Albumin":      "alb",
    "ALT":          "alt",
    "AST":          "ast",
    "BUN":          "bun",
    "Hemoglobin":   "hb",
    "HDL":          "hdl",
    "Platelet":     "plt",
    "PT-INR":       "pt_inr",
    "WBC":          "wbc",
    "CA-125":       "ca125",
    "Triglycerides": "_tg",
    "Glucose":      "_glucose",
}
_UPLOAD_NAMES = list(_UPLOAD_TO_FEAT.keys())


def _fetch_latest_labs(subject_id: int) -> dict[str, float]:
    """mimic_core.labevents에서 피처별 평균값 조회 (날짜 컬럼 없음)."""
    placeholders = ", ".join(f"'{l}'" for l in _NEEDED_LABELS)
    sql = text(f"""
        SELECT dl.label, AVG(le.valuenum) AS valuenum
        FROM {_CORE}.labevents le
        JOIN {_CORE}.d_labitems dl ON le.itemid = dl.itemid
        WHERE le.subject_id = :subject_id
          AND le.valuenum IS NOT NULL
          AND dl.label IN ({placeholders})
        GROUP BY dl.label
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"subject_id": subject_id}).fetchall()

    vals: dict[str, float] = {}
    for r in rows:
        feat_key = _LABEL_TO_FEAT.get(r.label)
        if feat_key:
            vals[feat_key] = float(r.valuenum)

    # 피처 폴백 1: CA-125 → ova_rmi_scores
    if "ca125" not in vals:
        with engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT ca125_value FROM {_OVA}.ova_rmi_scores
                WHERE subject_id = :subject_id AND ca125_value IS NOT NULL
                ORDER BY calculated_at DESC NULLS LAST LIMIT 1
            """), {"subject_id": subject_id}).fetchone()
        if row and row.ca125_value is not None:
            vals["ca125"] = float(row.ca125_value)

    # 피처 폴백 2: 누락된 모든 피처 → ova_lab_uploads (신규 등록 환자)
    all_needed = set(_FEAT_ORDER) - {"tyg_index"} | {"_tg", "_glucose"}
    if all_needed - vals.keys():
        upload_placeholders = ", ".join(f"'{n}'" for n in _UPLOAD_NAMES)
        with engine.connect() as conn:
            rows2 = conn.execute(text(f"""
                SELECT test_name, AVG(value) AS value
                FROM public.ova_lab_uploads
                WHERE subject_id = :subject_id
                  AND test_name IN ({upload_placeholders})
                  AND value IS NOT NULL
                GROUP BY test_name
            """), {"subject_id": subject_id}).fetchall()
        for r in rows2:
            feat_key = _UPLOAD_TO_FEAT.get(r.test_name)
            if feat_key and feat_key not in vals:
                vals[feat_key] = float(r.value)

    return vals


def _build_result(subject_id: int, lab_vals: dict) -> dict:
    """lab_vals → 예측 결과 dict (단일·배치 공용)."""
    tg      = lab_vals.pop("_tg",      None)
    glucose = lab_vals.pop("_glucose", None)
    tyg_index: float | None = None
    if tg is not None and glucose is not None and tg > 0 and glucose > 0:
        tyg_index = math.log(tg * glucose) / 2

    lab_vals["tyg_index"] = tyg_index if tyg_index is not None else 0.0

    missing = [f for f in _FEAT_ORDER if not lab_vals.get(f)]
    feature_vec = np.array([[lab_vals.get(f) or 0.0 for f in _FEAT_ORDER]], dtype=np.float32)
    prob_mal = float(_model.predict_proba(feature_vec)[0][1])

    if prob_mal >= 0.7:   risk_tier = "HIGH"
    elif prob_mal >= 0.4: risk_tier = "MODERATE"
    else:                 risk_tier = "LOW"

    return {
        "subject_id":      subject_id,
        "probability":     round(prob_mal, 4),
        "probability_pct": round(prob_mal * 100, 1),
        "prediction":      "악성" if prob_mal >= 0.5 else "양성",
        "risk_tier":       risk_tier,
        "tyg_index":       round(tyg_index, 4) if tyg_index is not None else None,
        "features_used":   {f: round(lab_vals.get(f) or 0.0, 4) for f in _FEAT_ORDER},
        "missing_features": missing,
    }


def predict_batch(subject_ids: list[int]) -> list[dict]:
    """
    여러 환자 일괄 예측 — 쿼리 1회로 전체 처리.
    반환: [{ subject_id, probability_pct, risk_tier, ... }, ...]
    """
    if not subject_ids:
        return []

    placeholders_labels = ", ".join(f"'{l}'" for l in _NEEDED_LABELS)
    sid_list = ", ".join(str(s) for s in subject_ids)

    sql = text(f"""
        SELECT le.subject_id, dl.label, AVG(le.valuenum) AS valuenum
        FROM {_CORE}.labevents le
        JOIN {_CORE}.d_labitems dl ON le.itemid = dl.itemid
        WHERE le.subject_id IN ({sid_list})
          AND le.valuenum IS NOT NULL
          AND dl.label IN ({placeholders_labels})
        GROUP BY le.subject_id, dl.label
    """)

    # 피처 폴백 1: CA-125 → ova_rmi_scores
    sql_ca = text(f"""
        SELECT DISTINCT ON (subject_id)
            subject_id, ca125_value
        FROM {_OVA}.ova_rmi_scores
        WHERE subject_id IN ({sid_list})
          AND ca125_value IS NOT NULL
        ORDER BY subject_id, calculated_at DESC NULLS LAST
    """)

    # 피처 폴백 2: 누락된 모든 피처 → ova_lab_uploads (신규 등록 환자)
    upload_placeholders = ", ".join(f"'{n}'" for n in _UPLOAD_NAMES)
    sql_upload = text(f"""
        SELECT subject_id, test_name, AVG(value) AS value
        FROM public.ova_lab_uploads
        WHERE subject_id IN ({sid_list})
          AND test_name IN ({upload_placeholders})
          AND value IS NOT NULL
        GROUP BY subject_id, test_name
    """)

    labs_by_sid: dict[int, dict] = {sid: {} for sid in subject_ids}

    with engine.connect() as conn:
        for r in conn.execute(sql).fetchall():
            feat_key = _LABEL_TO_FEAT.get(r.label)
            if feat_key:
                labs_by_sid[r.subject_id][feat_key] = float(r.valuenum)

        for r in conn.execute(sql_ca).fetchall():
            sid = r.subject_id
            if "ca125" not in labs_by_sid.get(sid, {}):
                labs_by_sid[sid]["ca125"] = float(r.ca125_value)

        for r in conn.execute(sql_upload).fetchall():
            sid = r.subject_id
            feat_key = _UPLOAD_TO_FEAT.get(r.test_name)
            if feat_key and feat_key not in labs_by_sid.get(sid, {}):
                labs_by_sid[sid][feat_key] = float(r.value)

    return [_build_result(sid, labs_by_sid[sid]) for sid in subject_ids]


def predict_malignancy(subject_id: int) -> dict:
    """단일 환자 악성 종양 확률 예측."""
    return _build_result(subject_id, _fetch_latest_labs(subject_id))
