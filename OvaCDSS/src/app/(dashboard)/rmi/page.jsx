'use client';
import { useState } from 'react';
import RiskBadge from '@/components/RiskBadge';

const US_OPTIONS = [
  { value: 0, label: '0점 — 특이소견 없음' },
  { value: 1, label: '1점 — 1가지 이상 소견' },
  { value: 3, label: '3점 — 2가지 이상 소견' },
];

const MENO_OPTIONS = [
  { value: 1, label: '1 (폐경 전)' },
  { value: 3, label: '3 (폐경 후)' },
];

function calcRisk(rmi) {
  if (rmi >= 200) return 'HIGH';
  if (rmi >= 25)  return 'MODERATE';
  return 'LOW';
}

const RISK_BAR  = { HIGH: 'bg-red-500', MODERATE: 'bg-amber-400', LOW: 'bg-emerald-500' };
const RISK_BAR_W = { HIGH: 'w-full', MODERATE: 'w-2/3', LOW: 'w-1/3' };
const RISK_DESC = {
  HIGH:     '수술적 탐색 및 종양내과 협진 권고',
  MODERATE: '추가 정밀검사 및 단기 추적 관찰 권고',
  LOW:      '정기 추적 관찰 유지',
};

export default function RMIPage() {
  const [ca125, setCa125] = useState('');
  const [us,    setUs]    = useState('');
  const [meno,  setMeno]  = useState('');

  const ca125Val = parseFloat(ca125);
  const usVal    = us   !== '' ? Number(us)   : null;
  const menoVal  = meno !== '' ? Number(meno) : null;

  const ready = !isNaN(ca125Val) && ca125Val > 0 && usVal !== null && menoVal !== null;
  const rmi   = ready ? ca125Val * usVal * menoVal : null;
  const risk  = rmi !== null ? calcRisk(rmi) : null;

  const reset = () => { setCa125(''); setUs(''); setMeno(''); };

  const inputCls = "w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors";
  const labelCls = "block text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5";

  return (
    <div className="p-8 max-w-xl">
      <div className="mb-7">
        <h1 className="text-2xl font-semibold text-ink mb-1" style={{ letterSpacing: '-0.5px' }}>RMI 계산기</h1>
        <p className="text-sm text-ink-subtle">Risk of Malignancy Index = CA-125 × 초음파 점수 × 폐경 인자</p>
      </div>

      {/* ── 입력 카드 ──────────────────────────────────────────────── */}
      <div className="bg-surface-1 rounded-xl border border-hairline p-5 mb-4">
        <div className="text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-5">입력값</div>

        {/* CA-125 */}
        <div className="mb-5">
          <label className={labelCls}>
            CA-125 <span className="text-ink-tertiary normal-case font-normal">(U/mL)</span>
          </label>
          <input
            type="number" min="0" step="0.1"
            value={ca125}
            onChange={e => setCa125(e.target.value)}
            placeholder="수치 입력"
            className={inputCls}
          />
          {ca125Val > 35 && (
            <p className="text-xs text-red-600 mt-1.5">정상 범위 초과 (기준: 35 U/mL)</p>
          )}
        </div>

        {/* 초음파 점수 */}
        <div className="mb-5">
          <label className={labelCls}>초음파 점수 (U)</label>
          <div className="grid grid-cols-3 gap-2">
            {US_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setUs(String(opt.value))}
                className={`px-3 py-2.5 rounded-lg border text-xs font-medium transition-colors text-left ${
                  us === String(opt.value)
                    ? 'bg-primary border-primary text-white'
                    : 'bg-surface-2 text-ink-subtle border-hairline hover:border-hairline-strong hover:text-ink'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* 폐경 인자 */}
        <div>
          <label className={labelCls}>폐경 인자 (M)</label>
          <div className="grid grid-cols-2 gap-2">
            {MENO_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setMeno(String(opt.value))}
                className={`px-3 py-2.5 rounded-lg border text-xs font-medium transition-colors ${
                  meno === String(opt.value)
                    ? 'bg-primary border-primary text-white'
                    : 'bg-surface-2 text-ink-subtle border-hairline hover:border-hairline-strong hover:text-ink'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── 결과 카드 ──────────────────────────────────────────────── */}
      <div className={`bg-surface-1 rounded-xl border p-5 transition-all ${
        risk === 'HIGH'     ? 'border-red-500/30'
        : risk === 'MODERATE' ? 'border-amber-500/30'
        : 'border-hairline'
      }`}>
        <div className="text-xs font-medium text-ink-subtle uppercase tracking-[0.4px] mb-4">계산 결과</div>

        {rmi !== null ? (
          <>
            <div className="flex items-center gap-4 mb-4">
              <div>
                <div className="text-4xl font-semibold text-ink tabular-nums" style={{ letterSpacing: '-1px' }}>
                  {rmi.toLocaleString()}
                </div>
                <div className="text-xs text-ink-subtle mt-0.5">RMI Score</div>
              </div>
              <div className="ml-1">
                <RiskBadge tier={risk} />
              </div>
            </div>

            <div className="w-full bg-surface-3 rounded-full h-1.5 mb-4 overflow-hidden">
              <div className={`h-1.5 rounded-full transition-all ${RISK_BAR[risk]} ${RISK_BAR_W[risk]}`} />
            </div>

            <p className="text-xs text-ink-muted mb-1">
              <span className="font-semibold text-ink-subtle">계산식:</span>{' '}
              {ca125Val.toLocaleString()} × {usVal} × {menoVal} = {rmi.toLocaleString()}
            </p>
            <p className="text-xs text-ink-subtle">{RISK_DESC[risk]}</p>

            <button
              onClick={reset}
              className="mt-4 text-xs text-ink-tertiary hover:text-ink-subtle underline transition-colors"
            >
              초기화
            </button>
          </>
        ) : (
          <p className="text-sm text-ink-subtle">위 항목을 모두 입력하면 결과가 표시됩니다.</p>
        )}
      </div>
    </div>
  );
}
