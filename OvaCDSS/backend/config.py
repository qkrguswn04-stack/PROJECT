import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://team2:1234@192.168.0.33:5432/mimic"
)

API_PORT = int(os.getenv("API_PORT", "8001"))

DB_POOL_SIZE    = int(os.getenv("DB_POOL_SIZE",    "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

MIMIC_HOSP_SCHEMA = os.getenv("MIMIC_HOSP_SCHEMA", "mimic_ova")
MIMIC_ICU_SCHEMA  = os.getenv("MIMIC_ICU_SCHEMA",  "mimic_ova")

# 활력징후 itemid (MIMIC-IV MetaVision)
VITALS_ITEMIDS = {
    "hr":     220045,
    "sbp":    220179,
    "dbp":    220180,
    "rr":     220210,
    "spo2":   220277,
    "temp_c": 223762,
}

# 모델 가중치 경로
MODEL_WEIGHTS_DIR = os.getenv(
    "MODEL_WEIGHTS_DIR",
    "/home/team2/model_weights/runs"
)

# DICOM 파일 경로
DICOM_DIR = os.getenv(
    "DICOM_DIR",
    r"C:\Users\301-22\Desktop\DICOM\dicom_conversion\dicom_output"  # 로컬 경로로 임시 변경
)
