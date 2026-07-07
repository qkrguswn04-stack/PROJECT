const RISK_STYLE = {
  HIGH:     "bg-red-50     border border-red-200     text-red-700",
  MODERATE: "bg-amber-50   border border-amber-200   text-amber-700",
  LOW:      "bg-emerald-50 border border-emerald-200 text-emerald-700",
};

const RISK_LABEL = {
  HIGH:     "고위험",
  MODERATE: "중등도",
  LOW:      "저위험",
};

const STATUS_DOT = {
  "신규":    "bg-blue-500",
  "관찰중":  "bg-amber-500",
  "검토완료": "bg-emerald-500",
  "의뢰완료": "bg-purple-500",
};

const STATUS_TEXT = {
  "신규":    "text-blue-600",
  "관찰중":  "text-amber-600",
  "검토완료": "text-emerald-600",
  "의뢰완료": "text-purple-600",
};

export default function RiskBadge({ tier, pct }) {
  const label = RISK_LABEL[tier] ?? (tier && tier !== 'UNKNOWN' ? tier : '미확인');
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full ${RISK_STYLE[tier] ?? "bg-surface-2 border border-hairline text-ink-tertiary"}`}>
      {label}
      {pct != null && (
        <span className="font-normal opacity-80">{pct.toFixed(1)}%</span>
      )}
    </span>
  );
}

export function StatusBadge({ status }) {
  const dot  = STATUS_DOT[status]  ?? "bg-ink-tertiary";
  const text = STATUS_TEXT[status] ?? "text-ink-tertiary";
  return (
    <span className={`inline-flex items-center gap-1.5 text-s font-medium ${text}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
      {status}
    </span>
  );
}
