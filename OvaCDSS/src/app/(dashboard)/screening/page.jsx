'use client';
import { useState, useEffect } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/AuthContext';
import { getPatients, getDicomSubjectIds } from '@/lib/api';
import RiskBadge, { StatusBadge } from '@/components/RiskBadge';
import DateRangePicker from '@/components/DateRangePicker';
import RegisterDrawer from '@/components/RegisterDrawer';

const TABS         = ['전체', '신규', '관찰중', '검토완료', '의뢰완료'];
const RISK_OPTIONS = ['전체', 'HIGH', 'MODERATE', 'LOW'];
const COL_PCT      = ['9%', '13%', '9%', '5%', '11%', '10%', '10%', '9%', '9%', '15%'];

function actionLabel(status) {
  if (status === '검토완료' || status === '의뢰완료') return '결과 보기';
  return 'CDSS 분석';
}

function actionPath(id) {
  return `/cdss?subject_id=${id}`;
}

function detailPath(id) {
  return `/patients/${id}`;
}

const SELECT_CLS = "px-3 py-2 text-sm bg-surface-1 border border-hairline rounded-lg text-ink-subtle outline-none focus:border-primary transition-colors appearance-none cursor-pointer";

export default function ScreeningPage() {
  const { user, role } = useAuth();
  const router    = useRouter();

  const [allPatients, setAllPatients] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [tab,         setTab]         = useState('전체');
  const [search,      setSearch]      = useState('');
  const [riskFilter,  setRiskFilter]  = useState('전체');
  const [dateRange,   setDateRange]   = useState({ start: null, end: null });
  const [page,        setPage]        = useState(1);
  const [drawerOpen,       setDrawerOpen]       = useState(false);
  const [dicomIds,         setDicomIds]         = useState(null); // null = 로딩 중
  const [onlyUnregistered, setOnlyUnregistered] = useState(false);

  const PAGE_SIZE = 20;

  const loadAll = () => {
    setLoading(true); setError(null);
    getPatients(1, 1000)
      .then(({ patients }) => setAllPatients(patients))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAll();
    getDicomSubjectIds()
      .then(ids => setDicomIds(ids))
      .catch(() => setDicomIds(new Set()));
  }, []);

  const { start: rangeStart, end: rangeEnd } = dateRange;
  const filtered = allPatients
    .filter(p => tab === '전체' || p.status === tab)
    .filter(p => riskFilter === '전체' || p.riskTier === riskFilter)
    .filter(p => {
      if (!rangeStart && !rangeEnd) return true;
      const d = new Date(p.admitDate);
      if (isNaN(d.getTime())) return false;
      if (rangeStart) { const s = new Date(rangeStart); s.setHours(0,0,0,0); if (d < s) return false; }
      if (rangeEnd)   { const e = new Date(rangeEnd);   e.setHours(23,59,59,999); if (d > e) return false; }
      return true;
    })
    .filter(p => p.name.includes(search) || p.id.toLowerCase().includes(search.toLowerCase()))
    .filter(p => !onlyUnregistered || !dicomIds || !dicomIds.has(Number(p.subject_id)));

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const paginated  = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <>
    <RegisterDrawer
      open={drawerOpen}
      onClose={() => setDrawerOpen(false)}
      onSuccess={() => loadAll()}
    />
    <div className="p-8 max-w-[1320px]">

      {/* ── 백엔드 연결 실패 배너 ────────────────────────────────────── */}
      {!loading && error && (
        <div className="mb-5 flex items-center gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm">
          <span className="text-red-500 font-semibold shrink-0">⚠ 백엔드 연결 실패</span>
          <span className="text-red-600 font-mono text-xs truncate">{error}</span>
          <button
            onClick={() => loadAll(page)}
            className="ml-auto shrink-0 px-3 py-1 text-xs font-medium bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* ── 헤더 ──────────────────────────────────────────────────────── */}
      <div className="mb-5">
        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-2xl font-semibold text-ink" style={{ letterSpacing: '-0.5px' }}>환자목록</h1>
          <span className="text-s font-medium px-2.5 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded-full">
            {loading ? '…' : `전체 ${allPatients.length}명`}
          </span>
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="이름 또는 ID 검색"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="px-3 py-2 text-sm bg-surface-1 border border-hairline rounded-lg text-ink outline-none focus:border-primary transition-colors w-44"
            />
            <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} className={SELECT_CLS}>
              {RISK_OPTIONS.map(r => (
                <option key={r} value={r}>{r === '전체' ? '전체 위험도' : r}</option>
              ))}
            </select>
            <button
              onClick={() => { setOnlyUnregistered(v => !v); setPage(1); }}
              disabled={dicomIds === null}
              className={`px-3 py-2 text-sm rounded-lg border font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                onlyUnregistered
                  ? 'bg-primary text-white border-primary'
                  : 'bg-surface-1 border-hairline text-ink-subtle hover:border-hairline-strong hover:text-ink'
              }`}
            >
              초음파 미등록
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDateRange({ start: null, end: null })}
              className={`px-3 py-2 text-sm rounded-lg border transition-colors ${!dateRange.start ? 'bg-primary text-white border-primary' : 'border-hairline text-ink-subtle hover:border-hairline-strong hover:text-ink'}`}
            >
              전체
            </button>
            <DateRangePicker value={dateRange} onChange={setDateRange} />
            <button
              onClick={() => { setSearch(''); setRiskFilter('전체'); setDateRange({ start: null, end: null }); setTab('전체'); setOnlyUnregistered(false); }}
              className="px-3 py-2 text-sm border border-hairline rounded-lg text-ink-subtle hover:border-hairline-strong hover:text-ink transition-colors"
            >
              초기화
            </button>
            {(role === 'nurse' || role === 'doctor') && (
              <button
                onClick={() => setDrawerOpen(true)}
                className="px-3.5 py-2 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors"
              >
                + 환자 등록
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── 탭 ──────────────────────────────────────────────────────────── */}
      <div className="flex gap-0.5 mb-4">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setPage(1); }}
            className="px-3 py-1.5 text-base font-medium rounded-lg transition-colors"
            style={{
              background: tab === t ? '#5e6ad2' : 'transparent',
              color:      tab === t ? '#ffffff' : '#8a8f98',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── 테이블 ──────────────────────────────────────────────────────── */}
      <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">

        {loading && (
          <div className="py-16 text-center text-sm text-ink-tertiary">
            <div className="inline-block w-4 h-4 border-2 border-surface-3 border-t-primary rounded-full animate-spin mb-3" />
            <p>환자 목록 불러오는 중…</p>
          </div>
        )}

        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="w-full table-fixed min-w-[1160px]">
              <colgroup>
                {COL_PCT.map((w, i) => <col key={i} style={{ width: w }} />)}
              </colgroup>
              <thead>
                <tr className="border-b border-hairline-strong bg-surface-2">
                  <TH center>상태</TH>
                  <TH center>환자 정보</TH>
                  <TH center>ID</TH>
                  <TH center>나이</TH>
                  <TH center>등록일</TH>
                  <TH center>CA-125</TH>
                  <TH center>RMI 점수</TH>
                  <TH center>위험도</TH>
                  <TH center>초음파</TH>
                  <TH center>작업</TH>
                </tr>
              </thead>
              <tbody>
                {paginated.map((p, i) => (
                  <tr
                    key={p.id}
                    onClick={() => router.push(detailPath(p.id))}
                    className="border-b border-hairline-strong hover:bg-surface-2 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <td className="px-4 py-2.5 text-center">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="px-4 py-2.5 text-center whitespace-normal">
                      <div className="font-medium text-base text-ink leading-tight">{p.name}</div>
                      <div className="text-sm text-ink-subtle mt-0.5">
                        {p.gender === 'F' ? '여성' : p.gender === 'M' ? '남성' : '—'} · GY
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-center font-mono text-sm text-ink">{p.id}</td>
                    <td className="px-4 py-2.5 text-center text-base text-ink">{p.age}세</td>
                    <td className="px-4 py-2.5 text-center text-base text-ink-subtle font-mono whitespace-nowrap">{p.admitDate}</td>
                    <td className="px-4 py-2.5 text-center">
                      {p.ca125 != null ? (
                        <>
                          <span className={`text-base font-semibold tabular-nums ${p.ca125 > 35 ? 'text-red-600' : 'text-ink'}`}>
                            {p.ca125.toLocaleString()}
                          </span>
                          {p.ca125 > 35 && <span className="text-sm text-red-600 ml-0.5">↑</span>}
                          <span className="text-sm text-ink-subtle ml-1">U/mL</span>
                        </>
                      ) : (
                        <span className="text-base text-ink-subtle">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {p.rmi > 0 ? (
                        <span className={`text-base font-semibold tabular-nums ${p.rmi >= 200 ? 'text-red-600' : 'text-ink'}`}>
                          {p.rmi.toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-base text-ink-subtle">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <RiskBadge tier={p.riskTier} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {dicomIds === null ? (
                        <span className="text-base text-ink-subtle">…</span>
                      ) : dicomIds.has(Number(p.subject_id)) ? (
                        <CheckCircle2 size={16} className="text-emerald-500 inline" />
                      ) : (
                        <span className="text-base text-ink-subtle">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <button
                        onClick={e => { e.stopPropagation(); router.push(actionPath(p.id)); }}
                        className="text-base font-medium px-2.5 py-1 border border-hairline rounded-lg hover:border-primary hover:text-primary text-ink transition-colors"
                      >
                        {actionLabel(p.status)}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="py-14 text-center text-sm text-ink-tertiary">
            {allPatients.length === 0 ? 'DB에 해당 환자가 없습니다' : '검색 결과가 없습니다'}
          </div>
        )}

        {!loading && !error && totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-hairline">
            <span className="text-sm text-ink-subtle">
              {safePage} / {totalPages} 페이지 · {filtered.length}명
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="px-3 py-1.5 text-sm border border-hairline rounded-lg text-ink-subtle hover:border-hairline-strong hover:text-ink transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                이전
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const start = Math.max(1, Math.min(safePage - 2, totalPages - 4));
                const pg = start + i;
                return (
                  <button
                    key={pg}
                    onClick={() => setPage(pg)}
                    className={`w-7 h-7 text-sm rounded-lg transition-colors ${pg === safePage ? 'bg-primary text-white' : 'border border-hairline text-ink-subtle hover:border-hairline-strong hover:text-ink'}`}
                  >
                    {pg}
                  </button>
                );
              })}
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="px-3 py-1.5 text-sm border border-hairline rounded-lg text-ink-subtle hover:border-hairline-strong hover:text-ink transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                다음
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  );
}

function TH({ children, right, center }) {
  return (
    <th className={`px-4 py-2.5 text-base font-medium text-ink-tertiary whitespace-nowrap ${right ? 'text-right' : center ? 'text-center' : 'text-left'}`}>
      {children}
    </th>
  );
}
