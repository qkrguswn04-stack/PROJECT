'use client';
import { useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Calendar, X } from 'lucide-react';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

function fmt(d) {
  if (!d) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

function sameDay(a, b) {
  return a && b && a.toDateString() === b.toDateString();
}

function between(d, a, b) {
  if (!a || !b) return false;
  const [lo, hi] = a <= b ? [a, b] : [b, a];
  return d > lo && d < hi;
}

function DayCell({ date, isStart, isEnd, inRange, onClick, onEnter, onLeave }) {
  const isSun = date.getDay() === 0;
  const isSat = date.getDay() === 6;
  const isEdge = isStart || isEnd;

  return (
    <div className="relative h-8 flex items-center justify-center">
      {/* 범위 배경 스트립 */}
      {inRange && !isStart && (
        <div className="absolute left-0 right-1/2 inset-y-1 bg-primary/10" />
      )}
      {inRange && !isEnd && (
        <div className="absolute left-1/2 right-0 inset-y-1 bg-primary/10" />
      )}
      {isStart && inRange && (
        <div className="absolute left-1/2 right-0 inset-y-1 bg-primary/10" />
      )}
      {isEnd && inRange && (
        <div className="absolute left-0 right-1/2 inset-y-1 bg-primary/10" />
      )}

      <button
        onMouseEnter={onEnter}
        onMouseLeave={onLeave}
        onClick={onClick}
        className={[
          'relative z-10 w-7 h-7 rounded-full text-xs flex items-center justify-center transition-colors select-none',
          isEdge
            ? 'bg-primary text-white font-semibold'
            : inRange
              ? 'text-ink hover:bg-primary/20'
              : isSun
                ? 'text-red-500 hover:bg-surface-3'
                : isSat
                  ? 'text-blue-500 hover:bg-surface-3'
                  : 'text-ink hover:bg-surface-3',
        ].join(' ')}
      >
        {date.getDate()}
      </button>
    </div>
  );
}

function CalendarGrid({ year, month, start, end, hover, onDayClick, onDayEnter, onDayLeave }) {
  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);

  const rangeEnd = hover || end;

  return (
    <>
      <div className="grid grid-cols-7 mb-1">
        {WEEKDAYS.map(w => (
          <div key={w} className="h-7 flex items-center justify-center text-[10px] font-semibold text-ink-tertiary">
            {w}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((d, i) =>
          d ? (
            <DayCell
              key={i}
              date={d}
              isStart={sameDay(d, start)}
              isEnd={sameDay(d, end) || (!end && sameDay(d, hover))}
              inRange={
                (between(d, start, rangeEnd)) ||
                sameDay(d, start) ||
                sameDay(d, end) ||
                (!end && sameDay(d, hover) && start)
              }
              onClick={() => onDayClick(d)}
              onEnter={() => onDayEnter(d)}
              onLeave={onDayLeave}
            />
          ) : (
            <div key={i} className="h-8" />
          )
        )}
      </div>
    </>
  );
}

export default function DateRangePicker({ value, onChange }) {
  const today = new Date(2026, 5, 15);
  const { start, end } = value;

  const [open, setOpen]       = useState(false);
  const [hover, setHover]     = useState(null);
  const [phase, setPhase]     = useState('start');
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  const ref = useRef(null);

  useEffect(() => {
    const handler = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  };

  const handleDayClick = d => {
    if (phase === 'start') {
      onChange({ start: d, end: null });
      setPhase('end');
    } else {
      const [s, e] = d < start ? [d, start] : [start, d];
      onChange({ start: s, end: e });
      setPhase('start');
      setHover(null);
      setOpen(false);
    }
  };

  const handleClear = e => {
    e?.stopPropagation();
    onChange({ start: null, end: null });
    setPhase('start');
    setHover(null);
  };

  const label = start
    ? end ? `${fmt(start)} ~ ${fmt(end)}` : `${fmt(start)} ~`
    : '날짜 범위 선택';

  const MONTHS_KR = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];

  return (
    <div className="relative" ref={ref}>
      {/* 트리거 버튼 */}
      <button
        onClick={() => setOpen(o => !o)}
        className={[
          'flex items-center gap-1.5 px-3 py-2 text-xs border rounded-lg transition-colors outline-none appearance-none',
          open
            ? 'border-primary text-ink bg-surface-1'
            : 'border-hairline text-ink-subtle bg-surface-1 hover:border-hairline-strong hover:text-ink',
          start ? 'pr-2' : '',
        ].join(' ')}
      >
        <Calendar size={12} className="shrink-0 text-ink-tertiary" />
        <span className={start ? 'text-ink font-medium' : ''}>{label}</span>
        {start && (
          <span
            role="button"
            onClick={handleClear}
            className="ml-0.5 text-ink-tertiary hover:text-ink transition-colors"
          >
            <X size={11} />
          </span>
        )}
      </button>

      {/* 달력 팝오버 */}
      {open && (
        <div className="absolute right-0 mt-1.5 z-50 bg-surface-1 border border-hairline rounded-xl shadow-lg p-4 w-[272px]">
          {/* 월 네비게이션 */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={prevMonth}
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-2 text-ink-subtle transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-sm font-semibold text-ink">
              {viewYear}년 {MONTHS_KR[viewMonth]}
            </span>
            <button
              onClick={nextMonth}
              className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-surface-2 text-ink-subtle transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>

          {/* 달력 */}
          <CalendarGrid
            year={viewYear}
            month={viewMonth}
            start={start}
            end={end}
            hover={phase === 'end' ? hover : null}
            onDayClick={handleDayClick}
            onDayEnter={d => phase === 'end' && setHover(d)}
            onDayLeave={() => setHover(null)}
          />

          {/* 하단 상태 안내 */}
          <div className="mt-3 pt-3 border-t border-hairline flex items-center justify-between">
            <span className="text-[10px] text-ink-tertiary">
              {!start ? '시작일을 선택하세요' : !end ? '종료일을 선택하세요' : `${fmt(start)} ~ ${fmt(end)}`}
            </span>
            {start && (
              <button
                onClick={handleClear}
                className="text-[10px] text-ink-subtle hover:text-red-500 transition-colors"
              >
                초기화
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
