# batch_infer.py
import requests
import psycopg

DB_CONFIG = {
    "host": "192.168.0.33",
    "port": 5432,
    "dbname": "mimic",
    "user": "team2",
    "password": "1234",
}

API_URL = "http://localhost:8001"

def main():
    # DB에서 초음파 이미지 있는 환자 목록 조회
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT subject_id 
                FROM mimic_ova.ova_ultrasound
                ORDER BY subject_id
            """)
            subject_ids = [row[0] for row in cur.fetchall()]

    print(f"총 {len(subject_ids)}명 추론 시작...")

    success, fail = 0, 0
    for subject_id in subject_ids:
        try:
            images_resp = requests.get(
                f"{API_URL}/api/dicom/images",
                params={"case_code": str(subject_id), "subject_id": str(subject_id)},
                timeout=30
            )
            images = images_resp.json()
            if not images:
                print(f"❌ {subject_id} 이미지 없음")
                fail += 1
                continue

            # 전체 이미지 추론
            results = []
            for img in images:
                resp = requests.post(
                    f"{API_URL}/api/inference",
                    json={"hadm_id": str(subject_id), "image_seq": img["seq"]},
                    timeout=120
                )
                if resp.status_code == 200:
                    results.append(resp.json())

            if not results:
                print(f"❌ {subject_id} 추론 실패")
                fail += 1
                continue

            # worst case 선택
            worst = max(results, key=lambda x: x.get("malignant_prob") or 0)
            result = worst

            # u_score 계산 추가
            checked = [
                worst.get("multilocular"),
                worst.get("solid_areas"),
                worst.get("bilateral"),
                worst.get("ascites"),
                worst.get("peritoneal_mets"),
            ]
            count = sum(1 for c in checked if c)
            u_score = 0 if count == 0 else 1 if count == 1 else 3

            # DB 저장 시 us_u_score 추가
            save_resp = requests.post(
                f"{API_URL}/api/cdss/save",
                json={
                    "subject_id": subject_id,
                    "malignant_prob": result.get("malignant_prob"),
                    "detected": result.get("detected"),
                    "tumor_size_max": result.get("tumor_size_max"),
                    "stage": result.get("stage") or "benign",
                    "subtype": result.get("subtype"),
                    "us_u_score": u_score,  # 추가
                },
                timeout=30
            )

            if save_resp.status_code == 200:
                print(f"✅ {subject_id} 저장 완료 (악성확률: {result.get('malignant_prob')}%)")
                success += 1
            else:
                print(f"❌ {subject_id} 저장 실패: {save_resp.status_code} {save_resp.text[:100]}")
                fail += 1

        except Exception as e:
            print(f"❌ {subject_id} 오류: {e}")
            fail += 1

    print(f"\n완료: 성공 {success}명 / 실패 {fail}명")

if __name__ == '__main__':
    main()