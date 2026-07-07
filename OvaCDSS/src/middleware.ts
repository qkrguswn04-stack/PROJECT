// ──────────────────────────────────────────────────────────────────────────────
// ⚠️  서버사이드 인증 가드 — 임의로 삭제하거나 단순화하지 말 것
//
// Next.js Edge Middleware: 모든 요청이 페이지에 도달하기 전 실행됨.
// ova-auth 쿠키가 없으면 /login 으로 강제 리다이렉트.
// 이 파일과 AuthContext.jsx, DashboardLayout이 3단 가드 구조를 이룸.
// 하나라도 제거하면 로그인 없이 대시보드 접근 가능해짐.
// ──────────────────────────────────────────────────────────────────────────────
import { NextRequest, NextResponse } from 'next/server';

const PUBLIC_PATHS = ['/login', '/_next', '/favicon', '/icons', '/ovacdss_logo_01.png'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  if (isPublic) return NextResponse.next();

  // ⚠️ ova-auth 쿠키 없으면 로그인 페이지로 강제 이동
  // 쿠키는 AuthContext의 setCookie()가 로그인 성공 시 설정 (Max-Age=8h)
  const isAuthenticated = request.cookies.has('ova-auth');
  if (!isAuthenticated) {
    return NextResponse.redirect(new URL('/login', request.url));
  }


  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
