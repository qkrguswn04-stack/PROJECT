'use client';
import { Suspense, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { CheckCircle2, Loader2, Send, ArrowLeft, Search, Printer } from 'lucide-react';
import { useAuth } from '@/lib/AuthContext';
import { getPatients, getPatientDetail, runCdssPredict, saveReferral, cancelReferral, getCdssResult } from '@/lib/api';

// ── 상수 ─────────────────────────────────────────────────────────────────────

const RISK_LABEL = { HIGH: '고위험', MODERATE: '중위험', LOW: '저위험' };

const ALL_LABS = [
  { key: 'CA-125',        label: 'CA-125',  unit: 'U/mL',  ref: '< 35'    },
  { key: 'Glucose',       label: 'Glucose', unit: 'mg/dL', ref: '70–100'  },
  { key: 'Triglycerides', label: 'TG',      unit: 'mg/dL', ref: '< 150'   },
  { key: 'Albumin',       label: 'Albumin', unit: 'g/dL',  ref: '3.5–5.0' },
  { key: 'AST',           label: 'AST',     unit: 'U/L',   ref: '< 40'    },
  { key: 'ALT',           label: 'ALT',     unit: 'U/L',   ref: '< 56'    },
  { key: 'WBC',           label: 'WBC',     unit: 'K/μL',  ref: '4–10'    },
  { key: 'Hemoglobin',    label: 'Hb',      unit: 'g/dL',  ref: '12–16'   },
  { key: 'HDL',           label: 'HDL',     unit: 'mg/dL', ref: '> 40'    },
  { key: 'Platelet',      label: 'Plt',     unit: 'K/μL',  ref: '150–400' },
  { key: 'PT-INR',        label: 'PT-INR',  unit: '',      ref: '0.8–1.2' },
  { key: 'BUN',           label: 'BUN',     unit: 'mg/dL', ref: '7–20'    },
];

const FIGO_LABEL = { early: 'I–II기 (조기)', late: 'III–IV기 (진행)', benign: '양성' };

const DEST_OPTIONS = [
  '서울대학교병원 산부인과 부인종양클리닉',
  '삼성서울병원 부인암센터',
  '서울아산병원 부인종양과',
  '세브란스병원 부인암센터',
  '국립암센터 부인암센터',
];

function buildUsSummary(cdssResult, uScore, prediction, rmi) {
  if (!cdssResult) return null;
  const detected   = cdssResult.us_tumor_detected;
  const size       = cdssResult.us_tumor_size_cm2;
  const prob       = cdssResult.us_malignancy_prob;
  const aiTier     = prediction?.risk_tier;
  const rmiScore   = rmi?.rmi_score;
  const rmiTier    = rmi?.risk_level;

  const tumorPart = detected === true
    ? `종양 탐지됨${size != null ? ` (크기 ${size} cm²)` : ''}`
    : detected === false
    ? '종양 미탐지'
    : '초음파 AI 분석 수행';
  const uPart   = uScore != null ? `, U스코어 ${uScore}점` : '';
  const probPart = prob != null
    ? `, 악성 확률 ${Number(prob).toFixed(1)}%${aiTier ? ` (${RISK_LABEL[aiTier]})` : ''}`
    : '';
  const s1 = `초음파 AI 분석상 ${tumorPart}${uPart}${probPart} 소견입니다.`;

  const tier = aiTier ?? rmiTier;
  const conclusion = tier === 'HIGH'     ? '3차 의료기관 전원을 권고합니다.'
                   : tier === 'MODERATE' ? '추가 정밀검사를 권고합니다.'
                   : tier === 'LOW'      ? '정기 추적관찰을 권고합니다.'
                   : null;
  const s2 = rmiScore != null && conclusion
    ? `RMI ${rmiScore.toLocaleString()}점 (${rmiTier ? RISK_LABEL[rmiTier] : '—'}) 기반으로 ${conclusion}`
    : null;

  return [s1, s2].filter(Boolean).join(' ');
}

function autoReason(patient, prediction) {
  const tier = prediction?.risk_tier;
  const rmi  = patient?.rmi;
  const pct  = prediction?.probability_pct;
  return [
    `상기 환자는 CDSS AI 분석 결과 ${tier ? RISK_LABEL[tier] : '고위험'} 소견으로 판정되었습니다.`,
    ``,
    `RMI 점수 ${rmi?.rmi_score != null ? rmi.rmi_score.toLocaleString() : '—'}점 (위험도: ${rmi?.risk_level ? RISK_LABEL[rmi.risk_level] : '—'}), XGBoost 악성 예측 확률 ${pct != null ? pct.toFixed(1) + '%' : '—'}으로 전문적인 정밀 진단 및 치료를 위해 의뢰드립니다.`,
    ``,
    `부인종양 전문의의 협진 및 조기 수술적 치료 여부 결정을 요청드립니다.`,
  ].join('\n');
}

// ── 서브 컴포넌트 ─────────────────────────────────────────────────────────────

function SecHead({ n, title }) {
  return (
    <div className="flex items-center gap-2 px-[12px] py-[5px] bg-[#f3f4f6] border-b border-[#d1d5db]">
      <span className="w-[18px] h-[18px] rounded-full bg-[#5e6ad2] text-white text-[9px] font-bold flex items-center justify-center shrink-0 leading-none">
        {n}
      </span>
      <span className="text-[10pt] font-bold text-[#374151]">{title}</span>
    </div>
  );
}

function RField({ label, value, highlight, className = '' }) {
  return (
    <div className={className}>
      <div className="text-[9px] text-[#6b7280] uppercase tracking-wide leading-none mb-[3px]">{label}</div>
      <div className={`text-[11pt] font-semibold leading-snug ${highlight ? 'text-red-600' : 'text-[#111]'}`}>
        {value ?? '—'}
      </div>
    </div>
  );
}

// ── 출력 HTML 빌더 ────────────────────────────────────────────────────────────

function buildPrintHtml({ form, patient, prediction, cdssResult, allLabs, uScore, rmi, genderLabel, menopauseLabel, user }) {
  const findLab = (key) => allLabs.find(r => r.display_name === key || r.test_name === key);
  const dateStr = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  const name = patient?.patient_name || '—';

  const labRows = ALL_LABS.map(({ key, label, unit, ref }) => {
    const lab = findLab(key);
    const cls = lab?.status === 'high' ? 'color:#dc2626;font-weight:600' : lab?.status === 'low' ? 'color:#2563eb;font-weight:600' : '';
    const arrow = lab?.status === 'high' ? ' ↑' : lab?.status === 'low' ? ' ↓' : '';
    return `<tr><td>${label}</td><td style="${cls}">${lab?.value != null ? lab.value + ' ' + unit : '—'}${arrow}</td><td style="color:#6b7280;font-size:9pt">${ref}</td></tr>`;
  }).join('');

  return `<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"/>
<title>난소종양 전원 의뢰서 — ${name}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Apple SD Gothic Neo','맑은 고딕',sans-serif;font-size:11pt;color:#111;padding:16mm;line-height:1.6}
h1{font-size:19pt;font-weight:800;text-align:center;border-bottom:2.5px solid #111;padding-bottom:8px;margin-bottom:4px;letter-spacing:-.5px}
.sub{text-align:center;font-size:9.5pt;color:#6b7280;margin-bottom:16px}
.sec{margin-bottom:10px;border:1px solid #d1d5db;border-radius:4px;overflow:hidden}
.sh{background:#f3f4f6;padding:5px 12px;font-size:10pt;font-weight:700;color:#374151;border-bottom:1px solid #d1d5db;display:flex;align-items:center;gap:8px}
.sn{width:18px;height:18px;border-radius:50%;background:#5e6ad2;color:#fff;font-size:9pt;font-weight:700;display:inline-flex;align-items:center;justify-content:center}
.sb{padding:8px 12px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:6px 16px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px 16px}
.fl{font-size:9pt;color:#6b7280;line-height:1}
.fv{font-size:11pt;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:10pt}
th{background:#f9fafb;padding:3px 8px;text-align:left;font-weight:600;border:1px solid #e5e7eb}
td{padding:3px 8px;border:1px solid #e5e7eb}
.rbox{white-space:pre-wrap;min-height:70px;font-size:11pt}
.sl{border-bottom:1px solid #111;padding-bottom:4px;min-height:28px;margin-top:4px}
.ub{display:inline-block;padding:1px 10px;border-radius:12px;font-size:10pt;font-weight:600}
.u-일반{background:#eef0ff;color:#5e6ad2}.u-긴급{background:#fffbe6;color:#d97706}.u-응급{background:#fff0f0;color:#dc2626}
@media print{body{padding:12mm}}
</style></head><body>
<h1>난소종양 전원 의뢰서</h1>
<p class="sub">Ovarian Tumor Referral Letter</p>
<div class="sec"><div class="sh"><span class="sn">1</span>환자 기본정보</div><div class="sb">
<div class="g4">
<div><div class="fl">환자명</div><div class="fv">${name}</div></div>
<div><div class="fl">나이</div><div class="fv">${patient?.diag_att_age ?? '—'}세</div></div>
<div><div class="fl">성별</div><div class="fv">${genderLabel}</div></div>
<div><div class="fl">등록번호</div><div class="fv">${patient?.hadm_id || '—'}</div></div>
<div><div class="fl">생년월일</div><div class="fv">${patient?.birth_ym || '—'}</div></div>
<div><div class="fl">환자 ID</div><div class="fv">${patient?.subject_id || '—'}</div></div>
<div><div class="fl">폐경 여부</div><div class="fv">${menopauseLabel}</div></div>
</div></div></div>
<div class="sec"><div class="sh"><span class="sn">2</span>진단명 (의심 상병명)</div>
<div class="sb"><div class="fv">${form.diagnosis.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</div></div></div>
<div class="sec"><div class="sh"><span class="sn">3</span>임상 소견</div><div class="sb">
<div class="g2">
<div><div class="fl">주요 증상</div><div class="fv">${patient?.symptoms || '기록 없음'}</div></div>
<div><div class="fl">CA-125</div><div class="fv" style="${rmi?.ca125_value > 35 ? 'color:#dc2626' : ''}">${rmi?.ca125_value != null ? rmi.ca125_value.toLocaleString() + ' U/mL' : '—'}</div></div>
</div></div></div>
<div class="sec"><div class="sh"><span class="sn">4</span>검사 결과 (혈액검사)</div><div class="sb">
<table><tr><th>항목</th><th>결과</th><th>참고범위</th></tr>${labRows}</table>
</div></div>
<div class="sec"><div class="sh"><span class="sn">5</span>영상 소견 (초음파 AI)</div><div class="sb">
<div class="g4">
<div><div class="fl">종양 탐지</div><div class="fv">${cdssResult?.us_tumor_detected != null ? (cdssResult.us_tumor_detected ? '탐지됨' : '없음') : '—'}</div></div>
<div><div class="fl">종양 크기</div><div class="fv">${cdssResult?.us_tumor_size_cm2 != null ? cdssResult.us_tumor_size_cm2 + ' cm²' : '—'}</div></div>
<div><div class="fl">U스코어</div><div class="fv">${uScore != null ? uScore + '점' : '—'}</div></div>
<div><div class="fl">FIGO 병기</div><div class="fv">${cdssResult?.us_figo_stage ? (FIGO_LABEL[cdssResult.us_figo_stage] ?? cdssResult.us_figo_stage) : '—'}</div></div>
<div><div class="fl">종양 유형</div><div class="fv">${cdssResult?.us_tumor_type ?? '—'}</div></div>
<div><div class="fl">초음파 악성 확률</div><div class="fv">${cdssResult?.us_malignancy_prob != null ? Number(cdssResult.us_malignancy_prob).toFixed(1) + '%' : '—'}</div></div>
</div></div></div>
<div class="sec"><div class="sh"><span class="sn">6</span>AI 분석 결과</div><div class="sb">
<div class="g4">
<div><div class="fl">RMI 점수</div><div class="fv">${rmi?.rmi_score != null ? rmi.rmi_score.toLocaleString() : '—'}</div></div>
<div><div class="fl">RMI 위험도</div><div class="fv">${rmi?.risk_level ? RISK_LABEL[rmi.risk_level] : '—'}</div></div>
<div><div class="fl">XGBoost 악성 확률</div><div class="fv" style="${prediction?.probability_pct >= 60 ? 'color:#dc2626' : ''}">${prediction?.probability_pct != null ? prediction.probability_pct.toFixed(1) + '%' : '—'}</div></div>
<div><div class="fl">위험 등급</div><div class="fv">${prediction?.risk_tier ? RISK_LABEL[prediction.risk_tier] : '—'}</div></div>
</div></div></div>
<div class="sec"><div class="sh"><span class="sn">7</span>전원 사유 및 요청사항</div>
<div class="sb"><div class="rbox">${form.reason.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div></div></div>
<div class="sec"><div class="sh"><span class="sn">8</span>의뢰 기관 / 의뢰의 서명</div><div class="sb">
<div class="g2">
<div><div class="fl">의뢰 기관</div><div class="fv">${form.destination || '—'}</div></div>
<div><div class="fl">긴급도</div><div><span class="ub u-${form.urgency}">${form.urgency}</span></div></div>
</div>
<div class="g3" style="margin-top:12px">
<div><div class="fl">의뢰의</div><div class="sl">${user?.name || user?.employee_id || '—'}</div></div>
<div><div class="fl">사번</div><div class="sl">${user?.employee_id || '—'}</div></div>
<div><div class="fl">작성일</div><div class="sl">${dateStr}</div></div>
</div></div></div>
<script>window.onload=function(){window.print();};</script>
</body></html>`;
}

// ── 메인 ─────────────────────────────────────────────────────────────────────

function ReportsContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const { user, role } = useAuth();
  const canWrite = role === 'doctor';

  const [allPatients,   setAllPatients]   = useState([]);
  const [patientSearch, setPatientSearch] = useState('');
  const [sid,           setSid]           = useState(searchParams.get('subject_id') || '');

  const [patient,     setPatient]     = useState(null);
  const [prediction,  setPrediction]  = useState(null);
  const [cdssResult,  setCdssResult]  = useState(null);
  const [dataLoading, setDataLoading] = useState(false);

  const [form, setForm] = useState({
    urgency:     '일반',
    destination: '',
    diagnosis:   '난소 종양 의심 (Ovarian tumor, suspected)',
    reason:      '',
  });
  const [submitted,     setSubmitted]     = useState(false);
  const [submitting,    setSubmitting]    = useState(false);
  const [cancelling,    setCancelling]    = useState(false);
  const reasonRef = useRef(null);
  useEffect(() => {
    const el = reasonRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  }, [form.reason]);
  const [submittedForm, setSubmittedForm] = useState(null);

  useEffect(() => {
    getPatients(1, 500).then(({ patients }) => setAllPatients(patients)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sid) { setPatient(null); setPrediction(null); setCdssResult(null); return; }
    setDataLoading(true);
    setSubmitted(false);
    Promise.all([
      getPatientDetail(sid),
      runCdssPredict(sid).catch(() => null),
      getCdssResult(sid).catch(() => null),
    ])
      .then(([detail, pred, cdss]) => {
        setPatient(detail);
        setPrediction(pred);
        if (cdss?.subject_id) setCdssResult(cdss);
        if (detail.status === '의뢰완료') setSubmitted(true);
        const uScoreLocal = cdss?.us_u_score ?? detail?.rmi?.us_score ?? null;
        const usSummary   = buildUsSummary(cdss?.subject_id ? cdss : null, uScoreLocal, pred, detail?.rmi);
        const baseReason  = autoReason(detail, pred);
        setForm(f => ({ ...f, reason: usSummary ? `${baseReason}\n\n${usSummary}` : baseReason }));
      })
      .catch(() => {})
      .finally(() => setDataLoading(false));
  }, [sid]);

  const filteredPatients = useMemo(() =>
    allPatients.filter(p =>
      !patientSearch || p.name.includes(patientSearch) || p.id.includes(patientSearch)
    ), [allPatients, patientSearch]);

  const handleSelectPatient = (newSid) => {
    setSid(newSid);
    router.replace(newSid ? `/reports?subject_id=${newSid}` : '/reports', { scroll: false });
  };

  const handleSubmit = useCallback(async () => {
    if (!sid || !user) return;
    setSubmitting(true);
    try {
      await saveReferral(sid, {
        doctorId:    user.employee_id,
        urgency:     form.urgency,
        destination: form.destination.trim() || null,
        content:     [form.diagnosis, form.reason].filter(Boolean).join('\n\n'),
        hadmId:      patient?.hadm_id || null,
      });
      setSubmittedForm({ ...form });
      setSubmitted(true);
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  }, [sid, user, form, patient]);

  const allLabs        = patient?.labResultsByDate?.[0]?.results || [];
  const findLab        = (key) => allLabs.find(r => r.display_name === key || r.test_name === key);
  const rmi            = patient?.rmi;
  const uScore         = cdssResult?.us_u_score ?? rmi?.us_score ?? null;
  const genderLabel    = patient?.gender === 'F' ? '여성' : patient?.gender === 'M' ? '남성' : '—';
  const menopauseLabel = rmi?.menopause_factor === 3 ? '폐경 후' : rmi?.menopause_factor === 1 ? '폐경 전' : '—';

  const handleCancelReferral = useCallback(async () => {
    if (!sid || !window.confirm('의뢰를 취소하시겠습니까?\n상태가 "검토완료"로 되돌아갑니다.')) return;
    setCancelling(true);
    try {
      await cancelReferral(sid);
      setSubmitted(false);
      setSubmittedForm(null);
    } catch (err) {
      alert(err.message);
    } finally {
      setCancelling(false);
    }
  }, [sid]);

  const handlePrint = useCallback(() => {
    const f = submittedForm || form;
    const html = buildPrintHtml({ form: f, patient, prediction, cdssResult, allLabs, uScore, rmi, genderLabel, menopauseLabel, user });
    const w = window.open('', '_blank', 'width=920,height=780');
    if (w) { w.document.write(html); w.document.close(); }
  }, [submittedForm, form, patient, prediction, cdssResult, allLabs, uScore, rmi, genderLabel, menopauseLabel, user]);

  // urgency 배지 스타일 (출력본 동일 색상)
  const urgencyBadge = {
    '일반': 'bg-[#eef0ff] text-[#5e6ad2] border-[#c7d2fe]',
    '긴급': 'bg-[#fffbe6] text-[#d97706] border-[#fde68a]',
    '응급': 'bg-[#fff0f0] text-[#dc2626] border-[#fecaca]',
  };

  // ── 렌더 ─────────────────────────────────────────────────────────────────────

  return (
    <div className="flex gap-5 p-6 max-w-[1200px]" style={{ fontFamily: "'Apple SD Gothic Neo', '맑은 고딕', sans-serif" }}>

      {/* ── 왼쪽 컨트롤 패널 ── */}
      <div className="w-[220px] shrink-0 space-y-3">

        {sid && (
          <button
            onClick={() => router.push(`/cdss?subject_id=${sid}`)}
            className="flex items-center gap-1.5 text-[13px] text-[#6b7280] hover:text-[#374151] transition-colors"
          >
            <ArrowLeft size={13} /> CDSS로 돌아가기
          </button>
        )}

        {/* 환자 선택 */}
        <div className="bg-white border border-[#d1d5db] rounded-lg p-3 shadow-sm">
          <p className="text-[11px] font-bold text-[#6b7280] uppercase tracking-wider mb-2">환자 선택</p>
          <div className="relative mb-2">
            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#9ca3af] pointer-events-none" />
            <input
              type="text"
              placeholder="이름 · ID 검색"
              value={patientSearch}
              onChange={e => setPatientSearch(e.target.value)}
              className="w-full pl-6 pr-2 py-1.5 text-[13px] border border-[#d1d5db] rounded outline-none focus:border-[#5e6ad2] bg-[#f9fafb] text-[#111]"
            />
          </div>
          <select
            value={sid}
            onChange={e => handleSelectPatient(e.target.value)}
            className="w-full px-2 py-1.5 text-[13px] border border-[#d1d5db] rounded outline-none focus:border-[#5e6ad2] bg-[#f9fafb] text-[#111] cursor-pointer"
          >
            <option value="">— 환자 선택 —</option>
            {filteredPatients.map(p => (
              <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
            ))}
          </select>
        </div>

        {/* AI 요약 */}
        {(prediction || dataLoading) && (
          <div className="bg-white border border-[#d1d5db] rounded-lg p-3 shadow-sm space-y-2">
            <p className="text-[11px] font-bold text-[#6b7280] uppercase tracking-wider">AI 분석 요약</p>
            {dataLoading ? (
              <div className="flex items-center gap-1.5 text-[13px] text-[#9ca3af]">
                <Loader2 size={13} className="animate-spin" /> 분석 중…
              </div>
            ) : (
              <>
                {prediction && (
                  <div>
                    <div className={`text-[28px] font-bold font-mono tabular-nums leading-none ${
                      prediction.probability_pct >= 60 ? 'text-red-600' : 'text-emerald-600'
                    }`}>
                      {prediction.probability_pct.toFixed(1)}%
                    </div>
                    <div className="text-[11px] text-[#6b7280] mt-0.5">XGBoost 악성 확률</div>
                  </div>
                )}
                {rmi?.rmi_score != null && (
                  <div className="flex justify-between text-[13px] border-t border-[#f3f4f6] pt-2">
                    <span className="text-[#6b7280]">RMI 점수</span>
                    <span className={`font-semibold ${rmi.rmi_score >= 200 ? 'text-red-600' : 'text-[#111]'}`}>
                      {rmi.rmi_score.toLocaleString()}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* 액션 버튼 */}
        <div className="bg-white border border-[#d1d5db] rounded-lg p-3 shadow-sm space-y-2">
          {!canWrite && (
            <p className="text-[12px] text-[#9ca3af]">의뢰서 작성은 의사만 가능합니다</p>
          )}
          <button
            onClick={handlePrint}
            disabled={!sid}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-[13px] font-medium border border-[#d1d5db] rounded hover:bg-[#f9fafb] transition-colors text-[#374151] disabled:opacity-40"
          >
            <Printer size={14} /> 미리보기 / 출력
          </button>
          {!submitted ? (
            <button
              onClick={handleSubmit}
              disabled={!canWrite || submitting || !sid}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-[13px] font-medium bg-[#5e6ad2] hover:bg-[#4f5ab8] text-white rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting
                ? <><Loader2 size={14} className="animate-spin" /> 발송 중…</>
                : <><Send size={14} /> 의뢰하기</>
              }
            </button>
          ) : (
            <div className="space-y-1.5">
              <div className="flex items-center justify-center gap-1.5 text-[13px] text-emerald-600 font-semibold py-1">
                <CheckCircle2 size={15} /> 의뢰 완료
              </div>
              <button onClick={() => router.push(`/cdss?subject_id=${sid}`)} className="w-full px-3 py-2 text-[13px] font-medium bg-[#5e6ad2] hover:bg-[#4f5ab8] text-white rounded transition-colors">
                CDSS로 돌아가기
              </button>
              {canWrite && (
                <button
                  onClick={handleCancelReferral}
                  disabled={cancelling}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-[13px] font-medium border border-red-200 text-red-500 hover:bg-red-50 rounded transition-colors disabled:opacity-40"
                >
                  {cancelling
                    ? <><Loader2 size={13} className="animate-spin" /> 취소 중…</>
                    : '의뢰 취소'
                  }
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── 오른쪽: 출력본과 동일한 스타일의 문서 ── */}
      <div className="flex-1 min-w-0">
        {!sid ? (
          <div className="bg-white border border-[#d1d5db] rounded-lg shadow-sm flex items-center justify-center h-56">
            <div className="text-center text-[#9ca3af]">
              <Search size={28} className="mx-auto mb-2 opacity-30" />
              <p className="text-[11px]">왼쪽에서 환자를 선택하면 의뢰서가 자동 작성됩니다</p>
            </div>
          </div>
        ) : (

          /* 출력본과 동일한 스타일로 렌더링된 문서 */
          <div className="bg-white border border-[#d1d5db] rounded-lg shadow-md px-[20px] py-[20px]">

            {/* 문서 제목 */}
            <h2 style={{ fontSize: '19pt', fontWeight: 800, textAlign: 'center', borderBottom: '2.5px solid #111', paddingBottom: '8px', marginBottom: '4px', letterSpacing: '-0.5px', color: '#111' }}>
              난소종양 전원 의뢰서
            </h2>
            <p style={{ textAlign: 'center', fontSize: '9.5pt', color: '#6b7280', marginBottom: '16px' }}>
              Ovarian Tumor Referral Letter
            </p>

            {/* ① 환자 기본정보 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="1" title="환자 기본정보" />
              <div className="px-[12px] py-[8px] grid grid-cols-4 gap-x-4 gap-y-[6px]">
                <RField label="환자명"    value={patient?.patient_name} />
                <RField label="나이"      value={patient?.diag_att_age != null ? `${patient.diag_att_age}세` : null} />
                <RField label="성별"      value={genderLabel !== '—' ? genderLabel : null} />
                <RField label="등록번호"  value={patient?.hadm_id} />
                <RField label="생년월일"  value={patient?.birth_ym} />
                <RField label="환자 ID"   value={patient?.subject_id} />
                <RField label="폐경 여부" value={menopauseLabel !== '—' ? menopauseLabel : null} />
              </div>
            </div>

            {/* ② 진단명 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="2" title="진단명 (의심 상병명)" />
              <div className="px-[12px] py-[8px]">
                <input
                  type="text"
                  value={form.diagnosis}
                  onChange={e => setForm(f => ({ ...f, diagnosis: e.target.value }))}
                  disabled={!canWrite}
                  style={{ fontSize: '11pt', fontWeight: 600, color: '#111', width: '100%', background: 'transparent', border: 0, borderBottom: '1px dashed #d1d5db', outline: 'none', padding: '2px 0', fontFamily: 'inherit' }}
                  className="focus:border-b-[#5e6ad2] disabled:cursor-default"
                />
              </div>
            </div>

            {/* ③ 임상 소견 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="3" title="임상 소견" />
              <div className="px-[12px] py-[8px] grid grid-cols-2 gap-x-6 gap-y-[6px]">
                <RField label="주요 증상" value={patient?.symptoms || (patient ? '기록 없음' : null)} />
                <RField label="CA-125"    value={rmi?.ca125_value != null ? `${rmi.ca125_value.toLocaleString()} U/mL` : null}
                        highlight={rmi?.ca125_value > 35} />
              </div>
            </div>

            {/* ④ 검사 결과 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="4" title="검사 결과 (혈액검사)" />
              <div className="px-[12px] py-[8px]">
                {allLabs.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt' }}>
                    <thead>
                      <tr>
                        {['항목', '결과', '참고범위'].map(h => (
                          <th key={h} style={{ background: '#f9fafb', border: '1px solid #e5e7eb', padding: '3px 8px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ALL_LABS.map(({ key, label, unit, ref }) => {
                        const lab = findLab(key);
                        return (
                          <tr key={key}>
                            <td style={{ border: '1px solid #e5e7eb', padding: '3px 8px', color: '#374151' }}>{label}</td>
                            <td style={{
                              border: '1px solid #e5e7eb', padding: '3px 8px', fontFamily: 'monospace',
                              color: lab?.status === 'high' ? '#dc2626' : lab?.status === 'low' ? '#2563eb' : '#111',
                              fontWeight: (lab?.status === 'high' || lab?.status === 'low') ? 600 : 400,
                            }}>
                              {lab?.value != null ? `${lab.value} ${unit}` : '—'}
                              {lab?.status === 'high' && ' ↑'}
                              {lab?.status === 'low'  && ' ↓'}
                            </td>
                            <td style={{ border: '1px solid #e5e7eb', padding: '3px 8px', color: '#6b7280' }}>{ref}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <p style={{ fontSize: '10pt', color: '#9ca3af' }}>
                    {dataLoading ? '불러오는 중…' : '검사 데이터 없음'}
                  </p>
                )}
              </div>
            </div>

            {/* ⑤ 영상 소견 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="5" title="영상 소견 (초음파 AI)" />
              <div className="px-[12px] py-[8px] grid grid-cols-4 gap-x-4 gap-y-[6px]">
                <RField label="종양 탐지" value={
                  cdssResult?.us_tumor_detected != null
                    ? (cdssResult.us_tumor_detected ? '탐지됨' : '없음')
                    : null
                } highlight={cdssResult?.us_tumor_detected} />
                <RField label="종양 크기"      value={cdssResult?.us_tumor_size_cm2 != null ? `${cdssResult.us_tumor_size_cm2} cm²` : null} />
                <RField label="U스코어"        value={uScore != null ? `${uScore}점` : null} />
                <RField label="FIGO 병기"      value={cdssResult?.us_figo_stage ? (FIGO_LABEL[cdssResult.us_figo_stage] ?? cdssResult.us_figo_stage) : null} />
                <RField label="종양 유형"      value={cdssResult?.us_tumor_type} />
                <RField label="초음파 악성 확률" value={cdssResult?.us_malignancy_prob != null ? `${Number(cdssResult.us_malignancy_prob).toFixed(1)}%` : null} />
              </div>
            </div>

            {/* ⑥ AI 분석 결과 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="6" title="AI 분석 결과" />
              <div className="px-[12px] py-[8px] grid grid-cols-4 gap-x-4 gap-y-[6px]">
                <RField label="RMI 점수"   value={rmi?.rmi_score != null ? rmi.rmi_score.toLocaleString() : null} highlight={rmi?.rmi_score >= 200} />
                <RField label="RMI 위험도" value={rmi?.risk_level ? RISK_LABEL[rmi.risk_level] : null} />
                <RField label="XGBoost 악성 확률"
                        value={prediction?.probability_pct != null ? `${prediction.probability_pct.toFixed(1)}%` : (dataLoading ? '분석 중…' : null)}
                        highlight={prediction?.probability_pct >= 60} />
                <RField label="위험 등급"  value={prediction?.risk_tier ? RISK_LABEL[prediction.risk_tier] : null} />
              </div>
            </div>

            {/* ⑦ 전원 사유 */}
            <div className="mb-[10px] border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="7" title="전원 사유 및 요청사항" />
              <div className="px-[12px] py-[8px]">
                <textarea
                  ref={reasonRef}
                  value={form.reason}
                  onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}
                  disabled={!canWrite}
                  style={{
                    width: '100%', fontSize: '11pt', color: '#111', background: 'transparent',
                    border: 0, outline: 'none', resize: 'none', lineHeight: 1.7, fontFamily: 'inherit',
                    overflow: 'hidden',
                  }}
                  className="disabled:cursor-default"
                />
              </div>
            </div>

            {/* ⑧ 의뢰 기관 / 서명 */}
            <div className="mb-0 border border-[#d1d5db] rounded overflow-hidden">
              <SecHead n="8" title="의뢰 기관 / 의뢰의 서명" />
              <div className="px-[12px] py-[8px]">
                <div className="grid grid-cols-2 gap-x-6 gap-y-[6px] mb-[12px]">
                  <div>
                    <div className="text-[9px] text-[#6b7280] uppercase tracking-wide leading-none mb-[3px]">의뢰 기관</div>
                    <select
                      value={form.destination}
                      onChange={e => setForm(f => ({ ...f, destination: e.target.value }))}
                      disabled={!canWrite}
                      style={{
                        fontSize: '11pt', fontWeight: 600, color: '#111', background: 'transparent',
                        border: 0, borderBottom: '1px dashed #d1d5db', outline: 'none', padding: '2px 0',
                        width: '100%', fontFamily: 'inherit',
                      }}
                      className="disabled:cursor-default"
                    >
                      <option value="">— 선택하세요 —</option>
                      {DEST_OPTIONS.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <div className="text-[9px] text-[#6b7280] uppercase tracking-wide leading-none mb-[6px]">긴급도</div>
                    <div className="flex gap-2">
                      {['일반', '긴급', '응급'].map(key => (
                        <button
                          key={key}
                          onClick={() => canWrite && setForm(f => ({ ...f, urgency: key }))}
                          disabled={!canWrite}
                          className={`px-3 py-[3px] rounded-full text-[10px] font-semibold border transition-colors ${
                            form.urgency === key ? urgencyBadge[key] + ' border-current' : 'bg-white text-[#6b7280] border-[#d1d5db]'
                          } ${!canWrite ? 'cursor-default' : 'cursor-pointer hover:border-[#9ca3af]'}`}
                        >
                          {key}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 서명란 */}
                <div className="grid grid-cols-3 gap-x-6">
                  {[
                    { label: '의뢰의', value: user?.name || user?.employee_id || '—' },
                    { label: '사번',   value: user?.employee_id || '—' },
                    { label: '작성일', value: new Date().toLocaleDateString('ko-KR') },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <div className="text-[9px] text-[#6b7280] uppercase tracking-wide leading-none mb-[3px]">{label}</div>
                      <div style={{ fontSize: '11pt', fontWeight: 600, color: '#111', borderBottom: '1px solid #111', paddingBottom: '4px', minHeight: '28px' }}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <Suspense fallback={null}>
      <ReportsContent />
    </Suspense>
  );
}
