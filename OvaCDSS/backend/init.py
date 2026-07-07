"""
init.py — 서버 시작 시 1회 실행: 커스텀 테이블 생성 + 초기 데이터 시드
"""

from __future__ import annotations

from sqlalchemy import text

from config import MIMIC_HOSP_SCHEMA
from db import engine, _OVA
from auth import _hash_pw, _verify_pw, _INITIAL_USERS


def init_custom_tables() -> None:
    with engine.begin() as conn:

        # ── 사용자 테이블 ──────────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ova_users (
                id            SERIAL PRIMARY KEY,
                employee_id   VARCHAR(20)  NOT NULL UNIQUE,
                name          VARCHAR(50)  NOT NULL,
                role          VARCHAR(20)  NOT NULL CHECK (role IN ('doctor','nurse','admin')),
                password_hash TEXT         NOT NULL,
                created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
            )
        """))
        # COUNT(*)==0 방식은 테이블에 행이 하나라도 있으면 신규 계정 추가나
        # 손상된 해시 복구가 전혀 이뤄지지 않는 구조적 결함이 있었음.
        # 계정별로 존재 여부를 확인해:
        #   - 없으면 INSERT, 있지만 해시가 틀리면 UPDATE (시드 비밀번호 기준 복구)
        #   - 해시가 올바르면 그대로 유지 (사용자가 직접 바꾼 비밀번호 보존 안 됨 —
        #     시드 계정은 시스템 계정이므로 허용)
        for u in _INITIAL_USERS:
            row = conn.execute(text("""
                SELECT password_hash FROM public.ova_users WHERE employee_id = :eid
            """), {"eid": u["employee_id"]}).fetchone()

            if row is None:
                conn.execute(text("""
                    INSERT INTO ova_users (employee_id, name, role, password_hash)
                    VALUES (:eid, :name, :role, :hash)
                """), {
                    "eid":  u["employee_id"],
                    "name": u["name"],
                    "role": u["role"],
                    "hash": _hash_pw(u["pw"]),
                })
            elif not _verify_pw(u["pw"], row[0]):
                # 해시가 손상됐거나 비밀번호가 바뀐 경우 시드 값으로 복구
                conn.execute(text("""
                    UPDATE public.ova_users SET password_hash = :hash
                    WHERE employee_id = :eid
                """), {"hash": _hash_pw(u["pw"]), "eid": u["employee_id"]})

        # ── RMI 점수 (사용자 입력) ──────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ova_rmi_scores (
                id               SERIAL PRIMARY KEY,
                subject_id       INTEGER     NOT NULL,
                hadm_id          INTEGER,
                ca125_value      NUMERIC,
                us_score         INTEGER     CHECK (us_score IN (0, 1, 3)),
                menopause_factor INTEGER     CHECK (menopause_factor IN (1, 3)),
                rmi_score        NUMERIC,
                risk_level       VARCHAR(20) CHECK (risk_level IN ('HIGH','MODERATE','LOW')),
                calculated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                notes            TEXT
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_rmi_subject ON ova_rmi_scores(subject_id)
        """))

        # ── 스크리닝 상태 ──────────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ova_screening_status (
                id          SERIAL PRIMARY KEY,
                subject_id  INTEGER     NOT NULL UNIQUE,
                status      VARCHAR(20) NOT NULL
                            CHECK (status IN ('신규','관찰중','검토완료','의뢰완료')),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_by  VARCHAR(100),
                notes       TEXT
            )
        """))

        # 기존 CHECK 제약에 '의뢰완료' 포함 (이전 버전 호환)
        conn.execute(text("""
            DO $$
            DECLARE v_conname text;
            BEGIN
                SELECT conname INTO v_conname
                FROM pg_constraint c
                JOIN pg_class r ON r.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = r.relnamespace
                WHERE n.nspname = 'public'
                  AND r.relname = 'ova_screening_status'
                  AND c.contype = 'c'
                LIMIT 1;

                IF v_conname IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE public.ova_screening_status DROP CONSTRAINT '
                            || quote_ident(v_conname);
                END IF;

                EXECUTE $sql$
                    ALTER TABLE public.ova_screening_status
                    ADD CONSTRAINT ova_screening_status_status_check
                    CHECK (status IN ('신규','관찰중','검토완료','의뢰완료'))
                $sql$;
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """))

        # ── 초음파 이미지 ──────────────────────────────────────────────────
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_OVA}.ova_ultrasound (
                id           SERIAL       PRIMARY KEY,
                subject_id   INTEGER      NOT NULL,
                hadm_id      INTEGER,
                file_name    VARCHAR(255) NOT NULL,
                file_path    TEXT         NOT NULL,
                file_size    INTEGER,
                mime_type    VARCHAR(20)  NOT NULL
                             CHECK (mime_type IN ('image/png','image/jpeg')),
                uploaded_by  VARCHAR(20)  REFERENCES public.ova_users(employee_id),
                uploaded_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                notes        TEXT
            )
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_us_subject
            ON {_OVA}.ova_ultrasound(subject_id)
        """))

        # ── CDSS 분석 결과 ────────────────────────────────────────────────
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_OVA}.ova_cdss_results (
                id                    SERIAL       PRIMARY KEY,
                subject_id            INTEGER      NOT NULL,
                hadm_id               INTEGER,
                ultrasound_id         INTEGER
                                      REFERENCES {_OVA}.ova_ultrasound(id)
                                      ON DELETE SET NULL,
                rmi_score_id          INTEGER
                                      REFERENCES public.ova_rmi_scores(id)
                                      ON DELETE SET NULL,
                us_malignancy_prob    NUMERIC(5,2),
                us_tumor_detected     BOOLEAN,
                us_tumor_size_cm2     NUMERIC(8,2),
                us_u_score            INTEGER      CHECK (us_u_score BETWEEN 0 AND 10),
                us_figo_stage         VARCHAR(20),
                us_tumor_type         VARCHAR(50),
                blood_malignancy_prob NUMERIC(5,2),
                blood_risk_level      VARCHAR(20)
                                      CHECK (blood_risk_level IN ('HIGH','MODERATE','LOW')),
                overall_risk_level    VARCHAR(20)
                                      CHECK (overall_risk_level IN ('HIGH','MODERATE','LOW')),
                recommendation        VARCHAR(100),
                reviewed_by           VARCHAR(20)
                                      REFERENCES public.ova_users(employee_id),
                reviewed_at           TIMESTAMPTZ,
                model_version         VARCHAR(50),
                created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
                notes                 TEXT
            )
        """))
        conn.execute(text(f"""
            ALTER TABLE {_OVA}.ova_cdss_results
            ADD COLUMN IF NOT EXISTS us_image_url TEXT
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_cdss_subject
            ON {_OVA}.ova_cdss_results(subject_id)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_cdss_us
            ON {_OVA}.ova_cdss_results(ultrasound_id)
        """))

        # ── 의뢰서 ────────────────────────────────────────────────────────
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_OVA}.ova_referrals (
                id             SERIAL       PRIMARY KEY,
                subject_id     INTEGER      NOT NULL,
                hadm_id        INTEGER,
                cdss_result_id INTEGER
                               REFERENCES {_OVA}.ova_cdss_results(id)
                               ON DELETE SET NULL,
                doctor_id      VARCHAR(20)  NOT NULL
                               REFERENCES public.ova_users(employee_id),
                referral_type  VARCHAR(50),
                urgency        VARCHAR(20)  NOT NULL DEFAULT '일반'
                               CHECK (urgency IN ('일반','긴급','매우긴급')),
                destination    TEXT,
                content        TEXT,
                status         VARCHAR(20)  NOT NULL DEFAULT '대기'
                               CHECK (status IN ('대기','발송','완료')),
                issued_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
                updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
                notes          TEXT
            )
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_ref_subject
            ON {_OVA}.ova_referrals(subject_id)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_ref_doctor
            ON {_OVA}.ova_referrals(doctor_id)
        """))

        # ova_referrals urgency CHECK 제약에 '응급' 추가
        conn.execute(text(f"""
            DO $$
            DECLARE v_conname text;
            BEGIN
                SELECT conname INTO v_conname
                FROM pg_constraint c
                JOIN pg_class r ON r.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = r.relnamespace
                WHERE n.nspname = '{_OVA}'
                  AND r.relname = 'ova_referrals'
                  AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) LIKE '%urgency%'
                LIMIT 1;

                IF v_conname IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE {_OVA}.ova_referrals DROP CONSTRAINT '
                            || quote_ident(v_conname);
                END IF;

                ALTER TABLE {_OVA}.ova_referrals
                ADD CONSTRAINT ova_referrals_urgency_check
                CHECK (urgency IN ('일반','긴급','매우긴급','응급'));
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """))

        # ova_referrals status CHECK에 '취소' 추가
        conn.execute(text(f"""
            DO $$
            DECLARE v_conname text;
            BEGIN
                SELECT conname INTO v_conname
                FROM pg_constraint c
                JOIN pg_class r ON r.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = r.relnamespace
                WHERE n.nspname = '{_OVA}'
                  AND r.relname = 'ova_referrals'
                  AND c.contype = 'c'
                  AND pg_get_constraintdef(c.oid) LIKE '%status%'
                LIMIT 1;

                IF v_conname IS NOT NULL THEN
                    EXECUTE 'ALTER TABLE {_OVA}.ova_referrals DROP CONSTRAINT '
                            || quote_ident(v_conname);
                END IF;

                ALTER TABLE {_OVA}.ova_referrals
                ADD CONSTRAINT ova_referrals_status_check
                CHECK (status IN ('대기','발송','완료','취소'));
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """))

        # ── 신규 환자 추가 정보 ────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.ova_patient_info (
                subject_id         INTEGER      NOT NULL UNIQUE,
                name               VARCHAR(100),
                birth_year         INTEGER,
                symptoms           TEXT,
                menopause          BOOLEAN,
                has_diabetes       BOOLEAN      NOT NULL DEFAULT FALSE,
                has_hypertension   BOOLEAN      NOT NULL DEFAULT FALSE,
                has_hyperlipidemia BOOLEAN      NOT NULL DEFAULT FALSE,
                height             NUMERIC(5,1),
                weight             NUMERIC(5,1),
                bmi                NUMERIC(5,1),
                created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
            )
        """))
        # 기존 테이블에 컬럼 없으면 추가 (마이그레이션)
        conn.execute(text("""
            ALTER TABLE public.ova_patient_info
              ADD COLUMN IF NOT EXISTS has_diabetes       BOOLEAN NOT NULL DEFAULT FALSE,
              ADD COLUMN IF NOT EXISTS has_hypertension   BOOLEAN NOT NULL DEFAULT FALSE,
              ADD COLUMN IF NOT EXISTS has_hyperlipidemia BOOLEAN NOT NULL DEFAULT FALSE,
              ADD COLUMN IF NOT EXISTS height             NUMERIC(5,1),
              ADD COLUMN IF NOT EXISTS weight             NUMERIC(5,1),
              ADD COLUMN IF NOT EXISTS bmi                NUMERIC(5,1)
        """))

        # ── 환자 목록 제외 ────────────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.ova_excluded_patients (
                subject_id   INTEGER      NOT NULL UNIQUE,
                excluded_by  VARCHAR(100),
                excluded_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                reason       TEXT
            )
        """))

        # ── 파일 업로드 검사결과 ──────────────────────────────────────────
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.ova_lab_uploads (
                id            SERIAL       PRIMARY KEY,
                subject_id    INTEGER      NOT NULL,
                test_name     VARCHAR(100) NOT NULL,
                value         NUMERIC,
                unit          VARCHAR(50),
                recorded_date DATE,
                uploaded_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
                uploaded_by   VARCHAR(20)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_lab_uploads_subject
            ON public.ova_lab_uploads(subject_id)
        """))
