"""
db.py — 엔진·공유 상수·헬퍼 (다른 모듈이 이 파일에서 import)

실제 쿼리 함수는 역할별 파일에 있음:
  patients.py  — 환자 목록·상세·검사결과·등록·의뢰서
  rmi.py       — RMI 이력·저장, 스크리닝 상태
  auth.py      — 사용자 인증·비밀번호·프로필
  init.py      — 커스텀 테이블 초기화 (서버 시작 시 1회)
"""

from __future__ import annotations

import datetime
import math

from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool

from config import (
    DB_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT,
    MIMIC_HOSP_SCHEMA, MIMIC_ICU_SCHEMA,
    VITALS_ITEMIDS,
)

# ── 스키마 상수 ───────────────────────────────────────────────────────────────
_CORE = "mimic_core"
_OVA  = MIMIC_HOSP_SCHEMA

# ── 검사항목 메타 (단위·참고범위) ──────────────────────────────────────────────
_LAB_META: dict[str, dict] = {
    "CA-125":                           {"unit": "U/mL",  "lo": 0,    "hi": 35,    "display": "CA-125"},
    "Glucose":                          {"unit": "mg/dL", "lo": 70,   "hi": 99,    "display": "Glucose"},
    "Triglycerides":                    {"unit": "mg/dL", "lo": 0,    "hi": 149,   "display": "Triglycerides"},
    "Albumin":                          {"unit": "g/dL",  "lo": 3.5,  "hi": 5.0,   "display": "Albumin"},
    "Alanine Aminotransferase (ALT)":   {"unit": "U/L",   "lo": 7,    "hi": 56,    "display": "ALT"},
    "Aspartate Aminotransferase (AST)": {"unit": "U/L",   "lo": 10,   "hi": 40,    "display": "AST"},
    "Urea Nitrogen (BUN)":              {"unit": "mg/dL", "lo": 7,    "hi": 20,    "display": "BUN"},
    "Hemoglobin":                       {"unit": "g/dL",  "lo": 12.0, "hi": 16.0,  "display": "Hemoglobin"},
    "HDL Cholesterol":                  {"unit": "mg/dL", "lo": 40,   "hi": 9999,  "display": "HDL", "ref": "≥40"},
    "Platelet Count":                   {"unit": "K/μL",  "lo": 150,  "hi": 400,   "display": "Platelet"},
    "INR(PT)":                          {"unit": "",      "lo": 0.8,  "hi": 1.2,   "display": "PT-INR"},
    "White Blood Cells":                {"unit": "K/μL",  "lo": 4.5,  "hi": 11.0,  "display": "WBC"},
    "Creatinine":                       {"unit": "mg/dL", "lo": 0.5,  "hi": 1.1,   "display": "Creatinine"},
}

# ── risk_level / status SQL 변환 ──────────────────────────────────────────────
_RISK_CASE = """
    CASE r.risk_level
        WHEN 'High Risk'     THEN 'HIGH'
        WHEN 'Moderate Risk' THEN 'MODERATE'
        WHEN 'Low Risk'      THEN 'LOW'
        ELSE CASE
            WHEN r.rmi_score >= 200 THEN 'HIGH'
            WHEN r.rmi_score >= 25  THEN 'MODERATE'
            ELSE 'LOW'
        END
    END
""".strip()

_STATUS_CASE = """
    CASE ova_s.status
        WHEN 'NEW'    THEN '신규'
        WHEN '분석중' THEN '관찰중'
        ELSE COALESCE(ova_s.status, '신규')
    END
""".strip()

# ── 엔진 ──────────────────────────────────────────────────────────────────────
engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=False,
)

@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _):
    dbapi_conn.execute(
        f"SET search_path TO public, {MIMIC_HOSP_SCHEMA}, {MIMIC_ICU_SCHEMA}"
    )


# ── 공유 헬퍼 ─────────────────────────────────────────────────────────────────

def _sanitize(row: dict) -> dict:
    """float NaN → None (JSON 직렬화 불가)."""
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}


def _fmt_datetime(dt) -> str | None:
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d %H:%M') if hasattr(dt, 'strftime') else str(dt)[:16]


def _fmt_date(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)[:10]


# ── 헬스체크 ──────────────────────────────────────────────────────────────────

def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
