"""
patients.py — 환자 목록·상세·검사결과·등록·의뢰서
"""

from __future__ import annotations

import datetime
from collections import defaultdict

from sqlalchemy import text

from db import (
    engine, _OVA, _CORE,
    _RISK_CASE, _STATUS_CASE, _LAB_META,
    _sanitize, _fmt_date,
)
from rmi import upsert_screening_status


# ── 검사 항목 엔트리 생성 헬퍼 ────────────────────────────────────────────────

def _make_lab_entry(label: str, val: float, unit_override: str | None = None, recorded_at: str = '—') -> dict:
    meta = _LAB_META.get(label, {"unit": unit_override or "—", "lo": None, "hi": None})
    lo, hi = meta.get("lo"), meta.get("hi")
    if lo is not None and hi is not None:
        flag      = 'high' if val > hi else ('low' if val < lo else 'normal')
        ref_range = meta.get("ref") or f"{lo}–{hi}"
    else:
        flag, ref_range = 'normal', '—'
    return {
        'test_name':    label,
        'display_name': meta.get("display", label),
        'value':        round(val, 2),
        'unit':         unit_override or meta.get("unit", "—"),
        'ref_range':    ref_range,
        'status':       flag,
        'recorded_at':  recorded_at,
    }


# 12개 필수 검사 itemid (미보유 환자 제외)
_REQUIRED_LAB_ITEMIDS = "50882,50931,51000,50862,50878,50861,51006,51222,50904,51265,51237,51301"
_REQUIRED_LAB_COUNT   = 12

# ova_lab_uploads 짧은 이름 → d_labitems canonical 이름 정규화
_UPLOAD_NAME_MAP: dict[str, str] = {
    'AST':      'Aspartate Aminotransferase (AST)',
    'ALT':      'Alanine Aminotransferase (ALT)',
    'BUN':      'Urea Nitrogen (BUN)',
    'HDL':      'HDL Cholesterol',
    'Platelet': 'Platelet Count',
    'PT-INR':   'INR(PT)',
    'WBC':      'White Blood Cells',
}


# ── 환자 목록 ─────────────────────────────────────────────────────────────────

def fetch_screening_patients(page: int = 1, limit: int = 20) -> dict:
    """
    mimic_core 기존 환자 중 필수 12개 검사 항목 보유자 + mimic_ova 신규 등록 환자 UNION.
    반환: { data, total, page, limit, total_pages }
    """
    offset = (page - 1) * limit
    sql = text(f"""
        WITH lab_complete AS (
            -- 12개 검사 항목을 모두 보유한 subject_id만 추출
            SELECT subject_id
            FROM {_CORE}.labevents
            WHERE itemid IN ({_REQUIRED_LAB_ITEMIDS})
              AND valuenum IS NOT NULL
            GROUP BY subject_id
            HAVING COUNT(DISTINCT itemid) = {_REQUIRED_LAB_COUNT}
        ),
        latest_rmi AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, hadm_id, ca125_value, us_score,
                m_factor, rmi_score, risk_level, calculated_at
            FROM {_OVA}.ova_rmi_scores
            ORDER BY subject_id, calculated_at DESC
        ),
        upload_ca125 AS (
            -- ova_rmi_scores에 CA-125 없을 때 폴백
            SELECT DISTINCT ON (subject_id)
                subject_id,
                value AS ca125_value
            FROM public.ova_lab_uploads
            WHERE test_name = 'CA-125' AND value IS NOT NULL
            ORDER BY subject_id, recorded_date DESC NULLS LAST, id DESC
        ),
        base AS (
            -- 기존 환자 (mimic_core)
            SELECT
                p.subject_id,
                p.gender,
                p.anchor_age                        AS age,
                NULL::integer                        AS anchor_year,
                a.hadm_id,
                NULL::timestamptz                    AS admittime,
                COALESCE(r.ca125_value, uc.ca125_value) AS ca125_value,
                r.us_score,
                r.m_factor                           AS menopause_factor,
                COALESCE(
                    r.rmi_score,
                    CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                         THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END
                )                                    AS rmi_score,
                CASE
                    WHEN r.subject_id IS NULL THEN NULL
                    WHEN COALESCE(r.rmi_score,
                         CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                              THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END) >= 200 THEN 'HIGH'
                    WHEN COALESCE(r.rmi_score,
                         CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                              THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END) >= 25  THEN 'MODERATE'
                    ELSE 'LOW'
                END                                  AS risk_level,
                r.calculated_at                      AS rmi_calculated_at,
                COALESCE(
                    pub_s.status,
                    {_STATUS_CASE}
                )                                    AS status,
                COALESCE(pub_s.updated_at, ova_s.last_updated) AS status_updated_at,
                NULL::text                           AS patient_name
            FROM {_CORE}.patients p
            JOIN lab_complete lc              ON p.subject_id = lc.subject_id
            LEFT JOIN (
                SELECT DISTINCT ON (subject_id) subject_id, hadm_id
                FROM {_CORE}.admissions
                ORDER BY subject_id, hadm_id DESC
            ) a                               ON p.subject_id = a.subject_id
            LEFT JOIN latest_rmi r            ON p.subject_id = r.subject_id
            LEFT JOIN upload_ca125 uc         ON p.subject_id = uc.subject_id
            LEFT JOIN {_OVA}.ova_screening_status ova_s ON p.subject_id = ova_s.subject_id
            LEFT JOIN public.ova_screening_status pub_s  ON p.subject_id = pub_s.subject_id

            UNION ALL

            -- 신규 등록 환자 (mimic_ova, subject_id >= 90000001)
            SELECT
                p2.subject_id,
                p2.gender,
                p2.anchor_age                        AS age,
                p2.anchor_year,
                a2.hadm_id,
                a2.admittime,
                COALESCE(r.ca125_value, uc.ca125_value) AS ca125_value,
                r.us_score,
                r.m_factor                           AS menopause_factor,
                COALESCE(
                    r.rmi_score,
                    CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                         THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END
                )                                    AS rmi_score,
                CASE
                    WHEN r.subject_id IS NULL THEN NULL
                    WHEN COALESCE(r.rmi_score,
                         CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                              THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END) >= 200 THEN 'HIGH'
                    WHEN COALESCE(r.rmi_score,
                         CASE WHEN COALESCE(r.ca125_value, uc.ca125_value) IS NOT NULL AND r.m_factor IS NOT NULL
                              THEN 1 * r.m_factor * COALESCE(r.ca125_value, uc.ca125_value) END) >= 25  THEN 'MODERATE'
                    ELSE 'LOW'
                END                                  AS risk_level,
                r.calculated_at                      AS rmi_calculated_at,
                COALESCE(pub_s.status, '신규')       AS status,
                pub_s.updated_at                     AS status_updated_at,
                pi.name                              AS patient_name
            FROM {_OVA}.patients p2
            JOIN {_OVA}.admissions a2       ON p2.subject_id = a2.subject_id
            LEFT JOIN latest_rmi r          ON p2.subject_id = r.subject_id
            LEFT JOIN upload_ca125 uc       ON p2.subject_id = uc.subject_id
            LEFT JOIN public.ova_screening_status pub_s ON p2.subject_id = pub_s.subject_id
            LEFT JOIN public.ova_patient_info pi     ON p2.subject_id = pi.subject_id
            WHERE p2.subject_id >= 90000001
        )
        SELECT *, COUNT(*) OVER() AS total_count
        FROM base
        WHERE subject_id NOT IN (
            SELECT subject_id FROM public.ova_excluded_patients
        )
        ORDER BY
            status_updated_at DESC NULLS LAST,
            rmi_calculated_at DESC NULLS LAST,
            subject_id DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(sql, {"limit": limit, "offset": offset})]

    total = int(rows[0]["total_count"]) if rows else 0
    rows = [_sanitize({k: v for k, v in r.items() if k != "total_count"}) for r in rows]

    return {
        "data": rows,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


def fetch_landing_stats() -> dict:
    """
    로그인 페이지 통계 카드용 집계.
    - total: 필수 12개 검사 보유 환자 수 (+ 신규 등록)
    - high_risk_pct: HIGH 위험도 비율 (rmi_score 기준)
    - rmi_avg: 전체 평균 RMI 점수 (NULL 제외)
    """
    sql = text(f"""
        WITH lab_complete AS (
            SELECT subject_id
            FROM {_CORE}.labevents
            WHERE itemid IN ({_REQUIRED_LAB_ITEMIDS})
              AND valuenum IS NOT NULL
            GROUP BY subject_id
            HAVING COUNT(DISTINCT itemid) = {_REQUIRED_LAB_COUNT}
        ),
        latest_rmi AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, rmi_score, risk_level
            FROM {_OVA}.ova_rmi_scores
            ORDER BY subject_id, calculated_at DESC
        ),
        base AS (
            SELECT
                r.rmi_score,
                CASE
                    WHEN r.rmi_score IS NULL THEN NULL
                    WHEN r.rmi_score >= 200 THEN 'HIGH'
                    WHEN r.rmi_score >= 25  THEN 'MODERATE'
                    ELSE 'LOW'
                END AS risk_level
            FROM {_CORE}.patients p
            JOIN lab_complete lc ON p.subject_id = lc.subject_id
            LEFT JOIN latest_rmi r ON p.subject_id = r.subject_id

            UNION ALL

            SELECT
                r2.rmi_score,
                CASE
                    WHEN r2.rmi_score IS NULL THEN NULL
                    WHEN r2.rmi_score >= 200 THEN 'HIGH'
                    WHEN r2.rmi_score >= 25  THEN 'MODERATE'
                    ELSE 'LOW'
                END AS risk_level
            FROM {_OVA}.patients p2
            LEFT JOIN latest_rmi r2 ON p2.subject_id = r2.subject_id
            WHERE p2.subject_id >= 90000001
        )
        SELECT
            COUNT(*)                                            AS total,
            COUNT(*) FILTER (WHERE risk_level = 'HIGH')        AS high_count,
            COUNT(*) FILTER (WHERE risk_level IS NOT NULL)      AS risk_known,
            ROUND(AVG(rmi_score) FILTER (WHERE rmi_score IS NOT NULL))::int AS rmi_avg
        FROM base
    """)
    with engine.connect() as conn:
        row = dict(conn.execute(sql).mappings().one())
    total      = int(row["total"])
    high_count = int(row["high_count"])
    risk_known = int(row["risk_known"])
    rmi_avg    = int(row["rmi_avg"]) if row["rmi_avg"] is not None else None
    high_pct   = round(high_count / risk_known * 100) if risk_known else 0
    return {
        "total":         total,
        "high_risk_pct": high_pct,
        "high_count":    high_count,
        "rmi_avg":       rmi_avg,
    }


# patients.py 에 추가할 헬퍼
def _shape_patient_detail(raw: dict, subject_id: int) -> dict:
    """BE raw row → FE id/page.jsx 기대 구조로 변환"""

    # labResultsByDate는 별도 fetch
    lab_data = fetch_labs_by_date(subject_id)

    # CA-125: labevents 최신값 우선, 없으면 ova_rmi_scores 폴백
    lab_ca125 = None
    if lab_data:
        for entry in lab_data[0].get("results", []):
            if entry.get("test_name") == "CA-125":
                lab_ca125 = entry.get("value")
                break

    # M스코어: ova_patient_info.menopause boolean 우선, 없으면 m_factor 폴백
    menopause_val = raw.get("menopause")
    if menopause_val is True:
        computed_m_factor = 3
    elif menopause_val is False:
        computed_m_factor = 1
    else:
        computed_m_factor = raw.get("menopause_factor")

    # RMI 서브객체
    rmi = {
        "us_score": raw.get("us_score"),   # COALESCE(cdss.us_u_score, rmi.us_score) — null 가능
        "menopause_factor": computed_m_factor,
        "ca125_value": lab_ca125 if lab_ca125 is not None else raw.get("ca125_value"),
        "rmi_score": raw.get("rmi_score"),
        "risk_level": raw.get("risk_level"),
    }

    return {
        # FE 기대 필드명으로 매핑
        "subject_id": raw.get("subject_id"),
        "hadm_id": raw.get("hadm_id"),
        "pt_id": str(raw.get("subject_id", "")),
        "patient_name": raw.get("patient_name") or None,
        "patient_reg_no": str(raw.get("hadm_id") or "—"),
        "anchor_year": raw.get("anchor_year"),
        "birth_year": raw.get("birth_year"),   # YYYYMMDD — api.js _computeBirthYm()에서 파싱
        "diag_att_age": raw.get("age"),
        "gender": raw.get("gender"),
        "menopause": raw.get("menopause"),
        "symptoms": raw.get("symptoms"),
        "height": raw.get("height"),
        "weight": raw.get("weight"),
        "bmi": raw.get("bmi"),
        "risk_level": raw.get("risk_level"),
        "status": raw.get("status") or "신규",
        "last_updated": str(raw.get("status_updated_at") or raw.get("rmi_calculated_at") or "—")[:10],
        "rmi": rmi,
        "labResultsByDate": lab_data,
    }

# ── 환자 상세 ─────────────────────────────────────────────────────────────────

def fetch_patient_detail(subject_id: int) -> dict | None:
    """단일 환자 기본 정보 + 최신 RMI + 스크리닝 상태."""
    sql_core = text(f"""
        WITH latest_rmi AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, hadm_id,
                ca125_value, us_score, m_factor, rmi_score, risk_level, calculated_at
            FROM {_OVA}.ova_rmi_scores
            WHERE subject_id = :subject_id
            ORDER BY subject_id, calculated_at DESC
        ),
        latest_cdss AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, us_u_score
            FROM {_OVA}.ova_cdss_results
            WHERE subject_id = :subject_id
            ORDER BY subject_id, created_at DESC
        )
        SELECT
            p.subject_id,
            p.gender,
            p.anchor_age                        AS age,
            NULL::integer                        AS anchor_year,
            a.hadm_id,
            NULL::timestamptz                    AS admittime,
            r.ca125_value,
            COALESCE(cdss.us_u_score, r.us_score) AS us_score,
            r.m_factor                           AS menopause_factor,
            COALESCE(
                r.rmi_score,
                CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                     THEN 1 * r.m_factor * r.ca125_value END
            )                                    AS rmi_score,
            CASE
                WHEN COALESCE(r.rmi_score,
                     CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                          THEN 1 * r.m_factor * r.ca125_value END) >= 200 THEN 'HIGH'
                WHEN COALESCE(r.rmi_score,
                     CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                          THEN 1 * r.m_factor * r.ca125_value END) >= 25  THEN 'MODERATE'
                WHEN r.subject_id IS NOT NULL                              THEN 'LOW'
                ELSE NULL
            END                                  AS risk_level,
            r.calculated_at                      AS rmi_calculated_at,
            COALESCE(
                pub_s.status,
                {_STATUS_CASE}
            )                                    AS status,
            COALESCE(pub_s.updated_at, ova_s.last_updated) AS status_updated_at,
            pub_s.notes                          AS status_notes,
            pi.name                              AS patient_name,
            pi.birth_year,
            pi.symptoms,
            pi.menopause,
            pi.height,
            pi.weight,
            pi.bmi
        FROM {_CORE}.patients p
        LEFT JOIN {_CORE}.admissions a      ON p.subject_id = a.subject_id
        LEFT JOIN latest_rmi r              ON p.subject_id = r.subject_id
        LEFT JOIN latest_cdss cdss          ON p.subject_id = cdss.subject_id
        LEFT JOIN {_OVA}.ova_screening_status ova_s ON p.subject_id = ova_s.subject_id
        LEFT JOIN public.ova_screening_status pub_s  ON p.subject_id = pub_s.subject_id
        LEFT JOIN public.ova_patient_info pi         ON p.subject_id = pi.subject_id
        WHERE p.subject_id = :subject_id
    """)

    sql_ova = text(f"""
        WITH latest_rmi AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, hadm_id,
                ca125_value, us_score, m_factor, rmi_score, risk_level, calculated_at
            FROM {_OVA}.ova_rmi_scores
            WHERE subject_id = :subject_id
            ORDER BY subject_id, calculated_at DESC
        ),
        latest_cdss AS (
            SELECT DISTINCT ON (subject_id)
                subject_id, us_u_score
            FROM {_OVA}.ova_cdss_results
            WHERE subject_id = :subject_id
            ORDER BY subject_id, created_at DESC
        )
        SELECT
            p.subject_id,
            p.gender,
            p.anchor_age                         AS age,
            p.anchor_year,
            a.hadm_id,
            a.admittime,
            r.ca125_value,
            COALESCE(cdss.us_u_score, r.us_score) AS us_score,
            r.m_factor                           AS menopause_factor,
            COALESCE(
                r.rmi_score,
                CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                     THEN 1 * r.m_factor * r.ca125_value END
            )                                    AS rmi_score,
            CASE
                WHEN COALESCE(r.rmi_score,
                     CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                          THEN 1 * r.m_factor * r.ca125_value END) >= 200 THEN 'HIGH'
                WHEN COALESCE(r.rmi_score,
                     CASE WHEN r.ca125_value IS NOT NULL AND r.m_factor IS NOT NULL
                          THEN 1 * r.m_factor * r.ca125_value END) >= 25  THEN 'MODERATE'
                WHEN r.subject_id IS NOT NULL                              THEN 'LOW'
                ELSE NULL
            END                                  AS risk_level,
            r.calculated_at                      AS rmi_calculated_at,
            COALESCE(pub_s.status, '신규')       AS status,
            pub_s.updated_at                     AS status_updated_at,
            pub_s.notes                          AS status_notes,
            pi.name                              AS patient_name,
            pi.birth_year,
            pi.symptoms,
            pi.menopause,
            pi.height,
            pi.weight,
            pi.bmi
        FROM {_OVA}.patients p
        LEFT JOIN {_OVA}.admissions a       ON p.subject_id = a.subject_id
        LEFT JOIN latest_rmi r              ON p.subject_id = r.subject_id
        LEFT JOIN latest_cdss cdss          ON p.subject_id = cdss.subject_id
        LEFT JOIN public.ova_screening_status pub_s ON p.subject_id = pub_s.subject_id
        LEFT JOIN public.ova_patient_info pi         ON p.subject_id = pi.subject_id
        WHERE p.subject_id = :subject_id
    """)

    with engine.connect() as conn:
        row = conn.execute(sql_core, {"subject_id": subject_id}).fetchone()
        if row:
            return _shape_patient_detail(_sanitize(dict(row._mapping)), subject_id)  # ← 교체
        row = conn.execute(sql_ova, {"subject_id": subject_id}).fetchone()
        return _shape_patient_detail(_sanitize(dict(row._mapping)), subject_id) if row else None


# ── 검사 결과 ─────────────────────────────────────────────────────────────────

def fetch_labs_by_date(subject_id: int, max_rows: int = 2000) -> list[dict]:
    """
    mimic_core.labevents + public.ova_lab_uploads 통합.
    반환: [{date, results: [{test_name, value, unit, ref_range, status, recorded_at}]}]
    날짜 내림차순 정렬.
    """
    results_by_date: dict[str, list] = defaultdict(list)

    with engine.connect() as conn:
        core_rows = [dict(r._mapping) for r in conn.execute(text(f"""
            SELECT dl.label AS test_name, le.valuenum AS value
            FROM {_CORE}.labevents le
            JOIN {_CORE}.d_labitems dl ON le.itemid = dl.itemid
            WHERE le.subject_id = :subject_id AND le.valuenum IS NOT NULL
            LIMIT :max_rows
        """), {"subject_id": subject_id, "max_rows": max_rows})]

    if core_rows:
        date_key = _fmt_date(datetime.date.today())
        for r in core_rows:
            label = r.get('test_name') or ''
            val   = r.get('value')
            if not label or val is None:
                continue
            results_by_date[date_key].append(_make_lab_entry(label, round(float(val), 2)))

    with engine.connect() as conn:
        upload_rows = conn.execute(text("""
            SELECT test_name, value, unit, recorded_date
            FROM public.ova_lab_uploads
            WHERE subject_id = :subject_id
            ORDER BY recorded_date DESC NULLS LAST, id
        """), {"subject_id": subject_id}).fetchall()

    for r in upload_rows:
        val = r.value
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        date_key = _fmt_date(r.recorded_date) if r.recorded_date else '날짜 미상'
        canonical = _UPLOAD_NAME_MAP.get(r.test_name, r.test_name)
        results_by_date[date_key].append(
            _make_lab_entry(canonical, val, r.unit or None, date_key)
        )

    if not results_by_date:
        return []

    return [
        {'date': d, 'results': entries}
        for d, entries in sorted(results_by_date.items(), reverse=True)
    ]


def fetch_vitals_by_date(subject_id: int) -> list[dict]:
    """ICU chartevents 없음 → 빈 배열 반환."""
    return []


# ── 신규 환자 등록 ────────────────────────────────────────────────────────────

_MDAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def _birth_yyyymmdd(subject_id: int, birth_year_yyyy: int) -> int:
    """subject_id 기반 결정적 월/일로 YYYYMMDD 계산 (api.js와 동일 공식)."""
    month = (subject_id % 12) + 1
    day   = (subject_id // 12 % _MDAYS[month - 1]) + 1
    return birth_year_yyyy * 10000 + month * 100 + day


def register_patient(
    gender: str,
    birth_year: int,
    admission_type: str,
    admit_date: str,
    name: str | None = None,
    symptoms: str | None = None,
    menopause: bool | None = None,
    has_diabetes: bool = False,
    has_hypertension: bool = False,
    has_hyperlipidemia: bool = False,
    height: float | None = None,
    weight: float | None = None,
    bmi: float | None = None,
) -> dict:
    anchor_year = datetime.date.today().year
    anchor_age  = max(0, anchor_year - birth_year)

    with engine.begin() as conn:
        max_core_sid = conn.execute(text(f"SELECT COALESCE(MAX(subject_id), 0) FROM {_CORE}.patients")).scalar()
        max_ova_sid  = conn.execute(text(f"SELECT COALESCE(MAX(subject_id), 0) FROM {_OVA}.patients")).scalar()
        subject_id   = max(int(max_core_sid), int(max_ova_sid), 90000000) + 1

        max_core_hid = conn.execute(text(f"SELECT COALESCE(MAX(hadm_id), 0) FROM {_CORE}.admissions")).scalar()
        max_ova_hid  = conn.execute(text(f"SELECT COALESCE(MAX(hadm_id), 0) FROM {_OVA}.admissions")).scalar()
        hadm_id      = max(int(max_core_hid), int(max_ova_hid), 90000000) + 1

        conn.execute(text(f"""
            INSERT INTO {_OVA}.patients (subject_id, gender, anchor_age, anchor_year)
            VALUES (:sid, :gender, :age, :year)
        """), {"sid": subject_id, "gender": gender, "age": anchor_age, "year": anchor_year})

        conn.execute(text(f"""
            INSERT INTO {_OVA}.admissions (subject_id, hadm_id, admittime, admission_type)
            VALUES (:sid, :hid, :admittime, :atype)
        """), {
            "sid": subject_id, "hid": hadm_id,
            "admittime": admit_date, "atype": admission_type,
        })

        birth_year_full = _birth_yyyymmdd(subject_id, birth_year)

        conn.execute(text("""
            INSERT INTO public.ova_patient_info
                (subject_id, name, birth_year, symptoms, menopause,
                 has_diabetes, has_hypertension, has_hyperlipidemia,
                 height, weight, bmi)
            VALUES (:sid, :name, :birth_year, :symptoms, :menopause,
                    :has_diabetes, :has_hypertension, :has_hyperlipidemia,
                    :height, :weight, :bmi)
        """), {
            "sid": subject_id, "name": name or None,
            "birth_year": birth_year_full, "symptoms": symptoms or None,
            "menopause": menopause,
            "has_diabetes": has_diabetes,
            "has_hypertension": has_hypertension,
            "has_hyperlipidemia": has_hyperlipidemia,
            "height": height,
            "weight": weight,
            "bmi": bmi,
        })

    upsert_screening_status(subject_id, "신규")

    return {
        "subject_id":     subject_id,
        "hadm_id":        hadm_id,
        "gender":         gender,
        "anchor_age":     anchor_age,
        "anchor_year":    anchor_year,
        "birth_year":     birth_year,
        "name":           name,
        "admission_type": admission_type,
        "admittime":      admit_date,
    }


# ── 검사결과 파일 업로드 ──────────────────────────────────────────────────────

def insert_lab_uploads(
    subject_id: int,
    rows: list[dict],
    uploaded_by: str | None = None,
) -> int:
    """파싱된 검사결과 rows → public.ova_lab_uploads 저장. 삽입된 행 수 반환."""
    if not rows:
        return 0
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO public.ova_lab_uploads
                    (subject_id, test_name, value, unit, recorded_date, uploaded_by)
                VALUES (:sid, :test_name, :value, :unit, :recorded_date, :uploaded_by)
            """), {
                "sid":           subject_id,
                "test_name":     str(r.get("test_name", ""))[:100],
                "value":         r.get("value"),
                "unit":          (str(r.get("unit") or ""))[:50] or None,
                "recorded_date": r.get("recorded_date") or None,
                "uploaded_by":   uploaded_by,
            })
    return len(rows)


# ── 동반질환 (ICD 코드) ───────────────────────────────────────────────────────

def fetch_comorbidities(subject_id: int) -> dict:
    """
    기저질환 조회.
    - MIMIC 환자: mimic_core.diagnoses_icd (ICD 코드 기반)
    - 신규 등록 환자(>= 90000001): public.ova_patient_info (등록 시 입력값)
    """
    # 신규 등록 환자 — ova_patient_info에서 직접 읽기
    if subject_id >= 90000001:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT has_diabetes, has_hypertension, has_hyperlipidemia
                FROM public.ova_patient_info
                WHERE subject_id = :subject_id
            """), {"subject_id": subject_id}).fetchone()
        if row:
            return {
                "subject_id":        subject_id,
                "comorbidities":     [],
                "has_diabetes":      bool(row.has_diabetes),
                "has_hypertension":  bool(row.has_hypertension),
                "has_hyperlipidemia": bool(row.has_hyperlipidemia),
            }
        return {"subject_id": subject_id, "comorbidities": [],
                "has_diabetes": False, "has_hypertension": False, "has_hyperlipidemia": False}

    # MIMIC 환자 — diagnoses_icd ICD 코드 기반
    sql = text(f"""
        SELECT
            icd_code,
            icd_version,
            seq_num,
            CASE
                WHEN icd_code LIKE 'E11%' OR icd_code LIKE '250%' THEN '당뇨'
                WHEN icd_code LIKE 'I10%' OR icd_code LIKE '401%' THEN '고혈압'
                WHEN icd_code LIKE 'E78%' OR icd_code LIKE '272%' THEN '고지혈증'
            END AS condition
        FROM {_CORE}.diagnoses_icd
        WHERE subject_id = :subject_id
          AND (
              icd_code LIKE 'E11%' OR icd_code LIKE '250%'
           OR icd_code LIKE 'I10%' OR icd_code LIKE '401%'
           OR icd_code LIKE 'E78%' OR icd_code LIKE '272%'
          )
        ORDER BY seq_num
    """)
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(sql, {"subject_id": subject_id})]

    return {
        "subject_id":        subject_id,
        "comorbidities":     rows,
        "has_diabetes":      any(r["condition"] == "당뇨"    for r in rows),
        "has_hypertension":  any(r["condition"] == "고혈압"  for r in rows),
        "has_hyperlipidemia": any(r["condition"] == "고지혈증" for r in rows),
    }


# ── CDSS 분석 결과 조회 ───────────────────────────────────────────────────────

def fetch_cdss_result(subject_id: int) -> dict | None:
    """mimic_ova.ova_cdss_results에서 가장 최근 AI 분석 결과 반환."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT
                subject_id,
                us_malignancy_prob,
                us_tumor_detected,
                us_tumor_size_cm2,
                us_figo_stage,
                us_tumor_type,
                us_u_score,
                us_image_url,
                blood_malignancy_prob,
                overall_risk_level,
                created_at
            FROM {_OVA}.ova_cdss_results
            WHERE subject_id = :subject_id
            ORDER BY created_at DESC
            LIMIT 1
        """), {"subject_id": subject_id}).fetchone()
    return _sanitize(dict(row._mapping)) if row else None


# ── 의뢰서 ────────────────────────────────────────────────────────────────────

def cancel_referral(subject_id: int) -> dict | None:
    """최신 의뢰를 '취소'로 변경 + 스크리닝 상태를 '검토완료'로 되돌림."""
    with engine.begin() as conn:
        row = conn.execute(text(f"""
            UPDATE {_OVA}.ova_referrals
            SET status = '취소', updated_at = now()
            WHERE id = (
                SELECT id FROM {_OVA}.ova_referrals
                WHERE subject_id = :subject_id
                ORDER BY issued_at DESC
                LIMIT 1
            )
            RETURNING id, subject_id, status
        """), {"subject_id": subject_id}).fetchone()
    if not row:
        return None
    upsert_screening_status(subject_id, "검토완료")
    return dict(row._mapping)


def save_referral(
    subject_id: int,
    doctor_id: str,
    urgency: str,
    destination: str | None,
    content: str | None,
    hadm_id: int | None = None,
) -> dict:
    """mimic_ova.ova_referrals에 의뢰서 저장 + 상태를 '의뢰완료'로 업데이트."""
    with engine.begin() as conn:
        row = conn.execute(text(f"""
            INSERT INTO {_OVA}.ova_referrals
                (subject_id, hadm_id, doctor_id, urgency, destination, content, status)
            VALUES
                (:subject_id, :hadm_id, :doctor_id, :urgency, :destination, :content, '대기')
            RETURNING id, subject_id, issued_at
        """), {
            "subject_id":  subject_id,
            "hadm_id":     hadm_id,
            "doctor_id":   doctor_id,
            "urgency":     urgency,
            "destination": destination or None,
            "content":     content or None,
        }).fetchone()

    upsert_screening_status(subject_id, "의뢰완료", updated_by=doctor_id)
    return _sanitize(dict(row._mapping))



