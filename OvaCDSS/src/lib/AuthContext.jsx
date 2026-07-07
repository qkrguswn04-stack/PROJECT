'use client';
import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

const COOKIE = 'ova-auth';
const STORE  = 'ova-cdss-user';

// ──────────────────────────────────────────────────────────────────────────────
// ⚠️  인증 핵심 코드 — 임의로 삭제하거나 단순화하지 말 것
//
// 이 앱의 로그인 보호는 3단 구조:
//   1) middleware.ts   (서버) — ova-auth 쿠키 없으면 /login 리다이렉트
//   2) DashboardLayout (클라) — user 없으면 /login 리다이렉트 + null 렌더
//   3) AuthContext     (여기) — 쿠키·localStorage 동기 검증, 로그아웃 시 완전 삭제
//
// 세션 쿠키(만료 없음)를 쓰면 브라우저 재시작 시 복원되어 로그인 없이 통과됨.
// 반드시 Max-Age를 명시해 유효 시간을 제한해야 함.
// ──────────────────────────────────────────────────────────────────────────────

const SESSION_MAX_AGE = 8 * 60 * 60; // 8시간 (초 단위)

const hasCookie = () => document.cookie.split(';').some(c => c.trim().startsWith(COOKIE + '='));

// ⚠️ Max-Age 필수 — 없으면 세션 쿠키가 되어 브라우저 복원 시 자동 통과 버그 발생
const setCookie = () => {
  document.cookie = `${COOKIE}=1; path=/; SameSite=Lax; Max-Age=${SESSION_MAX_AGE}`;
};

// ⚠️ Max-Age=0 AND expires=과거 — 두 방법 동시 사용해야 모든 브라우저에서 즉시 삭제됨
const clearCookie = () => {
  document.cookie = `${COOKIE}=; path=/; SameSite=Lax; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // ⚠️ 쿠키와 localStorage 둘 다 있어야만 세션으로 인정
    // 하나라도 없으면 둘 다 삭제해 불완전 상태를 방지
    try {
      const cookieExists = hasCookie();
      const stored = localStorage.getItem(STORE);
      if (cookieExists && stored) {
        setUser(JSON.parse(stored));
      } else {
        // 어느 한쪽만 남아있는 경우 → 둘 다 정리
        clearCookie();
        localStorage.removeItem(STORE);
      }
    } catch {
      clearCookie();
      localStorage.removeItem(STORE);
    }
    setLoading(false);
  }, []);

  const login = (userData) => {
    setUser(userData);
    localStorage.setItem(STORE, JSON.stringify(userData));
    setCookie(); // 8시간 만료 쿠키 설정
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(STORE); // ⚠️ localStorage 삭제 필수 — 없으면 쿠키 재설정 시 자동 로그인
    clearCookie();                  // ⚠️ 쿠키 삭제 필수 — 없으면 middleware가 계속 통과시킴
  };

  const updateUser = (userData) => {
    setUser(userData);
    localStorage.setItem(STORE, JSON.stringify(userData));
  };

  const role = user?.employee_id?.startsWith('DR') ? 'doctor'
             : user?.employee_id?.startsWith('NR') ? 'nurse'
             : null;

  return (
    <AuthContext.Provider value={{ user, role, login, logout, updateUser, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
