'use client';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getPatientDetail, getPatients, getComorbidities } from '@/lib/api';
import RiskBadge, { StatusBadge } from '@/components/RiskBadge';

// ── 혈액 수치 항목 정의 ──────────────────────────────────────────────────────
const KEY_LABS = [
  { name: 'CA-125',        label: 'CA-125' },
  { name: 'Glucose',       label: 'Glucose' },
  { name: 'Triglycerides', label: 'Triglycerides' },
  { name: 'TyG',           label: 'TyG Index' },
];

const GENERAL_LABS = [
  { name: 'Albumin',                          label: 'Albumin' },
  { name: 'Aspartate Aminotransferase (AST)', label: 'AST' },
  { name: 'Alanine Aminotransferase (ALT)',   label: 'ALT' },
  { name: 'Urea Nitrogen (BUN)',              label: 'BUN' },
  { name: 'Hemoglobin',                       label: 'Hemoglobin' },
  { name: 'HDL Cholesterol',                  label: 'HDL' },
  { name: 'Platelet Count',                   label: 'Platelet' },
  { name: 'INR(PT)',                          label: 'PT-INR' },
  { name: 'White Blood Cells',                label: 'WBC' },
];

const RISK_COLOR = {
  HIGH:     'bg-red-500',
  MODERATE: 'bg-amber-400',
  LOW:      'bg-green-500',
};

// U스코어 레이블
function fmtUscore(v) {
  if (v === 0) return '0 (특이소견 없음)';
  if (v === 1) return '1 (저위험)';
  if (v === 3) return '3 (고위험)';
  return '—';
}

// M스코어 레이블
function fmtMfactor(v) {
  if (v === 1) return '1 (폐경 전)';
  if (v === 3) return '3 (폐경 후)';
  return '—';
}

export default function PatientDetailPage() {
  const { id }  = useParams();
  const router  = useRouter();

  const [patient,         setPatient]         = useState(null);
  const [sidebarPatients, setSidebarPatients] = useState([]);
  const [comorbidities,   setComorbidities]   = useState(null);
  const [loading,         setLoading]         = useState(true);
  const [error,           setError]           = useState(null);
  const [selectedDate,    setSelectedDate]    = useState(null);
  const [sidebarSearch,   setSidebarSearch]   = useState('');
  const [sidebarPage, setSidebarPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getPatientDetail(id),
      getPatients(1, 300),
      getComorbidities(id).catch(() => null),
    ])
      .then(([detail, { patients }, comorbData]) => {
        setPatient(detail);
        setSidebarPatients(patients);
        setComorbidities(comorbData);
        setSelectedDate(detail.labResultsByDate[0]?.date ?? null);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-5 h-5 border-2 border-surface-3 border-t-primary rounded-full animate-spin mb-3" />
          <p className="text-sm text-ink-subtle">환자 정보 불러오는 중…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm">
          <span className="text-red-500 font-semibold shrink-0">⚠ 백엔드 연결 실패</span>
          <span className="text-red-600 font-mono text-xs truncate">{error}</span>
          <button
            onClick={() => router.push('/screening')}
            className="ml-auto shrink-0 px-3 py-1 text-xs font-medium bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
          >
            목록으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-ink-subtle mb-3">환자 정보를 찾을 수 없습니다.</p>
          <button onClick={() => router.push('/screening')} className="text-xs text-primary underline">
            목록으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  const { labResultsByDate, rmi } = patient;
  const labResults = labResultsByDate.find(d => d.date === selectedDate)?.results ?? [];
  const tygIndex = (() => {
    const tg = labResults.find(r => r.test_name === 'Triglycerides')?.value;
    const glucose = labResults.find(r => r.test_name === 'Glucose')?.value;
    if (!tg || !glucose) return null;
    return (Math.log(tg * glucose) / 2).toFixed(2);
  })();

  const findLab = (name) => {
    if (name === 'TyG') {
      if (tygIndex == null) return null;
      return {
        value: tygIndex,
        unit: '',
        ref_range: '0-4.5',
        status: tygIndex >= 4.5 ? 'high' : 'normal',
      };
    }
    return labResults.find(r => r.test_name === name) ?? null;
  };


  return (
    <>
    <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 64px)' }}>

      {/* ── 왼쪽 환자 목록 사이드바 ── */}
      <aside className="hidden lg:flex w-56 shrink-0 bg-surface-1 border-r border-hairline flex-col overflow-hidden">
        <div className="px-4 py-4 border-b border-hairline shrink-0">
          <button
            onClick={() => router.push('/screening')}
            className="flex items-center gap-1.5 text-xs text-ink-tertiary hover:text-ink-subtle transition-colors mb-3"
          >
            ← 환자목록
          </button>
          <p className="text-s font-semibold text-ink-subtle uppercase tracking-wider mb-2">환자 목록</p>
          <input
            type="text"
            placeholder="이름 · 등록번호 검색"
            value={sidebarSearch}
            onChange={e => { setSidebarSearch(e.target.value); setSidebarPage(1); }}
            className="w-full px-2.5 py-1.5 text-xs border border-hairline rounded-lg outline-none focus:border-primary transition-colors bg-surface-2 text-ink"
          />
        </div>
        <nav className="flex-1 py-2" style={{ overflowY: 'auto', minHeight: 0 }}>
          {(() => {
            const filtered = sidebarPatients.filter(p =>
              p.name.includes(sidebarSearch) || p.id.toLowerCase().includes(sidebarSearch.toLowerCase())
            );
            const paged = filtered.slice((sidebarPage - 1) * 10, sidebarPage * 10);
            return (
              <>
                {paged.map(p => {
                  const isActive = p.id === id;
                  return (
                    <button
                      key={p.id}
                      onClick={() => router.push(`/patients/${p.id}`)}
                      className={`w-full text-left px-4 py-3 transition-colors border-l-2 ${
                        isActive ? 'bg-surface-2 border-primary' : 'border-transparent hover:bg-surface-2'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-semibold ${isActive ? 'text-ink' : 'text-ink-muted'}`}>
                          {p.name}
                        </span>
                        <span className={`w-2 h-2 rounded-full shrink-0 ${RISK_COLOR[p.riskTier] ?? 'bg-ink-tertiary'}`} />
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-ink-tertiary font-mono">{p.id}</span>
                        <span className="text-xs text-hairline-strong">·</span>
                        <span className="text-xs text-ink-tertiary">{p.age}세</span>
                      </div>
                    </button>
                  );
                })}
                <div className="sticky bottom-0 bg-surface-1 border-t border-hairline flex items-center justify-center gap-1 py-2 w-full">
                  {Array.from({ length: Math.ceil(filtered.length / 10) }, (_, i) => i + 1)
                    .filter(page => page >= sidebarPage - 2 && page <= sidebarPage + 2)
                    .map(page => (
                      <button
                        key={page}
                        onClick={() => setSidebarPage(page)}
                        className={`w-6 h-6 text-xs rounded-md transition-colors ${
                          sidebarPage === page
                            ? 'bg-primary text-white font-bold'
                            : 'text-ink-tertiary hover:bg-surface-2'
                        }`}
                      >
                        {page}
                      </button>
                    ))}
                </div>
              </>
            );
          })()}
        </nav>
      </aside>

      {/* ── 메인 콘텐츠 ── */}
      <div className="flex-1 bg-canvas min-w-0 p-4 lg:p-8" style={{ overflowY: 'auto', height: '100%' }}>

        {/* 모바일 뒤로가기 */}
        <button
          onClick={() => router.push('/screening')}
          className="lg:hidden flex items-center gap-1.5 text-xs text-ink-tertiary hover:text-ink-subtle transition-colors mb-4"
        >
          ← 환자목록
        </button>

        {/* ── 환자 헤더 ── */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
          <div className="min-w-0">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h1 className="text-xl lg:text-2xl font-bold text-ink" style={{ letterSpacing: '-0.5px' }}>
                {patient.patient_name}
              </h1>
              <RiskBadge tier={patient.risk_level} />
              <StatusBadge status={patient.status} />
            </div>
            <div className="flex items-center gap-2.5 text-sm text-ink-subtle flex-wrap mb-1.5">
              <span className="font-mono text-xs bg-surface-2 border border-hairline px-2 py-0.5 rounded font-semibold text-ink">
                {patient.pt_id}
              </span>
              <span className="text-hairline-strong">|</span>
              <span>등록번호: <strong className="text-ink-muted">{patient.patient_reg_no}</strong></span>
              <span className="text-hairline-strong">|</span>
              <span>출생연도: <strong className="text-ink-muted">{patient.birth_ym}</strong></span>
              <span className="text-hairline-strong">|</span>
              <span>나이: <strong className="text-ink-muted">{patient.diag_att_age}세</strong></span>
            </div>
            <div className="text-xs text-ink-tertiary">마지막 업데이트: {patient.last_updated}</div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => router.push(`/pacs?case_code=${patient.subject_id}&subject_id=${patient.subject_id}`)}
              className="px-4 py-2 text-sm border border-hairline rounded-xl hover:border-hairline-strong bg-surface-1 transition-colors text-ink-subtle hover:text-ink">
              PACS 열기
            </button>
            <button
              onClick={() => router.push(`/cdss?subject_id=${id}`)}
              className="px-5 py-2 text-sm font-semibold bg-primary hover:bg-primary-hover text-white rounded-xl transition-colors">
              CDSS 분석 실행
            </button>
          </div>
        </div>

        {/* ── 본문: 2단 레이아웃 ── */}
        <div className="grid gap-5 grid-cols-1 lg:grid-cols-[240px_1fr]">

          {/* ── 왼쪽 열: 기본 정보 + RMI ── */}
          <div className="flex flex-col gap-5">

            {/* 기본 정보 카드 */}
            <div className="bg-surface-1 rounded-xl border border-hairline p-5">
              <SectionTitle>기본 정보</SectionTitle>
              <div className="space-y-4">
                <InfoRow label="PT ID"      value={patient.pt_id}          mono />
                <InfoRow label="환자등록번호" value={patient.patient_reg_no} />
                <InfoRow label="Birth YM"   value={patient.birth_ym}       />
                <InfoRow label="나이"        value={`${patient.diag_att_age}세`} />
                <InfoRow label="성별"        value={patient.gender === 'F' ? '여성' : patient.gender === 'M' ? '남성' : '—'} />
                <InfoRow
                  label="폐경 여부"
                  value={
                    patient.menopause != null
                      ? (patient.menopause ? '예 (폐경 후)' : '아니오 (폐경 전)')
                      : rmi?.menopause_factor === 3
                        ? '폐경 후'
                        : rmi?.menopause_factor === 1
                          ? '폐경 전'
                          : '정보 없음'
                  }
                  dimmed={patient.menopause == null && rmi?.menopause_factor == null}
                />
                <InfoRow label="주요 증상"   value={patient.symptoms ?? '정보 없음'} dimmed={!patient.symptoms} />
                <div className="border-t border-hairline pt-4 space-y-4">
                  <InfoRow label="키"   value={patient.height ?? '—'} unit="cm"  dimmed={!patient.height} />
                  <InfoRow label="몸무게" value={patient.weight ?? '—'} unit="kg"  dimmed={!patient.weight} />
                  <InfoRow label="BMI"  value={patient.bmi    ?? '—'}             dimmed={!patient.bmi} />
                </div>
              </div>
              {!patient.height && (
                <p className="mt-3 text-[11px] text-ink-tertiary leading-tight">
                  * 키·몸무게·BMI는 현재 DB에 데이터 없음
                </p>
              )}
            </div>

            {/* 기저질환 카드 */}
            <div className="bg-surface-1 rounded-xl border border-hairline p-5">
              <SectionTitle>기저질환</SectionTitle>
              {comorbidities === null ? (
                <div className="flex flex-wrap gap-2">
                  {['당뇨', '고혈압', '고지혈증'].map(label => (
                    <span key={label} className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-hairline bg-surface-2 text-ink-tertiary animate-pulse">
                      {label}
                    </span>
                  ))}
                </div>
              ) : !comorbidities.has_diabetes && !comorbidities.has_hypertension && !comorbidities.has_hyperlipidemia ? (
                <span className="text-sm text-ink-tertiary">해당 없음</span>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {comorbidities.has_diabetes && (
                    <ComorbiditiBadge label="당뇨" activeClass="bg-amber-50 text-amber-700 border-amber-300" />
                  )}
                  {comorbidities.has_hypertension && (
                    <ComorbiditiBadge label="고혈압" activeClass="bg-red-50 text-red-700 border-red-300" />
                  )}
                  {comorbidities.has_hyperlipidemia && (
                    <ComorbiditiBadge label="고지혈증" activeClass="bg-purple-50 text-purple-700 border-purple-300" />
                  )}
                </div>
              )}
            </div>

            {/* RMI 계산값 카드 */}
            <div className="bg-surface-1 rounded-xl border border-hairline p-5">
              <SectionTitle>RMI 계산값</SectionTitle>
              <div className="space-y-4">
                <InfoRow label="U 스코어"  value={fmtUscore(rmi?.us_score)} />
                <InfoRow label="M 스코어"  value={fmtMfactor(rmi?.menopause_factor)} />
                <InfoRow
                  label="CA-125"
                  value={rmi?.ca125_value != null ? rmi.ca125_value.toLocaleString() : '—'}
                  unit="U/mL"
                  highlight={rmi?.ca125_value != null && rmi.ca125_value > 35}
                />
                <InfoRow
                  label="RMI 점수"
                  value={rmi?.rmi_score != null ? rmi.rmi_score.toLocaleString() : '—'}
                  highlight={rmi?.rmi_score != null && rmi.rmi_score >= 200}
                />
                <div>
                  <div className="text-xs font-medium text-ink-subtle mb-1">위험도</div>
                  {rmi?.risk_level
                    ? <RmiRiskBadge level={rmi.risk_level} />
                    : <span className="text-sm text-ink-tertiary">—</span>
                  }
                </div>
                {rmi?.ca125_value > 35 && rmi?.us_score === 0 && (
                  <div className="flex items-start gap-2 px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg">
                    <span className="text-amber-500 text-sm shrink-0 mt-0.5">⚠</span>
                    <div>
                      <p className="text-xs font-semibold text-amber-700">CA-125 추적 관찰 필요</p>
                      <p className="text-xs text-amber-600 mt-0.5">U스코어 0 (이상소견 없음)이나 CA-125가 기준치(35 U/mL) 초과 — 추적 검사를 권장합니다.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── 오른쪽 열: 혈액검사 ── */}
          <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">

            {/* 섹션 헤더 */}
            <div className="px-5 py-3 bg-primary/10 border-b border-hairline flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-1 h-4 rounded-full bg-primary" />
                <span className="text-lg font-bold text-primary">혈액검사 결과</span>
              </div>
              {labResultsByDate.length > 0 && (
                <select
                  value={selectedDate ?? ''}
                  onChange={e => setSelectedDate(e.target.value)}
                  className="text-xs border border-hairline rounded-lg px-2.5 py-1.5 bg-surface-2 outline-none focus:border-primary transition-colors text-ink-subtle"
                >
                  {labResultsByDate.map(({ date }) => (
                    <option key={date} value={date}>{date}</option>
                  ))}
                </select>
              )}
            </div>
            {labResultsByDate.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-ink-tertiary">검사 결과 데이터가 없습니다</div>
            ) : (
              <div className="p-5 space-y-5">

                {/* 핵심 지표 카드 3개 */}
                <div>
                  <p className="text-s font-semibold text-ink-subtle uppercase tracking-wider mb-3">핵심 지표</p>
                  <div className="grid grid-cols-4 gap-2">
                    {KEY_LABS.map(({ name, label }) => (
                      <KeyLabCard key={name} label={label} lab={findLab(name)} />
                    ))}
                  </div>
                </div>

                {/* 일반 지표 테이블 */}
                <div>
                  <p className="text-s font-semibold text-ink-subtle uppercase tracking-wider mb-3">일반 지표</p>
                  <div className="overflow-x-auto rounded-lg border border-hairline">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b font-bold border-hairline bg-surface-2">
                          <LabTh>항목명</LabTh>
                          <LabTh right>값</LabTh>
                          <LabTh>단위</LabTh>
                          <LabTh>참고범위</LabTh>
                          <LabTh>상태</LabTh>
                        </tr>
                      </thead>
                      <tbody>
                        {GENERAL_LABS.map(({ name, label, aiNote }) => {
                          const lab      = findLab(name);
                          const abnormal = lab && lab.status !== 'normal';
                          return (
                            <tr
                              key={name}
                              className={`border-b border-hairline last:border-0 hover:bg-surface-2 transition-colors ${abnormal ? 'bg-red-50/40' : ''}`}
                            >
                              <td className="px-4 py-2.5 text-sm font-semibold text-ink whitespace-nowrap">
                                {label}
                                {aiNote && (
                                  <span className="ml-2 text-[10px] text-ink-tertiary bg-surface-3 border border-hairline px-1.5 py-0.5 rounded-full font-normal">
                                    AI 미사용
                                  </span>
                                )}
                              </td>
                              <td className={`px-4 py-2.5 text-sm font-bold text-right tabular-nums ${lab ? (abnormal ? 'text-red-600' : 'text-ink') : 'text-ink-tertiary'}`}>
                                {lab ? (
                                  <>
                                    {lab.value.toLocaleString()}
                                    {abnormal && <span className="text-xs ml-0.5">↑</span>}
                                  </>
                                ) : '—'}
                              </td>
                              <td className="px-4 py-2.5 text-sm text-ink-subtle">{lab?.unit || '—'}</td>
                              <td className="px-4 py-2.5 text-sm text-ink-subtle font-mono">{lab?.ref_range || '—'}</td>
                              <td className="px-4 py-2.5">
                                {lab ? <LabStatusBadge status={lab.status} /> : <span className="text-xs text-ink-tertiary">—</span>}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>
            )}
          </div>

        </div>
      </div>
    </div>
    </>
  );
}

/* ── 서브 컴포넌트 ──────────────────────────────────────────────────────────── */

function SectionTitle({ children }) {
  return (
    <h2 className="text-base font-bold text-ink-subtle uppercase tracking-wider mb-4">
      {children}
    </h2>
  );
}

function InfoRow({ label, value, unit, mono, highlight, dimmed }) {
  return (
    <div>
      <div className="text-xs font-medium text-ink-subtle mb-0.5">{label}</div>
      <div className={`text-sm font-semibold leading-snug ${
        highlight ? 'text-red-600' : dimmed ? 'text-ink-tertiary' : 'text-ink'
      } ${mono ? 'font-mono' : ''}`}>
        {value ?? '—'}
        {unit && value && value !== '—' && (
          <span className="text-xs font-normal text-ink-subtle ml-1">{unit}</span>
        )}
      </div>
    </div>
  );
}

function RmiRiskBadge({ level }) {
  const map = {
    HIGH:     { label: '고위험 (HIGH)',     cls: 'bg-red-50 text-red-700 border-red-200' },
    MODERATE: { label: '중위험 (MODERATE)', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
    LOW:      { label: '저위험 (LOW)',      cls: 'bg-green-50 text-green-700 border-green-200' },
  };
  const cfg = map[level] ?? { label: level, cls: 'bg-surface-2 text-ink-subtle border-hairline' };
  return (
    <span className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-lg border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

function KeyLabCard({ label, lab }) {
  const hasData  = lab != null;
  const abnormal = hasData && lab.status !== 'normal';

  return (
    <div className={`rounded-xl border p-4 ${
      abnormal ? 'border-red-200 bg-red-50/40' : 'border-hairline bg-white'
    }`}>
      <div className="text-xs font-semibold text-ink-subtle uppercase tracking-wider mb-2">{label}</div>
      <div className={`text-2xl font-bold font-mono tabular-nums leading-none mb-1 ${
        abnormal ? 'text-red-600' : 'text-ink'
      }`}>
        {hasData ? (
          <>
            {typeof lab.value === 'number' ? lab.value.toLocaleString() : lab.value}
            {abnormal && <span className="text-base ml-0.5">↑</span>}
          </>
        ) : '—'}
      </div>
      <div className="text-xs text-ink-subtle mb-2">{hasData ? (lab.unit || '\u00A0') : '—'}</div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-ink-tertiary font-mono">기준 {hasData ? lab.ref_range : '—'}</span>
        {hasData && <LabStatusBadge status={lab.status} />}
      </div>
    </div>
  );
}

function ComorbiditiBadge({ label, activeClass }) {
  return (
    <span className={`text-xs font-semibold px-3 py-1.5 rounded-lg border flex items-center gap-1.5 ${activeClass}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

function LabTh({ children, right }) {
  return (
    <th className={`px-4 py-2.5 text-sm font-bold text-ink-subtle whitespace-nowrap ${right ? 'text-right' : 'text-left'}`}>
      {children}
    </th>
  );
}

function LabStatusBadge({ status }) {
  const map = {
    high:   { label: '높음', cls: 'bg-red-50 text-red-600 border-red-200' },
    low:    { label: '낮음', cls: 'bg-blue-50 text-blue-600 border-blue-200' },
    normal: { label: '정상', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  };
  const cfg = map[status] ?? { label: status, cls: 'bg-surface-2 text-ink-subtle border-hairline' };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}
