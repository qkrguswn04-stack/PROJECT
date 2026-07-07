"""
auth.py — 사용자 인증·비밀번호·프로필
"""

from __future__ import annotations

import bcrypt as _bcrypt_lib
from sqlalchemy import text

from db import engine


def _hash_pw(raw: str) -> str:
    return _bcrypt_lib.hashpw(raw.encode(), _bcrypt_lib.gensalt()).decode()


def _verify_pw(raw: str, hashed: str) -> bool:
    return _bcrypt_lib.checkpw(raw.encode(), hashed.encode())


_INITIAL_USERS = [
    {"employee_id": "AD001", "name": "관리자",  "role": "admin",  "pw": "admin1!"},
    {"employee_id": "DR001", "name": "박지현",  "role": "doctor", "pw": "doctor1!"},
    {"employee_id": "DR002", "name": "김민준",  "role": "doctor", "pw": "doctor1!"},
    {"employee_id": "NR001", "name": "이수진",  "role": "nurse",  "pw": "nurse1!"},
    {"employee_id": "NR002", "name": "한지민",  "role": "nurse",  "pw": "nurse1!"},
]


def verify_user(employee_id: str, password: str) -> dict | None:
    """사번 + 비밀번호 검증. 성공 시 유저 정보(password_hash 제외) 반환, 실패 시 None."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT employee_id, name, role, password_hash
            FROM ova_users WHERE employee_id = :eid
        """), {"eid": employee_id}).fetchone()

    if not row:
        return None
    r = dict(row._mapping)
    if not _verify_pw(password, r["password_hash"]):
        return None
    return {"employee_id": r["employee_id"], "name": r["name"], "role": r["role"]}


def change_user_password(employee_id: str, current_password: str, new_password: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT password_hash FROM ova_users WHERE employee_id = :eid
        """), {"eid": employee_id}).fetchone()
    if not row or not _verify_pw(current_password, row[0]):
        return False
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE ova_users SET password_hash = :hash WHERE employee_id = :eid
        """), {"hash": _hash_pw(new_password), "eid": employee_id})
    return True


def update_user_profile(employee_id: str, name: str) -> dict | None:
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE ova_users SET name = :name WHERE employee_id = :eid
            RETURNING employee_id, name, role
        """), {"name": name, "eid": employee_id}).fetchone()
    return dict(row._mapping) if row else None
