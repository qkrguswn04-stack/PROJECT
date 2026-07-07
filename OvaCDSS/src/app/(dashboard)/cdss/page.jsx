'use client';
import { Suspense, useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ImageIcon, CheckCircle2, Loader2, Save, FileText } from 'lucide-react';
import { useAuth } from '@/lib/AuthContext';
import { getPatientBasic, getPatientStatus, updatePatientStatus, getLabsByDate, getPatients, runCdssPredict, getCdssResult, getDicomSubjectIds } from '@/lib/api';
import BboxOverlay from '@/components/BboxOverlay';

function SectionLabel({ children }) {
  return (
    <div className="px-5 py-3 bg-primary/10 border-b border-hairline flex items-center gap-2">
      <div className="w-1 h-4 rounded-full bg-primary" />
      <span className="text-lg font-bold text-primary">{children}</span>
    </div>
  );
}

function MetricCell({ label, value, sub, highlight }) {
  return (
    <div className="bg-surface-2 rounded-lg px-3 py-2.5">
      <div className="text-xs text-ink-subtle uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-lg font-semibold font-mono ${highlight ? 'text-red-600' : 'text-ink'}`}>
        {value ?? '—'}
      </div>
      <div className="text-xs text-ink-tertiary mt-0.5 h-4">{sub ?? ''}</div>
    </div>
  );
}

function LabValueCell({ label, value, unit, status }) {
  const valueColor =
    status === 'high' ? 'text-red-600' :
    status === 'low'  ? 'text-blue-600' :
    'text-ink';
  return (
    <div className="bg-surface-2 rounded-lg px-3 py-2.5">
      <div className="text-xs text-ink-subtle uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-sm font-semibold font-mono ${valueColor}`}>
        {value != null ? value : '—'}
      </div>
      <div className="text-xs text-ink-tertiary mt-0.5">{unit || '—'}</div>
    </div>
  );
}

// display_name → 화면 표시 레이블 + latestLabs 조회 키
const LAB_DISPLAY = [
  { key: 'CA-125',       label: 'CA-125',  unit: 'U/mL',  ref: '0–35'      },
  { key: 'Triglycerides',label: 'TG',      unit: 'mg/dL', ref: '0–149'     },
  { key: 'Glucose',      label: 'Glucose', unit: 'mg/dL', ref: '70–99'     },
  { key: 'Albumin',      label: 'Albumin', unit: 'g/dL',  ref: '3.5–5.0'   },
  { key: 'AST',          label: 'AST',     unit: 'U/L',   ref: '10–40'     },
  { key: 'ALT',          label: 'ALT',     unit: 'U/L',   ref: '7–56'      },
  { key: 'WBC',          label: 'WBC',     unit: 'K/μL',  ref: '4.5–11.0'  },
  { key: 'Hemoglobin',   label: 'Hb',      unit: 'g/dL',  ref: '12.0–16.0' },
  { key: 'HDL',          label: 'HDL',     unit: 'mg/dL', ref: '≥40'       },
  { key: 'Platelet',     label: 'Plt',     unit: 'K/μL',  ref: '150–400'   },
  { key: 'PT-INR',       label: 'PT-INR',  unit: '',      ref: '0.8–1.2'   },
  { key: 'BUN',          label: 'BUN',     unit: 'mg/dL', ref: '7–20'      },
];

// ── 환자 선택기 (sid 없을 때 표시) ───────────────────────────────────────────

const _RISK_LABEL  = { HIGH: '고위험', MODERATE: '중위험', LOW: '저위험' };
const _RISK_COLOR  = {
  HIGH:     'bg-red-50 text-red-600',
  MODERATE: 'bg-amber-50 text-amber-600',
  LOW:      'bg-emerald-50 text-emerald-600',
};
const _STATUS_COLOR = {
  '신규':    'bg-surface-2 text-ink-subtle',
  '관찰중':  'bg-blue-50 text-blue-600',
  '검토완료': 'bg-emerald-50 text-emerald-700',
  '의뢰완료': 'bg-violet-50 text-violet-700',
};

const PICKER_TABS = ['신규', '관찰중', '검토완료', '의뢰완료', '전체'];

const PICKER_PAGE_SIZE = 15;

function PatientPicker({ onSelect }) {
  const [all,      setAll]      = useState([]);   // 전체 로드 후 클라이언트 필터
  const [search,   setSearch]   = useState('');
  const [tab,      setTab]      = useState('신규');
  const [loading,  setLoading]  = useState(true);
  const [page,     setPage]     = useState(1);
  const [dicomIds, setDicomIds] = useState(null); // null = 로딩 중

  useEffect(() => {
    setLoading(true);
    // 105명 전부 한 번에 로드 → 탭·검색 모두 클라이언트 필터
    getPatients(1, 200)
      .then(({ patients }) => setAll(patients))
      .catch(() => {})
      .finally(() => setLoading(false));
    getDicomSubjectIds()
      .then(ids => setDicomIds(ids))
      .catch(() => setDicomIds(new Set()));
  }, []);

  const filtered = all
    .filter(p => tab === '전체' || p.status === tab)
    .filter(p => !search || p.name.includes(search) || p.id.includes(search));

  const totalPages = Math.max(1, Math.ceil(filtered.length / PICKER_PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const paginated  = filtered.slice((safePage - 1) * PICKER_PAGE_SIZE, safePage * PICKER_PAGE_SIZE);

  const countOf = (t) => t === '전체' ? all.length : all.filter(p => p.status === t).length;

  return (
    <div className="p-8 max-w-[1080px]">
      {/* 헤더 */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-ink" style={{ letterSpacing: '-0.5px' }}>CDSS</h1>
          <span className="text-xs font-medium px-2.5 py-0.5 bg-primary/10 text-primary border border-primary/20 rounded-full">
            {loading ? '…' : `전체 ${all.length}명`}
          </span>
        </div>
        <p className="text-sm text-ink-subtle">분석할 환자를 선택하세요</p>
      </div>

      {/* 탭 + 검색 */}
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-1">
          {PICKER_TABS.map(t => (
            <button
              key={t}
              onClick={() => { setTab(t); setPage(1); }}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
              style={{
                background: tab === t ? '#5e6ad2' : 'transparent',
                color:      tab === t ? '#fff'     : 'var(--color-ink-subtle)',
              }}
            >
              {t}
              {!loading && (
                <span className="ml-1.5 text-xs opacity-70">
                  {countOf(t)}
                </span>
              )}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="이름 또는 ID 검색"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="px-3 py-2 text-sm bg-surface-1 border border-hairline rounded-lg text-ink outline-none focus:border-primary transition-colors w-56"
        />
      </div>

      {/* 테이블 */}
      <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
        {loading ? (
          <div className="py-14 text-center">
            <Loader2 size={20} className="inline text-ink-tertiary animate-spin mb-2" />
            <p className="text-sm text-ink-subtle">환자 목록 불러오는 중…</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-hairline bg-surface-2">
                {['환자명 / ID', 'CA-125', 'RMI', '위험도', '초음파', '상태'].map(h => (
                  <th key={h} className="text-left text-sm font-medium text-ink-subtle px-4 py-3 first:pl-5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-sm text-ink-tertiary">
                    {search ? '검색 결과 없음' : `'${tab}' 상태 환자가 없습니다`}
                  </td>
                </tr>
              ) : paginated.map(p => (
                <tr
                  key={p.id}
                  onClick={() => onSelect(p.subject_id)}
                  className="border-b border-hairline last:border-0 hover:bg-surface-2 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3">
                    <div className="text-sm font-medium text-ink">{p.name}</div>
                    <div className="text-xs text-ink-tertiary font-mono">{p.id}</div>
                  </td>
                  <td className={`px-4 py-3 text-sm font-mono ${p.ca125 != null && p.ca125 > 35 ? 'text-red-600' : 'text-ink'}`}>
                    {p.ca125 != null ? p.ca125.toLocaleString() : '—'}
                  </td>
                  <td className={`px-4 py-3 text-sm font-mono ${p.rmi > 200 ? 'text-red-600' : 'text-ink'}`}>
                    {p.rmi > 0 ? p.rmi.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {p.riskTier && p.riskTier !== 'UNKNOWN' ? (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${_RISK_COLOR[p.riskTier] ?? ''}`}>
                        {_RISK_LABEL[p.riskTier] ?? p.riskTier}
                      </span>
                    ) : <span className="text-sm text-ink-tertiary">—</span>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {dicomIds === null ? (
                      <span className="text-sm text-ink-tertiary">…</span>
                    ) : dicomIds.has(Number(p.subject_id)) ? (
                      <CheckCircle2 size={15} className="text-emerald-500 inline" />
                    ) : (
                      <span className="text-sm text-ink-tertiary">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${_STATUS_COLOR[p.status] ?? _STATUS_COLOR['신규']}`}>
                      {p.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* 페이지네이션 */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 px-1">
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
  );
}

const STATUS_COLORS = {
  '신규':    'bg-surface-2 text-ink-subtle border border-hairline',
  '관찰중':  'bg-blue-50 text-blue-600 border border-blue-200',
  '검토완료': 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  '의뢰완료': 'bg-violet-50 text-violet-700 border border-violet-200',
};

function CdssContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { user, role } = useAuth();
  const canWrite = role === 'doctor';

  const sid = searchParams.get('subject_id');

  const [patientName,   setPatientName]   = useState('');
  const [currentStatus, setCurrentStatus] = useState(null);
  // step: 'idle' | 'analyzing' | 'done' | 'saved'
  const [step,          setStep]          = useState('idle');
  const [pageLoading,   setPageLoading]   = useState(false);
  const [saving,        setSaving]        = useState(false);
  const [error,         setError]         = useState(null);
  // display_name → {value, unit, status}
  const [latestLabs,    setLatestLabs]    = useState({});
  const [prediction,    setPrediction]    = useState(null); // { probability_pct, prediction, risk_tier, tyg_index, ... }
  const [usResult,      setUsResult]      = useState(null); // ova_cdss_results 초음파 AI 결과
  const [rmiScore,      setRmiScore]      = useState(null);
  const [rmiMeta,       setRmiMeta]       = useState({ usScore: null, mFactor: null, ca125: null });
  const [savedAiImage,  setSavedAiImage]  = useState(null);

  useEffect(() => {
    if (!sid) return;
    const saved = localStorage.getItem(`saved_ai_image_${sid}`);
    if (saved) {
      try { setSavedAiImage(JSON.parse(saved)); } catch(e) {}
    } else {
      setSavedAiImage(null);
    }
  }, [sid]);

  const loadData = useCallback(() => {
    if (!sid) return;
    setPageLoading(true);
    setError(null);
    Promise.all([getPatientBasic(sid), getPatientStatus(sid), getLabsByDate(sid), getCdssResult(sid).catch(() => null)])
      .then(([patient, statusData, labsRaw, cdssRes]) => {
        setError(null);
        setPatientName(patient.patient_name || `환자 ${sid}`);
        const raw = patient.rmi_score;
        setRmiScore(raw != null && !Number.isNaN(Number(raw)) ? Math.round(raw) : null);
        setRmiMeta({
          usScore: patient.us_score        ?? null,
          mFactor: patient.menopause_factor ?? null,
          ca125:   (patient.ca125_value != null && !Number.isNaN(Number(patient.ca125_value)))
                     ? patient.ca125_value : null,
        });
        const s = statusData.status ?? '신규';
        setCurrentStatus(s);

        if (s === '신규' && canWrite) {
          updatePatientStatus(sid, '관찰중', null).catch(() => {});
          setCurrentStatus('관찰중');
        } else if (s === '검토완료' || s === '의뢰완료') {
          setStep('saved');
        }

        // 의사: 항상 XGBoost 자동 로드 / 간호사: 검토완료·의뢰완료 환자만 로드
        if (canWrite || s === '검토완료' || s === '의뢰완료') {
          runCdssPredict(sid)
            .then(r => {
              setPrediction(r);
              setStep(prev => prev === 'saved' ? 'saved' : 'done');
            })
            .catch(() => {});
        }

        // 초음파 AI 결과 (ova_cdss_results)
        if (cdssRes && cdssRes.subject_id) {
          setUsResult(cdssRes);
          // localStorage에 없으면 DB에 저장된 이미지 URL로 복원
          if (cdssRes.us_image_url) {
            const cached = localStorage.getItem(`saved_ai_image_${sid}`);
            if (!cached) {
              setSavedAiImage({ url: cdssRes.us_image_url, bbox: null });
            }
          }
        }

        // 가장 최근 날짜 기준 검사결과 추출 (display_name 키)
        const labs = {};
        if (Array.isArray(labsRaw) && labsRaw.length > 0) {
          labsRaw[0].results?.forEach(r => {
            labs[r.display_name] = { value: r.value, unit: r.unit, status: r.status, ref_range: r.ref_range ?? null };
          });
        }
        setLatestLabs(labs);
      })
      .catch(err => {
        setError(err.message);
        setPatientName(`환자 ${sid}`);
        setCurrentStatus('관찰중');
        setStep('idle');
      })
      .finally(() => setPageLoading(false));
  }, [sid, canWrite]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRunAnalysis = useCallback(async () => {
    setStep('analyzing');
    setPrediction(null);
    setError(null);
    try {
      const result = await runCdssPredict(sid);
      setPrediction(result);
      setStep('done');
    } catch (err) {
      setError(err.message);
      setStep('idle'); // 실패 시 idle로 복귀 (빈 결과 패널 방지)
    }
  }, [sid]);

  const handleSaveAnalysis = useCallback(async () => {
    setSaving(true);
    try {
      await updatePatientStatus(sid, '검토완료', user?.employee_id);
      setCurrentStatus('검토완료');
      setStep('saved');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, [sid, user]);

  const isAnalyzing = step === 'analyzing';
  const isReferred  = currentStatus === '의뢰완료';

  const sectionDots = [
    // 초음파 AI: 데이터 있으면 녹색, 없으면 amber
    isAnalyzing ? 'bg-hairline-strong animate-pulse' : usResult ? 'bg-emerald-500' : 'bg-hairline-strong',
    // TyG/혈액 AI: 예측값 있으면 녹색, idle이면 회색, 로딩 중 없으면 회색
    isAnalyzing ? 'bg-hairline-strong animate-pulse' : prediction ? 'bg-emerald-500' : 'bg-hairline-strong',
    // RMI: rmiScore 있으면 녹색, 없으면 회색
    isAnalyzing ? 'bg-hairline-strong animate-pulse' : rmiScore != null ? 'bg-emerald-500' : 'bg-hairline-strong',
    // 임상 결론: rmiScore나 prediction 어느 하나라도 있으면 녹색
    isAnalyzing ? 'bg-hairline-strong animate-pulse' : (rmiScore != null || prediction) ? 'bg-emerald-500' : 'bg-hairline-strong',
  ];

  // ── 환자 미선택 → 인라인 환자 선택기 ─────────────────────────────────────
  if (!sid) {
    return (
      <PatientPicker onSelect={(subjectId) => router.push(`/cdss?subject_id=${subjectId}`)} />
    );
  }

  return (
    <div className="p-8 max-w-[1080px] space-y-4">

      {/* ── 백엔드 연결 실패 배너 ────────────────────────────────────── */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm">
          <span className="text-red-500 font-semibold shrink-0">⚠ 백엔드 연결 실패</span>
          <span className="text-red-600 font-mono text-xs truncate">{error}</span>
          <button
            onClick={loadData}
            className="ml-auto shrink-0 px-3 py-1 text-xs font-medium bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* ── 헤더 카드 ───────────────────────────────────────────────── */}
      <div className="bg-surface-1 rounded-xl border border-hairline px-5 py-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <button
              onClick={() => router.push('/screening')}
              className="text-xs text-ink-tertiary hover:text-ink-subtle transition-colors mb-1 block"
            >
              ← 환자목록
            </button>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl font-semibold text-ink" style={{ letterSpacing: '-0.5px' }}>
                {pageLoading ? '불러오는 중…' : `${patientName} (${sid})`}
              </h1>
              {currentStatus && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[currentStatus] ?? STATUS_COLORS['신규']}`}>
                  {currentStatus}
                </span>
              )}
            </div>
          </div>

          <div className="shrink-0 ml-4">
            {isAnalyzing ? (
              <div className="flex items-center gap-2 px-3.5 py-2 bg-blue-50 border border-blue-200 rounded-lg">
                <Loader2 size={14} className="text-blue-500 animate-spin" />
                <span className="text-xs font-medium text-blue-600">분석 중…</span>
              </div>
            ) : step === 'done' && canWrite ? (
              <button
                onClick={handleSaveAnalysis}
                disabled={saving}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors disabled:opacity-60"
              >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {saving ? '저장 중…' : '분석 결과 저장'}
              </button>
            ) : step === 'saved' ? (
              <div className="flex items-center gap-2 px-3.5 py-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                <CheckCircle2 size={14} className="text-emerald-600" />
                <span className="text-s font-medium text-emerald-700">분석 완료</span>
              </div>
            ) : canWrite ? (
              <button
                onClick={handleRunAnalysis}
                disabled={pageLoading}
                className="px-3.5 py-2 text-xs font-medium bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors disabled:opacity-50"
              >
                분석 실행
              </button>
            ) : (
              <div className="flex items-center gap-2 px-3.5 py-2 bg-surface-2 border border-hairline rounded-lg">
                <span className="text-xs font-medium text-ink-subtle">분석 대기 중</span>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {['초음파 AI 분석', 'TyG / 혈액 AI', 'RMI 스코어', '임상 결론'].map((label, idx) => (
            <div key={label} className="flex items-center justify-between px-3 py-2 bg-surface-2 border border-hairline rounded-lg">
              <span className="text-s text-ink-subtle">{label}</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                sectionDots[idx] === 'bg-emerald-500' ? 'bg-emerald-50 text-emerald-700' :
                sectionDots[idx] === 'bg-amber-400'   ? 'bg-amber-50 text-amber-700' :
                sectionDots[idx].includes('blue')     ? 'bg-blue-50 text-blue-600' :
                'bg-surface-3 text-ink-tertiary'
              }`}>
                {sectionDots[idx] === 'bg-emerald-500' ? '완료' :
                 sectionDots[idx]?.includes('blue')     ? '분석중' : '대기'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── 분석 중 안내 ─────────────────────────────────────────────── */}
      {isAnalyzing && (
        <div className="text-center py-10">
          <Loader2 size={22} className="inline text-blue-500 animate-spin mb-3" />
          <p className="text-base text-blue-600 font-medium">AI 모델이 분석 중입니다…</p>
          <p className="text-base text-ink-tertiary mt-1">초음파 AI · XGBoost · RMI 스코어 계산 중</p>
        </div>
      )}

      {/* ── 분석 결과 패널 (분석 중이 아닐 때 항상 표시) ────────────────── */}
      {!isAnalyzing && !pageLoading && (
        <div className="space-y-4">

          {/* 상단 2단 레이아웃 */}
          <div className="grid grid-cols-[4fr_6fr] gap-4">

          {/* 왼쪽: 초음파 AI */}
          <div className="space-y-4">
              <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
                <SectionLabel>초음파 AI 분석 결과</SectionLabel>
                {savedAiImage && (
                  <div className="p-5 pb-0">
                    <div className="rounded-xl overflow-hidden border border-hairline bg-black flex flex-col">
                      <div className="bg-surface-2 px-3 py-1.5 text-xs font-semibold border-b border-hairline text-ink">
                        저장된 AI 분석 이미지
                      </div>
                      <div className="flex items-center justify-center p-2 relative h-[260px]">
                        <BboxOverlay imageUrl={savedAiImage.url} bbox={savedAiImage.bbox} />
                      </div>
                    </div>
                  </div>
                )}
                {usResult ? (
                  /* ── 초음파 AI 결과 있음 ── */
                  <div className="p-5">
                      <div className="grid grid-cols-3 gap-2 mb-4 ">
                        <MetricCell
                          label="종양 탐지"
                          value={usResult.us_tumor_detected ? '탐지됨' : '없음'}
                          highlight={usResult.us_tumor_detected}
                        />
                        <MetricCell
                          label="종양 크기"
                          value={usResult.us_tumor_size_cm2 != null ? `${usResult.us_tumor_size_cm2}` : null}
                          sub="cm²"
                        />
                        <MetricCell
                          label="악성 확률"
                          value={usResult.us_malignancy_prob != null ? `${Number(usResult.us_malignancy_prob).toFixed(1)}%` : null}
                          highlight={usResult.us_malignancy_prob != null && Number(usResult.us_malignancy_prob) >= 50}
                        />
                        <MetricCell
                          label="FIGO Stage"
                          value={usResult.us_tumor_detected && usResult.us_figo_stage
                            ? ({ early: 'I-II', late: 'III-IV', benign: '양성' }[usResult.us_figo_stage] ?? usResult.us_figo_stage)
                            : null}
                        />
                        <MetricCell
                          label="U score"
                          value={(() => {
                            const v = usResult.us_u_score ?? rmiMeta.usScore;
                            return v != null ? String(v) : null;
                          })()}
                          sub={(() => {
                            const v = usResult.us_u_score ?? rmiMeta.usScore;
                            return v === 0 ? '이상소견 없음' : v === 1 ? '저위험' : v === 3 ? '고위험' : null;
                          })()}
                        />
                        <MetricCell
                          label="종양 유형"
                          value={usResult.us_tumor_type ?? null}
                        />
                      </div>
                      <div className="pt-3.5 border-t border-hairline space-y-2">
                        {[
                          { label: '악성 (Malignant)', pct: usResult.us_malignancy_prob != null ? Number(usResult.us_malignancy_prob) : null, color: 'bg-red-400' },
                          { label: '양성 (Benign)',    pct: usResult.us_malignancy_prob != null ? Math.round((100 - Number(usResult.us_malignancy_prob)) * 10) / 10 : null, color: 'bg-emerald-400' },
                        ].map(({ label, pct, color }) => (
                          <div key={label}>
                            <div className="flex justify-between text-s mb-1">
                              <span className="text-ink-subtle">{label}</span>
                              <span className="text-ink font-mono font-semibold">{pct != null ? `${pct.toFixed(1)}%` : '—'}</span>
                            </div>
                            <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
                              {pct != null && <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(pct, 100)}%`, transition: 'width 0.6s ease' }} />}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                ) : (
                  /* ── 초음파 AI 결과 없음 ── */
                  <div className="p-6 flex items-start gap-4">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center">
                      <ImageIcon size={18} className="text-amber-500" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-ink mb-0.5">초음파 검사 요망</p>
                      <p className="text-xs text-ink-subtle leading-relaxed">
                        이 환자의 초음파 AI 분석 결과가 없습니다.<br />
                        초음파 검사 후 영상 데이터를 등록하면 ResNet-50 분석 결과가 표시됩니다.
                      </p>
                      <div className="mt-3 grid grid-cols-3 gap-2 max-w-xs">
                        {[
                          { label: '종양 탐지', value: '검사 필요' },
                          { label: '악성 확률', value: null },
                          { label: 'U score',   value: rmiMeta.usScore },
                        ].map(({ label, value }) => (
                          <div key={label} className="bg-surface-2 rounded-lg px-3 py-2">
                            <div className="text-xs text-ink-subtle mb-0.5">{label}</div>
                            <div className={`text-sm font-mono ${value != null ? 'text-ink' : 'text-ink-tertiary'}`}>
                              {value ?? '—'}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
          </div>

          {/* 오른쪽: 혈액 AI */}
          <div className="space-y-4">
            <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
              <SectionLabel>혈액검사 기반 AI 분석</SectionLabel>
              <div className="p-5 space-y-4">

                {/* 혈액 검사 수치 테이블 */}
                <div className="overflow-x-auto rounded-lg border border-hairline">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-hairline bg-surface-2">
                        <th className="px-4 py-1.5 text-left text-xs font-semibold text-ink-subtle">항목명</th>
                        <th className="px-4 py-1.5 text-right text-xs font-semibold text-ink-subtle">값</th>
                        <th className="px-4 py-1.5 text-left text-xs font-semibold text-ink-subtle">단위</th>
                        <th className="px-4 py-1.5 text-left text-xs font-semibold text-ink-subtle">참고범위</th>
                        <th className="px-4 py-1.5 text-left text-xs font-semibold text-ink-subtle">상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {LAB_DISPLAY.map(({ key, label, ref }) => {
                        const lab = latestLabs[key];
                        const abnormal = lab && lab.status !== 'normal';
                        return (
                          <tr key={key} className={`border-b border-hairline last:border-0 hover:bg-surface-2 transition-colors ${abnormal ? 'bg-red-50/40' : ''}`}>
                            <td className="px-4 py-1.5 text-sm font-semibold text-ink">{label}</td>
                            <td className={`px-4 py-1.5 text-sm font-semibold text-right font-mono ${
                              lab?.status === 'high' ? 'text-red-600' :
                              lab?.status === 'low'  ? 'text-blue-600' : 'text-ink'
                            }`}>
                              {lab?.value != null ? `${lab.value}${lab?.status !== 'normal' ? ' ↑' : ''}` : '—'}
                            </td>
                            <td className="px-4 py-1.5 text-sm text-ink-subtle">{lab?.unit ?? '—'}</td>
                            <td className="px-4 py-1.5 text-sm text-ink-subtle">{ref ?? '—'}</td>
                            <td className="px-4 py-1.5">
                              {lab ? (
                                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                                  lab.status === 'high' ? 'bg-red-50 text-red-600 border-red-200' :
                                  lab.status === 'low'  ? 'bg-blue-50 text-blue-600 border-blue-200' :
                                  'bg-emerald-50 text-emerald-700 border-emerald-200'
                                }`}>
                                  {lab.status === 'high' ? '높음' : lab.status === 'low' ? '낮음' : '정상'}
                                </span>
                              ) : '—'}
                            </td>
                          </tr>
                        );
                      })}
                        <tr className="border-b border-hairline last:border-0 hover:bg-surface-2 transition-colors">
                        <td className="px-4 py-2.5 text-sm font-semibold text-ink">TyG Index</td>
                        <td className={`px-4 py-2.5 text-sm font-semibold text-right font-mono ${
                          prediction?.tyg_index != null && prediction.tyg_index >= 4.5 ? 'text-red-600' : 'text-ink'
                        }`}>
                          {prediction?.tyg_index != null ? prediction.tyg_index.toFixed(2) : '—'}
                        </td>
                        <td className="px-4 py-1.5 text-sm text-ink-subtle">—</td>
                        <td className="px-4 py-1.5 text-sm text-ink-subtle">0–4.5</td>
                        <td className="px-4 py-1.5">
                          {prediction?.tyg_index != null ? (
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                              prediction.tyg_index >= 4.5
                                ? 'bg-red-50 text-red-600 border-red-200'
                                : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            }`}>
                              {prediction.tyg_index >= 4.5 ? '높음' : '정상'}
                            </span>
                          ) : '—'}
                        </td>
                      </tr>
                      </tbody>
                      </table>
                      </div>

                {/* XGBoost 예측 확률 카드 */}
                <div className="bg-surface-2 rounded-xl px-4 py-3.5 flex items-center justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">악성 종양 가능성</div>
                  {prediction ? (
                    <div className="flex-1 flex justify-center">
                      <div className={`text-3xl font-semibold font-mono leading-none ${
                        prediction.probability_pct >= 60 ? 'text-red-600' : 'text-emerald-600'
                      }`} style={{ letterSpacing: '-1px' }}>
                        {prediction.probability_pct.toFixed(1)}<span className="text-base font-normal ml-1 text-ink-subtle">%</span>
                      </div>
                    </div>
                  ) : step === 'idle' ? (
                    <div className="text-sm text-ink-tertiary py-2">
                      {canWrite ? '상단 "분석 실행" 버튼을 누르면 표시됩니다' : '의사의 분석 완료 후 확인 가능합니다'}
                    </div>
                  ) : (
                    <div className="flex-1 flex justify-center">
                      <div className="text-3xl font-semibold text-ink font-mono leading-none" style={{ letterSpacing: '-1px' }}>
                        —<span className="text-base font-normal ml-1 text-ink-subtle">%</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

          {/* RMI */}
          <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
            <SectionLabel>RMI 최종스코어</SectionLabel>
            <div className="p-5">


              <div className="grid grid-cols-5 gap-2">
                {/* U스코어: 초음파 AI 결과(us_u_score) 우선, 없으면 DB 저장값, 없으면 — */}
                <div className="bg-surface-2 rounded-lg px-3 py-2.5 flex flex-col justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">U score</div>
                  <div className="text-base font-semibold text-ink font-mono">
                    {usResult?.us_u_score != null ? String(usResult.us_u_score) : rmiMeta.usScore ?? '—'}
                  </div>
                  <div className="text-xs text-ink-tertiary mt-0.5">초음파 소견</div>
                </div>
                {/* M스코어 */}
                <div className="bg-surface-2 rounded-lg px-3 py-2.5 flex flex-col justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">M score</div>
                  <div className="text-base font-semibold text-ink font-mono">
                    {rmiMeta.mFactor ?? '—'}
                  </div>
                  <div className="text-xs text-ink-tertiary mt-0.5">
                    {rmiMeta.mFactor === 3 ? '폐경 후' : rmiMeta.mFactor === 1 ? '폐경 전' : '폐경 인자'}
                  </div>
                </div>
                {/* CA-125 */}
                <div className="bg-surface-2 rounded-lg px-3 py-2.5 flex flex-col justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">CA-125</div>
                  <div className="text-base font-semibold text-ink font-mono">
                    {rmiMeta.ca125 != null ? rmiMeta.ca125.toLocaleString() : '—'}
                  </div>
                  <div className="text-xs text-ink-tertiary mt-0.5">U/mL</div>
                </div>
                {/* RMI 공식 */}
                <div className="bg-surface-2 rounded-lg px-3 py-2.5 flex flex-col justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">RMI 공식</div>
                  <div className="text-sm font-semibold text-ink font-mono">
                    {rmiMeta.ca125 != null && rmiMeta.mFactor != null
                      ? `${usResult?.us_u_score ?? rmiMeta.usScore ?? '—'} × ${rmiMeta.mFactor} × ${rmiMeta.ca125.toLocaleString()}`
                      : '—'}
                  </div>
                  <div className="text-xs text-ink-tertiary mt-0.5">U × M × CA-125</div>
                </div>
                {/* RMI 점수 */}
                <div className="bg-surface-2 rounded-lg px-3 py-2.5 flex flex-col justify-between">
                  <div className="text-s text-ink-subtle uppercase tracking-wide mb-1">최종 RMI 점수</div>
                  <div className={`text-xl font-semibold font-mono ${
                    rmiScore == null       ? 'text-ink' :
                    rmiScore >= 200        ? 'text-red-600' :
                    rmiScore >= 25         ? 'text-amber-600' : 'text-emerald-600'
                  }`}>
                    {rmiScore != null ? rmiScore.toLocaleString() : '—'}
                  </div>
                  <div className={`text-xs mt-1 font-semibold ${
                    rmiScore == null       ? 'text-ink-tertiary' :
                    rmiScore >= 200        ? 'text-red-500' :
                    rmiScore >= 25         ? 'text-amber-500' : 'text-emerald-500'
                  }`}>
                    {rmiScore == null ? '' : rmiScore >= 200 ? 'HIGH' : rmiScore >= 25 ? 'MODERATE' : 'LOW'}
                  </div>
                </div>
              </div>
              <p className="mt-3 text-xs text-ink-tertiary pt-2.5 border-t border-hairline">
                기준: RMI ≥ 200 → HIGH &nbsp;·&nbsp; 25–199 → MODERATE &nbsp;·&nbsp; &lt; 25 → LOW
              </p>
            </div>
          </div>

          {/* 통합 임상 결론 */}
          <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
            <SectionLabel>통합 임상 결론</SectionLabel>
            <div className="p-5">
              {(() => {
                let cfg;
                if (rmiScore == null) {
                  cfg = {
                    border: 'border-l-4 border-surface-3 bg-surface-2',
                    dot:    'bg-surface-3',
                    title:  'RMI 데이터 없음',
                    desc:   'RMI 점수를 계산한 뒤 다시 확인하세요.',
                    badge:  null,
                  };
                } else if (rmiScore >= 200) {
                  cfg = {
                    border: 'border-l-4 border-red-500 bg-red-50',
                    dot:    'bg-red-500',
                    title:  '3차 상급종합병원 전원 권고',
                    desc:   '종양내과 및 부인암 전문 외과 협진 의뢰가 필요합니다.',
                    badge:  { label: `RMI ${rmiScore}`, cls: 'bg-red-100 text-red-700' },
                  };
                } else if (rmiScore >= 25) {
                  cfg = {
                    border: 'border-l-4 border-amber-400 bg-amber-50',
                    dot:    'bg-amber-400',
                    title:  '추가 정밀검사 필요',
                    desc:   '골반 MRI, CT, 복강경 등 추가 검사를 권고합니다.',
                    badge:  { label: `RMI ${rmiScore}`, cls: 'bg-amber-100 text-amber-700' },
                  };
                } else {
                  cfg = {
                    border: 'border-l-4 border-emerald-500 bg-emerald-50',
                    dot:    'bg-emerald-500',
                    title:  '정기 추적관찰 권장',
                    desc:   '6개월 간격 초음파 및 CA-125 추적 관찰을 권장합니다.',
                    badge:  { label: `RMI ${rmiScore}`, cls: 'bg-emerald-100 text-emerald-700' },
                  };
                }
                return (
                  <div className={`p-4 rounded-lg mb-4 flex items-start gap-3 ${cfg.border}`}>
                    <div className={`w-3 h-3 rounded-full mt-0.5 shrink-0 ${cfg.dot}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-ink">{cfg.title}</span>
                        {cfg.badge && (
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cfg.badge.cls}`}>
                            {cfg.badge.label}
                          </span>
                        )}
                        {prediction && (
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            prediction.probability_pct >= 60 ? 'bg-red-100 text-red-700' :
                            prediction.probability_pct >= 40 ? 'bg-amber-100 text-amber-700' :
                                                               'bg-emerald-100 text-emerald-700'
                          }`}>
                            혈액검사 기반 예측률 {prediction.probability_pct.toFixed(1)}%
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-ink-subtle mt-0.5">{cfg.desc}</div>
                    </div>
                  </div>
                );
              })()}

              <p className="text-center font-semibold text-s text-ink-tertiary mb-3">
                본 결과는 AI 보조 참고 자료이며, 최종 임상 판단은 담당 의사의 책임입니다.
              </p>

              {isReferred ? (
                <div className="flex gap-2">
                  <div className="flex-1 py-2.5 font-bold rounded-lg text-base font-medium text-center bg-violet-50 text-violet-700 border border-violet-200">
                    <CheckCircle2 size={14} className="inline mr-1.5 mb-0.5" />
                    의뢰 완료
                  </div>
                  <button
                    onClick={() => router.push(`/reports?subject_id=${sid}`)}
                    className="px-4 py-2.5 rounded-lg text-sm font-medium border border-violet-300 text-violet-700 hover:bg-violet-50 transition-colors whitespace-nowrap"
                  >
                    의뢰서 보기 →
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => canWrite && router.push(`/reports?subject_id=${sid}`)}
                  disabled={!canWrite}
                  className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5 ${
                    canWrite
                      ? 'bg-primary hover:bg-primary-hover text-white'
                      : 'bg-surface-2 text-ink-subtle border border-hairline cursor-not-allowed opacity-60'
                  }`}
                >
                  <FileText size={14} />
                  의뢰서 작성{!canWrite && <span className="ml-1 text-xs opacity-70">(의사 전용)</span>}
                </button>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}

export default function CdssPage() {
  return (
    <Suspense fallback={null}>
      <CdssContent />
    </Suspense>
  );
}