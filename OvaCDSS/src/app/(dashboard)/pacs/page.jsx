'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useSearchParams } from 'next/navigation';
import { ImageIcon, CheckSquare, Square, Maximize2, X, ChevronRight, Save } from 'lucide-react';
import { getPatients, getPatientBasic, getCdssResult, getDicomSubjectIds } from '@/lib/api';
import BboxOverlay from '@/components/BboxOverlay';

// ─── 반원형 게이지 ───────────────────────────────────────────
function GaugeChart({ value, color }) {
  const r = 54;
  const circ = Math.PI * r;
  const pct = value != null ? Math.min(Math.max(value, 0), 100) : 0;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width="140" height="90" viewBox="0 0 140 90">
      <path d="M 14 76 A 56 56 0 0 1 126 76" fill="none" stroke="#e5e7eb" strokeWidth="12" strokeLinecap="round" />
      <path d="M 14 76 A 56 56 0 0 1 126 76" fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="70" y="68" textAnchor="middle" fontSize="22" fontWeight="bold" fill={color}>{value != null ? `${value}%` : '—'}</text>
      <text x="70" y="82" textAnchor="middle" fontSize="9" fill="#9ca3af">악성 가능성</text>
    </svg>
  );
}

// ─── 이미지 확대 모달 ────────────────────────────────────────
function ImageModal({ title, subtitle, children, onClose }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80" onClick={onClose}>
      <div className="relative bg-black rounded-2xl border border-hairline overflow-hidden w-[95vw] max-w-[1400px] max-h-[95vh] flex flex-col">
        <div className="bg-surface-2 px-4 py-2 text-xs font-semibold border-b border-hairline text-ink flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span>{title}</span>
            {subtitle && <span className="font-normal text-ink-tertiary">{subtitle}</span>}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-3 text-ink-tertiary hover:text-ink transition-colors">
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-2 overflow-auto min-h-0">{children}</div>
      </div>
    </div>
  );
}

// ─── 이미지 프레임 ───────────────────────────────────────────
function ImageFrame({ title, subtitle, children, modalChildren, headerAction }) {
  const [modalOpen, setModalOpen] = useState(false);
  return (
    <>
      <div className="rounded-xl border border-hairline bg-black flex flex-col overflow-hidden">
        <div className="bg-surface-2 px-3 py-1.5 text-xs font-semibold border-b border-hairline text-ink flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>{title}</span>
            {subtitle && <span className="font-normal text-ink-tertiary">{subtitle}</span>}
          </div>
          {headerAction && <div>{headerAction}</div>}
        </div>
        <div className="flex items-center justify-center p-3 relative h-[260px]">
          {children}
          <button onClick={() => setModalOpen(true)} className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-black/60 text-white hover:bg-black/90 transition-colors">
            <Maximize2 size={13} />
          </button>
        </div>
      </div>
      {modalOpen && (
        <ImageModal title={title} subtitle={subtitle} onClose={() => setModalOpen(false)}>
          {modalChildren ?? children}
        </ImageModal>
      )}
    </>
  );
}

// ─── 환자 기본 정보 ───────────────────────────────────────────
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

// ─── AI 결과 카드 ────────────────────────────────────────────
function AiCard({ label, value, sub, highlight }) {
  return (
    <div className="bg-surface-1 rounded-xl border border-hairline p-3 flex flex-col gap-1">
      <span className="text-s text-ink-tertiary">{label}</span>
      <span className={`text-xl font-bold ${highlight ? 'text-red-500' : 'text-ink'}`}>{value ?? '—'}</span>
      {sub && <span className="text-s text-ink-tertiary">{sub}</span>}
    </div>
  );
}

// ─── 체크 아이템 ─────────────────────────────────────────────
function CheckItem({ label, value, onChange }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors
        ${value ? 'bg-primary/10 border-primary/40 text-primary' : 'bg-surface-2 border-hairline text-ink-subtle hover:border-primary/30 hover:text-ink'}`}
    >
      {value ? <CheckSquare size={13} className="shrink-0" /> : <Square size={13} className="shrink-0" />}
      {label}
    </button>
  );
}

// ─── U스코어 체크 뱃지 ───────────────────────────────────────
function UBadge({ label, value }) {
  const checked = value === true;
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-sm
      ${checked ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-surface-2 border-hairline text-ink-tertiary'}`}>
      {checked
        ? <CheckSquare size={12} className="shrink-0" />
        : <Square size={12} className="shrink-0 opacity-40" />}
      {label}
    </div>
  );
}

const INIT_MANUAL = { wall_irregularity: false, papillary_projection: false, vascularity: false };

export default function PacsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseCode  = searchParams.get('case_code') ?? '—';
  const subjectId = searchParams.get('subject_id') ?? '—';

  // ── state ──────────────────────────────────────────────────
  const [patientData,     setPatientData]     = useState(null);
  const [sidebarPatients, setSidebarPatients] = useState([]);
  const [sidebarSearch,   setSidebarSearch]   = useState('');
  const [manualInput,     setManualInput]     = useState(INIT_MANUAL);
  const [selectedIdx,     setSelectedIdx]     = useState(0);
  const [showDetail,      setShowDetail]      = useState(false);
  const [dicomImages,     setDicomImages]     = useState([]);
  const [aiResult,        setAiResult]        = useState(null);
  const [finalResult,     setFinalResult]     = useState(null);
  const [dbCdssResult,    setDbCdssResult]    = useState(null);
  const [inferring,       setInferring]       = useState(false);
  const [finalInferring,  setFinalInferring]  = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportText, setReportText] = useState('');
  const [highlight, setHighlight] = useState(false);
  const [sidebarPage, setSidebarPage] = useState(1);
  const [dicomSubjectIds, setDicomSubjectIds] = useState(null); // null = 로딩 중
  const [onlyWithImages, setOnlyWithImages] = useState(false);

  // ── useEffect ──────────────────────────────────────────────
  // 사이드바 환자 목록 (api.js 경유 → 한국 이름 포함)
  useEffect(() => {
    getPatients(1, 300)
      .then(({ patients }) => setSidebarPatients(patients))
      .catch(() => {});
    getDicomSubjectIds()
      .then(ids => setDicomSubjectIds(ids))
      .catch(() => setDicomSubjectIds(new Set()));
  }, []);

  // 환자 기본 데이터 (api.js 경유 → birth_ym 포함)
  useEffect(() => {
    if (!subjectId || subjectId === '—') return;
    getPatientBasic(subjectId)
      .then(data => setPatientData(data))
      .catch(err => console.error('환자 데이터 로드 실패:', err));
  }, [subjectId]);

  // ova_cdss_results DB 로드 (GPU 서버 결과 없을 때 폴백)
  useEffect(() => {
    if (!subjectId || subjectId === '—') return;
    getCdssResult(subjectId)
      .then(data => { if (data?.subject_id) setDbCdssResult(data); })
      .catch(() => {});
  }, [subjectId]);

  // DICOM 이미지 목록
  useEffect(() => {
    if (!caseCode || caseCode === '—') return;
    fetch(`${process.env.NEXT_PUBLIC_SONO_URL}/api/dicom/images?case_code=${caseCode}&subject_id=${subjectId}`)
      .then(res => res.json())
      .then(data => setDicomImages(Array.isArray(data) ? data : []))
      .catch(err => console.error('DICOM 로드 실패:', err));
  }, [caseCode]);

  // 현재 이미지 추론
  const selectedImage = dicomImages[selectedIdx] ?? null;
  useEffect(() => {
    if (!selectedImage || !subjectId || subjectId === '—') return;
    setInferring(true);
    fetch(`${process.env.NEXT_PUBLIC_SONO_URL}/api/inference`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hadm_id: subjectId, image_seq: selectedImage.seq })
    })
      .then(res => res.json())
      .then(data => setAiResult(data))
      .catch(err => console.error('추론 실패:', err))
      .finally(() => setInferring(false));
  }, [selectedImage?.seq, subjectId]);

  // 전체 이미지 worst case 추론
  useEffect(() => {
    if (!subjectId || subjectId === '—' || dicomImages.length === 0) return;
    setFinalInferring(true);
    Promise.all(
      dicomImages.map(img =>
        fetch(`${process.env.NEXT_PUBLIC_SONO_URL}/api/inference`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ hadm_id: subjectId, image_seq: img.seq })
        })
          .then(res => res.json())
          .then(data => ({ ...data, _imgUrl: img.url }))
          .catch(() => null)
      )
    )
      .then(results => {
        const valid = results.filter(r => r !== null);
        if (valid.length === 0) return;
        const worst = valid.reduce((a, b) =>
          (a.malignant_prob ?? 0) > (b.malignant_prob ?? 0) ? a : b
        );
        setFinalResult(worst);

        // 가장 안 좋은(worst) 케이스의 이미지를 자동 저장
        if (worst && worst._imgUrl) {
          localStorage.setItem(`saved_ai_image_${subjectId}`, JSON.stringify({
            url: worst._imgUrl,
            bbox: worst.bbox ?? null
          }));
        }

        fetch(`${process.env.NEXT_PUBLIC_SONO_URL}/api/cdss/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject_id: parseInt(subjectId),
            malignant_prob: worst.malignant_prob,
            detected: worst.detected,
            tumor_size_max: worst.tumor_size_max,
            stage: worst.stage,
            subtype: worst.subtype,
            image_url: worst._imgUrl ?? null,
          })
        }).catch(err => console.error('저장 실패:', err));
      })
      .catch(err => console.error('최종 추론 실패:', err))
      .finally(() => setFinalInferring(false));  // ← Promise.all 체인에 붙어야 함

  }, [subjectId, dicomImages.length]);

  // ── 헬퍼 ──────────────────────────────────────────────────
  const setManual = (key) => (val) => setManualInput((prev) => ({ ...prev, [key]: val }));

  const computedUScore = finalResult ? (() => {
    const count = [
      finalResult.multilocular, finalResult.solid_areas, finalResult.bilateral,
      finalResult.ascites, finalResult.peritoneal_mets
    ].filter(Boolean).length;
    return count === 0 ? 0 : count === 1 ? 1 : 3;
  })() : null;

  // GPU 결과 우선, 없으면 ova_cdss_results DB 값 사용
  const effectiveResult = finalResult ?? (dbCdssResult?.us_malignancy_prob != null ? {
    malignant_prob:  Number(dbCdssResult.us_malignancy_prob),
    detected:        dbCdssResult.us_tumor_detected,
    tumor_size_max:  dbCdssResult.us_tumor_size_cm2 != null ? Number(dbCdssResult.us_tumor_size_cm2) : null,
    stage:           dbCdssResult.us_figo_stage,
    subtype:         dbCdssResult.us_tumor_type,
  } : null);
  const effectiveUScore = computedUScore ?? dbCdssResult?.us_u_score ?? null;

  const riskLevel = (() => {
    const u = effectiveUScore;
    const prob = effectiveResult?.malignant_prob;
    if (u === null || prob == null) return null;
    if (u === 3 || prob > 70) return { label: '고위험', color: '#ef4444', gaugeColor: '#ef4444' };
    if (u === 1 || prob > 30) return { label: '중위험', color: '#f59e0b', gaugeColor: '#f59e0b' };
    if (u === 0 && prob < 30) return { label: '저위험', color: '#22c55e', gaugeColor: '#22c55e' };
    return null;
  })();

  const EmptyFrame = ({ label }) => (
    <div className="flex flex-col items-center gap-2 text-ink-tertiary">
      <ImageIcon size={24} />
      <span className="text-xs">{label}</span>
    </div>
  );

  // ── 렌더 ──────────────────────────────────────────────────
  return (
    <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 64px)' }}>

      {/* ── 사이드바 ── */}
      <aside className="hidden lg:flex w-56 shrink-0 bg-surface-1 border-r border-hairline flex-col overflow-hidden">
        <div className="shrink-0 px-4 py-4 border-b border-hairline">
          <button
            onClick={() => router.push('/screening')}
            className="flex items-center gap-1.5 text-xs text-ink-tertiary hover:text-ink-subtle transition-colors mb-3"
          >
            ← 환자목록
          </button>
          <div className="flex items-center justify-between mb-2">
            <p className="text-s font-semibold text-ink-subtle uppercase tracking-wider">환자 목록</p>
            <button
              onClick={() => { setOnlyWithImages(v => !v); setSidebarPage(1); }}
              title={onlyWithImages ? '전체 환자 보기' : '이미지 있는 환자만 보기'}
              className={`px-2 py-0.5 text-xs rounded-md border font-medium transition-colors ${
                onlyWithImages
                  ? 'bg-primary/10 border-primary/40 text-primary'
                  : 'bg-surface-2 border-hairline text-ink-tertiary hover:border-primary/30'
              }`}
            >
              {dicomSubjectIds === null ? '…' : onlyWithImages ? '이미지만' : '전체'}
            </button>
          </div>
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
            const filtered = sidebarPatients.filter(p => {
              if (onlyWithImages && dicomSubjectIds && !dicomSubjectIds.has(Number(p.subject_id))) return false;
              if (sidebarSearch && !(p.name ?? '').includes(sidebarSearch) && !String(p.subject_id ?? '').includes(sidebarSearch)) return false;
              return true;
            });
            const paged = filtered.slice((sidebarPage - 1) * 10, sidebarPage * 10);
            return (
              <>
                {paged.map((p, idx) => {
                  const isActive = String(p.subject_id) === subjectId;
                  return (
                    <button
                      key={p.subject_id ?? idx}
                      onClick={() => router.push(`/pacs?case_code=${p.subject_id}&subject_id=${p.subject_id}`)}
                      className={`w-full text-left px-4 py-3 transition-colors border-l-2 ${
                        isActive ? 'bg-surface-2 border-primary' : 'border-transparent hover:bg-surface-2'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-semibold truncate pr-2 ${isActive ? 'text-ink' : 'text-ink-muted'}`}>
                          {p.name ?? `환자 ${p.subject_id}`}
                        </span>
                        <span className={`w-2 h-2 rounded-full shrink-0 ${
                          p.riskTier === 'HIGH'     ? 'bg-red-500' :
                          p.riskTier === 'MODERATE' ? 'bg-amber-400' :
                          p.riskTier === 'LOW'      ? 'bg-green-500' : 'bg-ink-tertiary'
                        }`} />
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-ink-tertiary font-mono">{p.id}</span>
                        <span className="text-xs text-hairline-strong">·</span>
                        <span className="text-xs text-ink-tertiary">{p.age != null ? `${p.age}세` : '—'}</span>
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

      {/* ── 메인 컨텐츠 ── */}
      <div className="flex-1 bg-canvas min-w-0" style={{ overflowY: 'auto', height: '100%' }}>
        <div className="p-4 lg:p-8 max-w-[1200px] space-y-4">

          {/* caseCode 없을 때 안내 */}
          {(!caseCode || caseCode === '—') && (
            <div className="bg-surface-1 rounded-xl border border-hairline p-10 flex flex-col items-center justify-center gap-3 min-h-[300px]">
              <ImageIcon size={32} className="text-ink-tertiary" />
              <p className="text-base font-bold text-ink-subtle">환자 목록에서 환자를 선택하면 초음파 분석이 시작됩니다.</p>
            </div>
          )}

          {caseCode && caseCode !== '—' && (
            <>
            {/* 타이틀 헤더 */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-ink" style={{ letterSpacing: '-0.5px' }}>초음파 AI 분석</h1>
                <p className="text-xs text-ink-tertiary mt-0.5">AI 기반 난소 종양 위험도 평가</p>
              </div>
            {/* 우측 버튼 영역 */}
              <div className="flex items-center gap-3 ml-auto shrink-0">
                {/* 소견서 작성 버튼 */}
                <button
                  onClick={() => {
                    const today = new Date().toLocaleDateString('ko-KR');
                    const draft = `[초음파 판독 소견서]

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Patient ID: ${subjectId}          Date: ${today}
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        [1. Clinical Information]
        - Suspected Diagnosis: Ovarian tumor
        - CA-125: ${patientData?.rmi?.ca125_value?.toLocaleString() ?? '—'} U/mL
        - RMI Score: ${patientData?.rmi?.rmi_score?.toLocaleString() ?? '—'}
        - Menopausal Status: ${patientData?.rmi?.menopause_factor === 3 ? 'Postmenopausal' : 'Premenopausal'}


        [2. Ultrasound Findings]
        - Tumor Size: ${finalResult?.tumor_size_max ?? '—'} cm
        - Morphological Features:
          · Multilocular cyst: ${finalResult?.multilocular ? 'Present' : 'Absent'}
          · Solid areas: ${finalResult?.solid_areas ? 'Present' : 'Absent'}
          · Bilateral lesion: ${finalResult?.bilateral ? 'Present' : 'Absent'}
          · Ascites: ${finalResult?.ascites ? 'Present' : 'Absent'}
          · Peritoneal metastasis: ${finalResult?.peritoneal_mets ? 'Present' : 'Absent'}
        - U Score: ${computedUScore ?? '—'}

        [3. AI Analysis Results]
        - Malignancy Probability: ${finalResult?.malignant_prob ?? '—'}%
        - Classification: ${finalResult?.malignant_prob >= 50 ? 'Suspicious for malignancy' : 'Likely benign'}
        - Subtype: ${finalResult?.subtype ?? '—'}
        - FIGO Stage (predicted): ${
          finalResult?.stage === 'early' ? 'Stage I-II' :
          finalResult?.stage === 'late'  ? 'Stage III-IV' :
          'N/A'
        }

        [4. Risk Assessment]
        - AI Risk Level: ${riskLevel?.label ?? '—'}
        - RMI-based Risk: ${patientData?.rmi?.risk_level ?? '—'}

        [5. Clinical Findings]
        · Wall irregularity: ${manualInput.wall_irregularity ? 'Present' : 'Absent'}
        · Papillary projection: ${manualInput.papillary_projection ? 'Present' : 'Absent'}
        · Internal vascularity (Doppler): ${manualInput.vascularity ? 'Present' : 'Absent'}


        [6. Conclusion & Recommendations]
        ${riskLevel?.label === '고위험'
          ? `- Immediate referral and imaging workup (CT/MRI) strongly recommended
        - Gynecologic oncology consultation required`
        : riskLevel?.label === '중위험'
        ? `- Additional imaging workup (CT/MRI) recommended
        - Follow-up within 2-4 weeks`
        : `- Routine follow-up recommended
        - Repeat examination in 3-6 months`}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        Radiologist: ___________________  (Signature)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
                    setReportText(draft);
                    setShowReport(true);
                  }}
                  className="px-6 py-3 rounded-xl border-2 border-primary bg-white text-base font-bold text-primary hover:bg-primary/5 transition-colors flex items-center gap-2"
                >
                  📋 소견서 작성
                </button>
                {/* CDSS로 이동 버튼 */}
                <button
                  onClick={() => router.push(`/cdss?subject_id=${subjectId}`)}
                  className="px-6 py-3 rounded-xl bg-primary text-white text-base font-bold hover:bg-primary-hover transition-colors flex items-center gap-2"
                >
                  CDSS 분석결과 보기
                </button>
              </div>
            </div>

            {/* 초음파 이미지 없음 안내 배너 */}
            {dicomImages.length === 0 && (
              <div className="flex items-center gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm">
                <span className="text-red-500 text-base shrink-0">⚠</span>
                <div>
                  <span className="font-semibold text-red-700">초음파 촬영이 필요합니다</span>
                  <span className="text-red-500 ml-2">— 이 환자의 DICOM 이미지가 등록되어 있지 않습니다.</span>
                </div>
              </div>
            )}

            {/* ▼ 여기서부터 2단 레이아웃으로 */}
            <div className="grid grid-cols-[240px_1fr] gap-2 items-start">

              {/* 왼쪽: 기본정보 + RMI */}
              <div className="flex flex-col gap-4">
                {/* 기본정보 카드 */}
                <div className="bg-surface-1 rounded-xl border border-hairline p-4">
                  <p className="text-base font-bold text-ink mb-4">기본정보</p>
                  <div className="space-y-3 text-xs">
                    <InfoRow label="이름"        value={patientData?.patient_name || '—'} />
                    <InfoRow label="PT ID"       value={patientData?.pt_id || '—'} mono />
                    <InfoRow label="초음파등록번호" value={patientData?.patient_reg_no || caseCode} />
                    <InfoRow label="생년월일"    value={patientData?.birth_ym || '—'} />
                    <InfoRow label="나이"        value={patientData?.diag_att_age ? `${patientData.diag_att_age}세` : '—'} />
                    <InfoRow label="성별"        value={patientData?.gender || '—'} />
                  </div>
                </div>

                {/* RMI 카드 */}
                <div className="bg-surface-1 rounded-xl border border-hairline p-4">
                  <p className="text-base font-bold text-ink mb-4">RMI 계산값</p>
                  <div className="space-y-3 text-xs">
                    <InfoRow label="U 스코어"  value={patientData?.rmi?.us_score ?? '—'} />
                    <InfoRow label="M 스코어"  value={patientData?.rmi?.menopause_factor ?? '—'} />
                    <InfoRow label="CA-125"    value={patientData?.rmi?.ca125_value ? patientData.rmi.ca125_value.toLocaleString() : '—'} unit="U/mL" />
                    <InfoRow label="RMI 점수"  value={patientData?.rmi?.rmi_score ? patientData.rmi.rmi_score.toLocaleString() : '—'} highlight={patientData?.rmi?.rmi_score >= 200} />
                  </div>
                </div>

                {/* ── 5. AI 위험도 평가 + 가이드 ── */}
                <div className="flex flex-col gap-3">
                  <div className={`rounded-xl border p-5 flex flex-col gap-2
                    ${riskLevel?.label === '고위험' ? 'bg-red-500/5 border-red-300' :
                      riskLevel?.label === '중위험' ? 'bg-amber-500/5 border-amber-300' :
                      riskLevel?.label === '저위험' ? 'bg-green-500/5 border-green-300' :
                      'bg-surface-1 border-hairline'}`}>
                    <p className="text-base font-bold text-ink mb-1">AI 위험도 평가</p>
                    <div className="flex flex-col items-center">
                      <GaugeChart value={effectiveResult?.malignant_prob != null ? Number(effectiveResult.malignant_prob.toFixed(1)) : null} color={riskLevel?.gaugeColor ?? '#d1d5db'} />
                      <div className="flex-1 text-center">
                        <p className="text-3xl items-center font-extrabold" style={{ color: riskLevel?.color ?? '#9ca3af' }}>
                          {riskLevel?.label ?? '—'}
                        </p>
                        <p className="text-sm items-center text-ink-subtle mt-1">
                          악성 가능성 <span className="font-bold">{effectiveResult?.malignant_prob != null ? `${Number(effectiveResult.malignant_prob).toFixed(1)}%` : '—'}</span>
                        </p>
                       </div>
                    </div>
                  </div>
                  <div className="bg-surface-1 rounded-xl border border-hairline p-5">
                    <p className="text-sm font-semibold text-ink mb-3">위험도 가이드</p>
                    <div className="space-y-2 text-xs text-ink-subtle">
                      <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" /><span>고위험 — U=3 OR 악성확률 &gt;70%</span></div>
                      <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0" /><span>중위험 — U=1 OR 악성확률 &gt;30%</span></div>
                      <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-green-500 shrink-0" /><span>저위험 — U=0 AND 악성확률 &lt;30%</span></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 오른쪽: 분석 시각화 + 나머지 전부 */}
              <div className="space-y-4">

              {/* ── 3. 분석 시각화 ── */}
              <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
                <div className="px-5 py-3 bg-primary/10 border-b border-hairline flex items-center gap-2">
                  <div className="w-1 h-4 rounded-full bg-primary" />
                  <span className="text-lg font-bold text-primary">분석 시각화</span>
                </div>
                <div className="p-5 space-y-4">

                  {/* 뷰어 2분할 */}
                  <div className="grid grid-cols-2 gap-4">
                    <ImageFrame
                      title="원본 초음파 이미지"
                      subtitle={selectedImage ? `${selectedImage.label}.dcm` : undefined}
                      modalChildren={
                        selectedImage?.url
                          ? <img src={selectedImage.url} alt="원본" className="w-full h-full object-contain" />
                          : <EmptyFrame label="등록된 초음파 이미지가 없습니다" />
                      }
                    >
                      {selectedImage?.url
                        ? <img src={selectedImage.url} alt="원본" className="max-w-full max-h-[260px] object-contain" />
                        : <EmptyFrame label="등록된 초음파 이미지가 없습니다" />}
                    </ImageFrame>
                    <ImageFrame
                      title="AI 분석"
                      subtitle={inferring ? "분석 중..." : "Bounding Box"}
                      modalChildren={
                        selectedImage?.url
                          ? <BboxOverlay imageUrl={selectedImage.url} bbox={aiResult?.bbox ?? null} isModal={true} />
                          : <EmptyFrame label="분석 대기 중" />
                      }
                    >
                      {inferring
                        ? <div className="flex flex-col items-center gap-3 text-ink-tertiary">
                            <div className="w-8 h-8 border-2 border-surface-3 border-t-primary rounded-full animate-spin" />
                            <span className="text-xs">AI 분석 중...</span>
                          </div>
                        : selectedImage?.url
                          ? <BboxOverlay imageUrl={selectedImage.url} bbox={aiResult?.bbox ?? null} />
                          : <EmptyFrame label="분석 대기 중" />}
                    </ImageFrame>
                  </div>

                  {/* 썸네일 */}
                  <div>
                    <p className="text-base text-ink-tertiary mb-2">동일 환자 초음파 이미지 목록 · {dicomImages.length}장</p>
                    <div className="flex gap-2 overflow-x-auto pb-1">
                      {dicomImages.map((img, idx) => (
                        <button key={img.id} onClick={() => setSelectedIdx(idx)}
                          className={`shrink-0 w-[72px] h-[60px] rounded-lg border-2 overflow-hidden flex flex-col items-center justify-center transition-all
                            ${idx === selectedIdx ? 'border-primary bg-primary/5' : 'border-hairline bg-surface-2 hover:border-primary/40'}`}>
                          {img.url
                            ? <img src={img.url} alt={img.label} className="w-full h-full object-cover" />
                            : <div className="flex flex-col items-center gap-0.5">
                                <ImageIcon size={12} className={idx === selectedIdx ? 'text-primary' : 'text-ink-tertiary'} />
                                <span className={`text-xs font-mono ${idx === selectedIdx ? 'text-primary' : 'text-ink-tertiary'}`}>_{img.seq}</span>
                              </div>}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 현재 이미지 AI 결과 카드 */}
                  <div className={`grid grid-cols-5 gap-3 transition-opacity ${inferring ? 'opacity-30' : 'opacity-100'}`}>
                    <AiCard label="종양 탐지" value={aiResult?.tumor_size_w ? '발견됨' : '—'} />
                    <AiCard label="양성/악성 예측"
                      value={aiResult?.malignant_prob != null ? (aiResult.malignant_prob >= 50 ? '악성' : '양성') : '—'}
                      sub={aiResult?.malignant_prob != null
                        ? `신뢰도 ${aiResult.malignant_prob >= 50
                            ? aiResult.malignant_prob
                            : Math.round((100 - aiResult.malignant_prob) * 10) / 10}%`
                        : undefined}
                      highlight={aiResult?.malignant_prob >= 50} />
                    <AiCard label="종양 크기"
                      value={aiResult?.tumor_size_max ? `${aiResult.tumor_size_max} cm²` : '—'} />
                    <AiCard label="Subtype"
                      value={aiResult?.subtype ?? '—'}
                      sub={aiResult?.subtype_confidence != null ? `신뢰도 ${aiResult.subtype_confidence}%` : undefined} />
                    <AiCard label="(예상) FIGO Stage"
                      value={
                        aiResult?.stage === 'early' ? 'I–II' :
                        aiResult?.stage === 'late'  ? 'III–IV' :
                        aiResult?.stage === null    ? '해당없음' : '—'
                      }
                      sub={aiResult?.stage_confidence != null ? `신뢰도 ${aiResult.stage_confidence}%` : undefined} />
                  </div>

                  {/* 상세 판독 소견 버튼 */}
                  <button
                    onClick={() => setShowDetail(!showDetail)}
                    className="w-full flex items-center justify-center gap-1 py-2 font-bold rounded-lg border border-primary/30 text-sm text-primary hover:bg-primary/5 transition-colors">
                    상세 판독 소견 {showDetail ? '접기' : '보기'} <ChevronRight size={20} className={`transition-transform ${showDetail ? 'rotate-90' : ''}`} />
                  </button>

                  {/* 최종 종합 판정 */}
                  <div className={`mt-4 p-4 rounded-xl border-2 transition-opacity ${
                    finalInferring ? 'opacity-30' : 'opacity-100'
                  } ${
                    effectiveResult?.malignant_prob >= 50 ? 'border-red-300 bg-red-50/50' : 'border-green-300 bg-green-50/50'
                  }`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-1 h-5 rounded-full bg-primary" />
                      <span className="text-xl font-bold text-ink">최종 종합 판정</span>
                      <span className="text-xs text-ink-tertiary">
                        {finalResult ? '(전체 이미지 중 최고 위험도 기준)' : '(DB 저장 결과)'}
                      </span>
                      {finalInferring && (
                        <div className="ml-auto w-4 h-4 border-2 border-surface-3 border-t-primary rounded-full animate-spin" />
                      )}
                    </div>
                    <div className="grid grid-cols-5 gap-3">
                      <AiCard
                        label="최종 판독"
                        value={effectiveResult?.malignant_prob != null ? (effectiveResult.malignant_prob >= 50 ? '악성' : '양성') : '—'}
                        sub={effectiveResult?.malignant_prob != null ? `악성 가능성 ${effectiveResult.malignant_prob.toFixed(1)}%` : undefined}
                        highlight={effectiveResult?.malignant_prob >= 50} />
                      <AiCard
                        label="종양 크기"
                        value={effectiveResult?.tumor_size_max != null ? `${effectiveResult.tumor_size_max} cm²` : '—'} />
                      <AiCard
                        label="Subtype"
                        value={effectiveResult?.subtype ?? '—'}
                        sub={effectiveResult?.subtype_confidence != null ? `신뢰도 ${effectiveResult.subtype_confidence}%` : undefined} />
                      <AiCard
                        label="FIGO-Stage"
                        value={
                          effectiveResult?.stage === 'early'  ? 'I–II' :
                          effectiveResult?.stage === 'late'   ? 'III–IV' :
                          effectiveResult?.stage === 'benign' ? '양성' :
                          effectiveResult?.stage === null     ? '해당없음' : '—'
                        }
                        sub={effectiveResult?.stage_confidence != null ? `신뢰도 ${effectiveResult.stage_confidence}%` : undefined} />
                      <AiCard
                        label="U-score"
                        value={effectiveUScore != null ? `${effectiveUScore}점` : '—'}
                        sub={
                          effectiveUScore === 0 ? '특이소견 없음' :
                          effectiveUScore === 1 ? '저위험' :
                          effectiveUScore === 3 ? '고위험' : undefined
                        }
                        highlight={effectiveUScore === 3} />
                    </div>
                  </div>
                </div>
              </div>

              {/* ── 4. AI 판독 소견 (토글) ── */}
              {showDetail && (
                <div className="bg-surface-1 rounded-xl border border-hairline overflow-hidden">
                  <div className="px-5 py-3 bg-primary/10 border-b border-hairline flex items-center gap-2">
                    <div className="w-1 h-4 rounded-full bg-primary" />
                    <span className="text-lg font-bold text-primary">AI 판독 소견</span>
                  </div>
                  <div className="p-5 space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <p className="text-s font-bold text-ink">U 스코어</p>
                        <p className="text-xs text-ink-tertiary">0개=0점, 1개=1점, 2개↑=3점</p>
                        <div className="flex flex-wrap gap-1.5">
                          {[
                            { label: '다방성 낭종', value: effectiveResult?.multilocular },
                            { label: '고형 병변',   value: effectiveResult?.solid_areas },
                            { label: '양측성 병변', value: effectiveResult?.bilateral },
                            { label: '복수',        value: effectiveResult?.ascites },
                            { label: '복막 전이',   value: effectiveResult?.peritoneal_mets },
                          ].map((item, i) => <UBadge key={i} label={item.label} value={item.value} />)}
                        </div>
                        <div className="flex items-center justify-between pt-1 border-t border-hairline text-sm">
                          <span className="text-ink-subtle font-semibold">최종 U score</span>
                          <span className={`text-xl font-bold ${highlight ? 'text-red-500' : 'text-ink'}`}>
                            {effectiveUScore ?? '—'} 점
                          </span>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <p className="text-s font-bold text-ink">형태 특성</p>
                        <div className="flex flex-wrap gap-1.5">
                          {[
                            { label: '다방성 낭종', value: effectiveResult?.multilocular },
                            { label: '고형 부위',   value: effectiveResult?.solid_areas },
                          ].map((item, i) => <UBadge key={i} label={item.label} value={item.value} />)}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <p className="text-s font-bold text-ink">관련 소견</p>
                        <div className="flex flex-wrap gap-1.5">
                          {[
                            { label: '양측성 병변', value: effectiveResult?.bilateral },
                            { label: '복수',        value: effectiveResult?.ascites },
                            { label: '복막 전이',   value: effectiveResult?.peritoneal_mets },
                          ].map((item, i) => <UBadge key={i} label={item.label} value={item.value} />)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 pt-3 border-t border-hairline">
                      <span className="text-s font-bold text-ink shrink-0">임상의 직접 입력</span>
                      <CheckItem label="벽 불규칙성" value={manualInput.wall_irregularity} onChange={setManual('wall_irregularity')} />
                      <CheckItem label="유두상 돌기" value={manualInput.papillary_projection} onChange={setManual('papillary_projection')} />
                      <CheckItem label="내부 혈류 신호 (Doppler)" value={manualInput.vascularity} onChange={setManual('vascularity')} />
                    </div>
                  </div>
                </div>
              )}



              {/* ── 소견서 모달 ── */}
              {showReport && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                  <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[90vh]">
                    <div className="px-6 py-4 border-b border-hairline flex items-center justify-between shrink-0">
                      <h2 className="text-lg font-bold text-ink">초음파 판독 소견서</h2>
                      <button onClick={() => setShowReport(false)} className="p-1.5 rounded-lg hover:bg-surface-2 text-ink-tertiary hover:text-ink transition-colors">
                        <X size={16} />
                      </button>
                    </div>
                    <div className="flex-1 overflow-auto p-6">
                      <textarea
                        value={reportText}
                        onChange={e => setReportText(e.target.value)}
                        className="w-full h-[500px] font-mono text-sm text-ink bg-surface-2 border border-hairline rounded-xl p-4 outline-none focus:border-primary resize-none leading-relaxed"
                      />
                    </div>
                    <div className="px-6 py-4 border-t border-hairline flex justify-end gap-3 shrink-0">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(reportText);
                          alert('클립보드에 복사됐어요!');
                        }}
                        className="px-4 py-2 text-sm border border-hairline rounded-xl hover:bg-surface-2 transition-colors text-ink-subtle"
                      >
                        복사
                      </button>
                      <button
                        onClick={() => {
                          const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `소견서_${subjectId}_${new Date().toLocaleDateString('ko-KR').replace(/\./g, '').replace(/ /g, '')}.txt`;
                          a.click();
                        }}
                        className="px-4 py-2 text-sm border border-hairline rounded-xl hover:bg-surface-2 transition-colors text-ink-subtle"
                      >
                        다운로드
                      </button>
                      <button
                        onClick={() => setShowReport(false)}
                        className="px-4 py-2 text-sm font-semibold bg-primary hover:bg-primary-hover text-white rounded-xl transition-colors"
                      >
                        닫기
                      </button>
                    </div>
                  </div>
                </div>
              )}
              </div> {/* 오른쪽 끝 */}
            </div> {/* grid 끝 */}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
