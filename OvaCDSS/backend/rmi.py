"""
rmi.py — RMI 이력·저장, 스크리닝 상태 조회·변경
"""

from __future__ import annotations

from sqlalchemy import text

from db import engine, _OVA, _CORE, _RISK_CASE, _STATUS_CASE, _sanitize


def fetch_rmi_history(subject_id: int) -> list[dict]:
    """mimic_ova.ova_rmi_scores (사전 적재) + public.ova_rmi_scores (계산기 입력) 통합."""
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT
                r.rmi_id        AS id,
                r.subject_id,
                r.hadm_id,
                r.ca125_value,
                r.us_score,
                r.m_factor      AS menopause_factor,
                r.rmi_score,
                {_RISK_CASE}    AS risk_level,
                r.calculated_at,
                NULL::text      AS notes
            FROM {_OVA}.ova_rmi_scores r
            WHERE r.subject_id = :subject_id
            UNION ALL
            SELECT
                id, subject_id, hadm_id, ca125_value, us_score,
                menopause_factor, rmi_score, risk_level, calculated_at, notes
            FROM public.ova_rmi_scores
            WHERE subject_id = :subject_id
            ORDER BY calculated_at DESC
        """), {"subject_id": subject_id})
        return [_sanitize(dict(r._mapping)) for r in rows]


def insert_rmi_score(
    subject_id: int, ca125_value: float, us_score: int,
    menopause_factor: int, risk_level: str,
    hadm_id: int | None = None, notes: str | None = None,
) -> dict:
    rmi_score = ca125_value * us_score * menopause_factor
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO public.ova_rmi_scores
                (subject_id, hadm_id, ca125_value, us_score, menopause_factor, rmi_score, risk_level, notes)
            VALUES (:subject_id, :hadm_id, :ca125_value, :us_score, :menopause_factor, :rmi_score, :risk_level, :notes)
            RETURNING id, subject_id, hadm_id, ca125_value, us_score,
                      menopause_factor, rmi_score, risk_level, calculated_at, notes
        """), {
            "subject_id": subject_id, "hadm_id": hadm_id,
            "ca125_value": ca125_value, "us_score": us_score,
            "menopause_factor": menopause_factor, "rmi_score": rmi_score,
            "risk_level": risk_level, "notes": notes,
        }).fetchone()
        return dict(row._mapping)


def fetch_screening_status(subject_id: int) -> dict | None:
    """public 우선, 없으면 mimic_ova에서 읽어 통일된 형식으로 반환."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, subject_id, status, updated_at, updated_by, notes
            FROM public.ova_screening_status WHERE subject_id = :subject_id
        """), {"subject_id": subject_id}).fetchone()
        if row:
            return dict(row._mapping)

        row = conn.execute(text(f"""
            SELECT
                status_id   AS id,
                subject_id,
                {_STATUS_CASE} AS status,
                last_updated   AS updated_at,
                NULL::text     AS updated_by,
                NULL::text     AS notes
            FROM {_OVA}.ova_screening_status ova_s
            WHERE subject_id = :subject_id
        """), {"subject_id": subject_id}).fetchone()
        return dict(row._mapping) if row else None


def upsert_screening_status(
    subject_id: int, status: str,
    updated_by: str | None = None, notes: str | None = None,
) -> dict:
    """public.ova_screening_status에 upsert (사용자 변경 이력 보존)."""
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO public.ova_screening_status (subject_id, status, updated_at, updated_by, notes)
            VALUES (:subject_id, :status, now(), :updated_by, :notes)
            ON CONFLICT (subject_id) DO UPDATE SET
                status     = EXCLUDED.status,
                updated_at = now(),
                updated_by = EXCLUDED.updated_by,
                notes      = EXCLUDED.notes
            RETURNING id, subject_id, status, updated_at, updated_by, notes
        """), {
            "subject_id": subject_id, "status": status,
            "updated_by": updated_by, "notes": notes,
        }).fetchone()
        return dict(row._mapping)
