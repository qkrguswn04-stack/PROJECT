'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/AuthContext';
import { loginUser, getLandingStats } from '@/lib/api';

export default function LoginPage() {
  const [employeeId, setEmployeeId] = useState('');
  const [password,   setPassword]   = useState('');
  const [showPw,     setShowPw]     = useState(false);
  const [error,      setError]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [stats,      setStats]      = useState(null);

  const router = useRouter();
  const { user, login } = useAuth();

  useEffect(() => {
    if (user) router.push('/screening');
  }, [user, router]);

  useEffect(() => {
    getLandingStats().then(setStats).catch(() => {});
  }, []);

  const handleLogin = async () => {
    if (!employeeId || !password) { setError('사번과 비밀번호를 입력해주세요.'); return; }
    setLoading(true); setError('');
    try {
      const u = await loginUser(employeeId, password);
      login(u);
      // useEffect([user])가 React 커밋 이후 router.push를 처리함
    } catch (err) {
      setError(err.message || '사번 또는 비밀번호가 올바르지 않습니다.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-canvas">

      {/* ── 좌측 브랜딩 ──────────────────────────────────────────────── */}
      <div className="hidden lg:flex flex-col justify-center w-1/2 px-16 py-14 border-r border-hairline">

        <div>
          {/* 아이브로우 */}
          <div className="text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-8">
            Ovarian Cancer Clinical Decision Support System
          </div>
          {/* 로고 + 헤드라인 가로 배치 */}
          <div className="flex items-center gap-6 mb-6">
            <img src="/ovacdss_logo_01.png" alt="OVA-LINK" className="h-24 w-auto shrink-0" />
            <h1 className="text-[3.2rem] font-semibold leading-[1.05] text-ink" style={{ letterSpacing: '-2px' }}>
              진단하라.<br />
              <span className="text-primary">더 빠르게.</span>
            </h1>
          </div>
          <p className="text-ink-subtle text-base leading-relaxed max-w-sm" style={{ letterSpacing: '-0.1px' }}>
            AI-driven clinical decision support for ovarian cancer early detection
            · CA-125 · RMI Score · ROMA Algorithm
          </p>
          {/* 스탯 카드 */}
          <div className="grid grid-cols-3 gap-3 mt-10">
            {[
              {
                label: '연동 환자',
                value: stats ? `${stats.total.toLocaleString()}명` : '—',
                tag: '스크리닝 대상',
              },
              {
                label: 'High Risk',
                value: stats ? `${stats.high_risk_pct}%` : '—',
                tag: stats ? `${stats.high_count.toLocaleString()}명 해당` : '—',
              },
              {
                label: 'RMI 평균',
                value: stats?.rmi_avg != null ? stats.rmi_avg.toLocaleString() : '—',
                tag: 'RMI 보유 환자 기준',
              },
            ].map((s, i) => (
              <div key={i} className="bg-surface-1 rounded-xl px-4 py-4 border border-hairline">
                <div className="text-2xl font-semibold text-ink mb-0.5" style={{ letterSpacing: '-0.6px' }}>{s.value}</div>
                <div className="text-xs font-medium text-ink-subtle">{s.label}</div>
                <div className="text-xs text-ink-tertiary mt-0.5">{s.tag}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-xs text-ink-tertiary">
          RMI Algorithm · ROMA Score · Moore et al. 2009
        </div>
      </div>

      {/* ── 우측 로그인 ──────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="w-full max-w-sm">
          {/* 모바일 로고 */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <div className="w-5 h-5 bg-primary rounded-[4px] flex items-center justify-center">
              <div className="w-1.5 h-1.5 bg-white rounded-full" />
            </div>
            <span className="text-sm font-semibold text-ink tracking-tight">OVA-LINK</span>
          </div>

          <h2 className="text-3xl font-semibold text-ink mb-1" style={{ letterSpacing: '-1px' }}>로그인</h2>
          <p className="text-sm text-ink-subtle mb-8">사번과 비밀번호를 입력해주세요</p>

          {/* 사번 */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5">
              사번 (Employee ID)
            </label>
            <input
              type="text"
              value={employeeId}
              onChange={e => { setEmployeeId(e.target.value); setError(''); }}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              placeholder="예: DR001"
              className={`w-full px-3.5 py-2.5 bg-surface-1 border rounded-lg text-sm text-ink outline-none transition-colors ${
                error ? 'border-red-500/50' : 'border-hairline focus:border-primary'
              }`}
            />
          </div>

          {/* 비밀번호 */}
          <div className="mb-6">
            <label className="block text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5">
              비밀번호
            </label>
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={e => { setPassword(e.target.value); setError(''); }}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                placeholder="비밀번호 입력"
                className={`w-full px-3.5 pr-11 py-2.5 bg-surface-1 border rounded-lg text-sm text-ink outline-none transition-colors ${
                  error ? 'border-red-500/50' : 'border-hairline focus:border-primary'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-tertiary hover:text-ink-subtle text-xs transition-colors"
              >
                {showPw ? '🙈' : '👁'}
              </button>
            </div>
          </div>

          {/* 에러 */}
          {error && (
            <div className="mb-4 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-600">
              {error}
            </div>
          )}

          {/* 로그인 버튼 */}
          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-white text-sm font-medium bg-primary hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </div>
      </div>
    </div>
  );
}
