from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import auth
import patients
import rmi
import predict as predict_mod
from init import init_custom_tables

# torchvision 등 ML 의존성이 없어도 서버가 뜰 수 있도록 optional import
try:
    import inference as inference_mod
except ImportError:
    inference_mod = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_custom_tables()
    yield


app = FastAPI(title="OvarianCDSS API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:3002", "http://127.0.0.1:3002",
        "http://localhost:3003", "http://127.0.0.1:3003",
        "http://192.168.0.5:3003"

    ],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 스키마 ────────────────────────────────────────────────────────────────────

class RMIRequest(BaseModel):
    ca125_value:      float = Field(..., gt=0)
    us_score:         int   = Field(...)
    menopause_factor: int   = Field(...)
    hadm_id:          Optional[int] = None
    notes:            Optional[str] = None

    @property
    def risk_level(self) -> str:
        score = self.ca125_value * self.us_score * self.menopause_factor
        if score >= 200:  return "HIGH"
        if score >= 25:   return "MODERATE"
        return "LOW"


class StatusRequest(BaseModel):
    status:     str
    updated_by: Optional[str] = None
    notes:      Optional[str] = None


class PatientRegisterRequest(BaseModel):
    gender:             str
    birth_year:         int  = Field(..., ge=1900, le=2100)
    admission_type:     str  = "ELECTIVE"
    admit_date:         str
    name:               Optional[str]  = None
    symptoms:           Optional[str]  = None
    menopause:          Optional[bool] = None
    registered_by:      Optional[str]  = None
    has_diabetes:       bool = False
    has_hypertension:   bool = False
    has_hyperlipidemia: bool = False
    height:             Optional[float] = None
    weight:             Optional[float] = None
    bmi:                Optional[float] = None


class LabRow(BaseModel):
    test_name:     str
    value:         Optional[float] = None
    unit:          Optional[str]   = None
    recorded_date: Optional[str]   = None


class LabUploadRequest(BaseModel):
    rows:        list[LabRow]
    uploaded_by: Optional[str] = None


class ReferralRequest(BaseModel):
    doctor_id:   str
    urgency:     str  = "일반"
    destination: Optional[str] = None
    content:     Optional[str] = None
    hadm_id:     Optional[int] = None


class LoginRequest(BaseModel):
    employee_id: str
    password:    str


class ChangePasswordRequest(BaseModel):
    employee_id:      str
    current_password: str
    new_password:     str


class UpdateProfileRequest(BaseModel):
    employee_id: str
    name:        str


class InferenceRequest(BaseModel):
    hadm_id:   str
    image_seq: int = 1  # 몇 번째 이미지인지


# ── 인증 ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(body: LoginRequest):
    user = auth.verify_user(body.employee_id, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="사번 또는 비밀번호가 올바르지 않습니다.")
    return user

@app.put("/api/auth/change-password")
def change_password(body: ChangePasswordRequest):
    ok = auth.change_user_password(body.employee_id, body.current_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
    return {"message": "비밀번호가 변경됐습니다."}

@app.put("/api/auth/profile")
def update_profile(body: UpdateProfileRequest):
    user = auth.update_user_profile(body.employee_id, body.name)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user


# ── 헬스체크 ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "OvarianCDSS API", "db_connected": db.check_db_connection()}

@app.get("/health")
def health():
    if not db.check_db_connection():
        raise HTTPException(status_code=503, detail="DB 연결 실패")
    return {"status": "ok"}


# ── 랜딩 통계 ────────────────────────────────────────────────────────────────

@app.get("/api/stats/summary")
def get_stats_summary():
    try:
        return patients.fetch_landing_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 환자 목록 ─────────────────────────────────────────────────────────────────

@app.get("/api/patients")
def get_patients(
    page:  int = Query(1,  ge=1),
    limit: int = Query(20, ge=1, le=1000),
):
    try:
        return patients.fetch_screening_patients(page=page, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patients/register", status_code=201)
def register_patient(body: PatientRegisterRequest):
    if body.gender not in ("F", "M"):
        raise HTTPException(status_code=422, detail="gender는 F 또는 M")
    try:
        return patients.register_patient(
            gender=body.gender,
            birth_year=body.birth_year,
            admission_type=body.admission_type,
            admit_date=body.admit_date,
            name=body.name,
            symptoms=body.symptoms,
            menopause=body.menopause,
            has_diabetes=body.has_diabetes,
            has_hypertension=body.has_hypertension,
            has_hyperlipidemia=body.has_hyperlipidemia,
            height=body.height,
            weight=body.weight,
            bmi=body.bmi,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patients/{subject_id}/labs/upload", status_code=201)
def upload_labs(subject_id: int, body: LabUploadRequest):
    try:
        count = patients.insert_lab_uploads(
            subject_id=subject_id,
            rows=[r.model_dump() for r in body.rows],
            uploaded_by=body.uploaded_by,
        )
        return {"inserted": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 환자 상세 ─────────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}")
def get_patient(subject_id: int):
    patient = patients.fetch_patient_detail(subject_id)
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다")
    return patient


# ── CDSS 분석 결과 ───────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/cdss-result")
def get_cdss_result(subject_id: int):
    try:
        return patients.fetch_cdss_result(subject_id) or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 검사 결과 ─────────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/labs/by-date")
def get_labs_by_date(subject_id: int):
    try:
        return patients.fetch_labs_by_date(subject_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── CDSS 예측 ────────────────────────────────────────────────────────────────

@app.post("/api/patients/{subject_id}/predict")
def run_prediction(subject_id: int):
    try:
        return predict_mod.predict_malignancy(subject_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/predictions")
def get_all_predictions():
    """전체 필터링 환자 일괄 예측 — 환자목록 위험도 퍼센트 표시용."""
    try:
        result = patients.fetch_screening_patients(page=1, limit=1000)
        subject_ids = [row["subject_id"] for row in result["data"]]
        preds = predict_mod.predict_batch(subject_ids)
        return {p["subject_id"]: p["probability_pct"] for p in preds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 동반질환 ─────────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/comorbidities")
def get_comorbidities(subject_id: int):
    try:
        return patients.fetch_comorbidities(subject_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 활력징후 ──────────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/vitals/by-date")
def get_vitals_by_date(subject_id: int):
    try:
        return patients.fetch_vitals_by_date(subject_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── RMI ──────────────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/rmi")
def get_rmi_history(subject_id: int):
    return rmi.fetch_rmi_history(subject_id)

@app.post("/api/patients/{subject_id}/rmi", status_code=201)
def save_rmi(subject_id: int, body: RMIRequest):
    if body.us_score not in (0, 1, 3):
        raise HTTPException(status_code=422, detail="us_score는 0, 1, 3 중 하나")
    if body.menopause_factor not in (1, 3):
        raise HTTPException(status_code=422, detail="menopause_factor는 1 또는 3")
    try:
        return rmi.insert_rmi_score(
            subject_id=subject_id,
            ca125_value=body.ca125_value,
            us_score=body.us_score,
            menopause_factor=body.menopause_factor,
            risk_level=body.risk_level,
            hadm_id=body.hadm_id,
            notes=body.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 의뢰서 ───────────────────────────────────────────────────────────────────

@app.post("/api/patients/{subject_id}/referral", status_code=201)
def create_referral(subject_id: int, body: ReferralRequest):
    allowed_urgency = {"일반", "긴급", "매우긴급", "응급"}
    if body.urgency not in allowed_urgency:
        raise HTTPException(status_code=422, detail="urgency는 일반/긴급/매우긴급 중 하나")
    try:
        return patients.save_referral(
            subject_id=subject_id,
            doctor_id=body.doctor_id,
            urgency=body.urgency,
            destination=body.destination,
            content=body.content,
            hadm_id=body.hadm_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/patients/{subject_id}/referral")
def cancel_referral(subject_id: int):
    result = patients.cancel_referral(subject_id)
    if not result:
        raise HTTPException(status_code=404, detail="의뢰 내역 없음")
    return result


# ── 스크리닝 상태 ─────────────────────────────────────────────────────────────

@app.get("/api/patients/{subject_id}/status")
def get_status(subject_id: int):
    result = rmi.fetch_screening_status(subject_id)
    return result or {"subject_id": subject_id, "status": "신규"}

@app.put("/api/patients/{subject_id}/status")
def update_status(subject_id: int, body: StatusRequest):
    allowed = {"신규", "관찰중", "검토완료", "의뢰완료"}
    if body.status not in allowed:
        raise HTTPException(status_code=422, detail=f"status는 {allowed} 중 하나")
    try:
        return rmi.upsert_screening_status(
            subject_id=subject_id, status=body.status,
            updated_by=body.updated_by, notes=body.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── DICOM ────────────────────────────────────────────────────────────────────

ORTHANC_URL  = "http://192.168.0.47:8042"
ORTHANC_AUTH = ("orthanc", "orthanc")
GPU_SERVER_URL = "http://192.168.0.47:9001"
USE_GPU_SERVER = True  # False면 로컬 CPU 추론(inference.py) 사용

@app.get("/api/dicom/has-images")
def get_dicom_has_images():
    """Orthanc에 이미지가 등록된 subject_id 목록을 한 번에 반환."""
    import requests as req
    try:
        resp = req.get(f"{ORTHANC_URL}/patients?expand", auth=ORTHANC_AUTH, timeout=10)
        patients = resp.json()
        subject_ids = []
        for p in patients:
            pid = p.get("MainDicomTags", {}).get("PatientID", "")
            if pid:
                try:
                    subject_ids.append(int(pid))
                except ValueError:
                    pass
        return {"subject_ids": subject_ids}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Orthanc 연결 실패: {e}")


@app.get("/api/dicom/images")
def get_dicom_images(case_code: str = Query(...), subject_id: str = Query(...)):
    """
    subject_id 기준으로 Orthanc에서 DICOM 인스턴스 목록 조회
    """
    import requests as req

    resp = req.post(f"{ORTHANC_URL}/tools/find", json={
        "Level": "Patient",
        "Query": {"PatientID": str(subject_id)}
    }, auth=ORTHANC_AUTH)

    patients_found = resp.json()
    if not patients_found:
        return []

    result = []
    idx = 1
    for patient_oid in patients_found:
        p_detail = req.get(f"{ORTHANC_URL}/patients/{patient_oid}", auth=ORTHANC_AUTH).json()
        for study_oid in p_detail.get("Studies", []):
            s_detail = req.get(f"{ORTHANC_URL}/studies/{study_oid}", auth=ORTHANC_AUTH).json()
            for series_oid in s_detail.get("Series", []):
                sr_detail = req.get(f"{ORTHANC_URL}/series/{series_oid}", auth=ORTHANC_AUTH).json()
                for inst_oid in sr_detail.get("Instances", []):
                    result.append({
                        "id":    idx,
                        "seq":   idx,
                        "label": f"{subject_id}_{idx}",
                        "url": f"http://localhost:8001/api/dicom/preview/{inst_oid}",
                    })
                    idx += 1

    return result

@app.get("/api/dicom/preview/{instance_id}")
def get_dicom_preview(instance_id: str):
    import requests as req
    from fastapi.responses import Response
    resp = req.get(
        f"{ORTHANC_URL}/instances/{instance_id}/preview",
        auth=ORTHANC_AUTH
    )
    return Response(content=resp.content, media_type="image/png")


# ── AI 추론 ──────────────────────────────────────────────────────────────────

@app.post("/api/inference")
def run_inference(body: InferenceRequest):
    import requests as req

    # 1. Orthanc에서 DICOM 가져오기
    resp = req.post(f"{ORTHANC_URL}/tools/find", json={
        "Level": "Instance",
        "Query": {"PatientID": str(body.hadm_id)}
    }, auth=ORTHANC_AUTH, timeout=10)
    instances = resp.json()

    if not instances or body.image_seq > len(instances):
        raise HTTPException(status_code=404, detail="DICOM 인스턴스를 찾을 수 없습니다.")

    inst_oid = instances[body.image_seq - 1]
    dcm_bytes = req.get(
        f"{ORTHANC_URL}/instances/{inst_oid}/file",
        auth=ORTHANC_AUTH,
        timeout=30,
    ).content

    # 2. 추론 실행
    if USE_GPU_SERVER:
        try:
            gpu_resp = req.post(
                f"{GPU_SERVER_URL}/infer",
                files={"file": ("image.dcm", dcm_bytes, "application/dicom")},
                timeout=60,
            )
            if not gpu_resp.ok:
                # GPU 서버의 실제 에러 메시지를 그대로 전달
                try:
                    detail = gpu_resp.json().get("detail", gpu_resp.text)
                except Exception:
                    detail = gpu_resp.text
                raise HTTPException(status_code=502, detail=f"GPU 서버 오류 ({gpu_resp.status_code}): {detail}")
            result = gpu_resp.json()
        except req.exceptions.ConnectionError as e:
            raise HTTPException(status_code=502, detail=f"GPU 서버 연결 실패: {e}")
        except req.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="GPU 서버 응답 시간 초과 (60s)")
        except req.exceptions.RequestException as e:
            raise HTTPException(status_code=502, detail=f"GPU 추론 서버 호출 실패: {e}")
    else:
        if inference_mod is None:
            raise HTTPException(status_code=503, detail="로컬 추론 모듈 의존성 미설치")
        import os, tempfile
        with tempfile.NamedTemporaryFile(suffix=".dcm", delete=False) as tmp:
            tmp.write(dcm_bytes)
            tmp_path = tmp.name
        try:
            result = inference_mod.run_pipeline(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            os.unlink(tmp_path)

    return result  # ← 이거 추가!


# ── CDSS 결과 저장 ────────────────────────────────────────────────────────────

class CdssResultBody(BaseModel):
    subject_id: int
    malignant_prob: float = None
    detected: bool = None
    tumor_size_max: float = None
    stage: str = None
    subtype: str = None
    us_u_score: int = None
    image_url: str = None


@app.post("/api/cdss/save")
def save_cdss_result(body: CdssResultBody):
    from sqlalchemy import text
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM mimic_ova.ova_cdss_results 
                WHERE subject_id = :subject_id
            """), {"subject_id": body.subject_id})
            conn.execute(text("""
                INSERT INTO mimic_ova.ova_cdss_results (
                    subject_id, us_malignancy_prob, us_tumor_detected,
                    us_tumor_size_cm2, us_figo_stage, us_tumor_type,
                    us_u_score, us_image_url, model_version, created_at
                ) VALUES (
                    :subject_id, :malignant_prob, :detected,
                    :tumor_size, :stage, :subtype,
                    :us_u_score, :image_url, 'v1.0', NOW()
                )
            """), {
                "subject_id":     body.subject_id,
                "malignant_prob": body.malignant_prob,
                "detected":       body.detected,
                "tumor_size":     body.tumor_size_max,
                "stage":          body.stage or "benign",
                "subtype":        body.subtype,
                "us_u_score":     body.us_u_score,
                "image_url":      body.image_url,
            })
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))