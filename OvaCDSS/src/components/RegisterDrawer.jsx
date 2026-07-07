'use client';
import { useState, useRef, useCallback } from 'react';
import { X, CheckCircle, Upload, FileSpreadsheet } from 'lucide-react';
import * as XLSX from 'xlsx';
import { useAuth } from '@/lib/AuthContext';
import { registerPatient, uploadLabData } from '@/lib/api';

const ADMISSION_TYPES = [
  { value: 'ELECTIVE', label: '외래 (ELECTIVE)' },
  { value: 'URGENT',   label: '긴급 (URGENT)'   },
];

const CURR_YEAR = new Date().getFullYear();

// ── 검사항목 자동 인식 ────────────────────────────────────────────────────────

const LAB_NAME_MAP = {
  ca125:      ['ca-125', 'ca125', 'ca_125', 'cancer antigen 125'],
  glucose:    ['glucose', '혈당', 'glu'],
  tg:         ['triglycerides', 'triglyceride', 'tg', '중성지방'],
  albumin:    ['albumin', 'alb', '알부민'],
  ast:        ['ast', 'ast(got)', 'got'],
  alt:        ['alt', 'alt(gpt)', 'gpt'],
  bun:        ['bun', 'urea nitrogen', '요소질소', 'blood urea nitrogen'],
  hemoglobin: ['hemoglobin', 'hb', 'hgb', '헤모글로빈'],
  hdl:        ['hdl', 'hdl cholesterol', 'hdl-c', 'hdl-콜레스테롤'],
  platelet:   ['platelet', 'plt', '혈소판', 'platelet count'],
  pt_inr:     ['pt-inr', 'pt_inr', 'inr(pt)', 'inr', 'prothrombin time'],
  wbc:        ['wbc', 'white blood cells', '백혈구'],
  height:     ['height', '키', '신장', '키(cm)'],
  weight:     ['weight', '체중', '몸무게', '체중(kg)'],
  bmi:        ['bmi', 'body mass index'],
};

const LAB_DISPLAY_META = [
  { key: 'ca125',      label: 'CA-125',  unit: 'U/mL'  },
  { key: 'glucose',    label: 'Glucose', unit: 'mg/dL' },
  { key: 'tg',         label: 'TG',      unit: 'mg/dL' },
  { key: 'albumin',    label: 'Albumin', unit: 'g/dL'  },
  { key: 'ast',        label: 'AST',     unit: 'U/L'   },
  { key: 'alt',        label: 'ALT',     unit: 'U/L'   },
  { key: 'bun',        label: 'BUN',     unit: 'mg/dL' },
  { key: 'hemoglobin', label: 'Hb',      unit: 'g/dL'  },
  { key: 'hdl',        label: 'HDL',     unit: 'mg/dL' },
  { key: 'platelet',   label: 'Plt',     unit: 'K/μL'  },
  { key: 'pt_inr',     label: 'PT-INR',  unit: ''      },
  { key: 'wbc',        label: 'WBC',     unit: 'K/μL'  },
  { key: 'height',     label: '키',      unit: 'cm'    },
  { key: 'weight',     label: '몸무게',  unit: 'kg'    },
  { key: 'bmi',        label: 'BMI',     unit: ''      },
];

function extractLabValues(rows) {
  const vals = {};
  for (const row of rows) {
    const name = (row.test_name || '').toLowerCase().trim();
    for (const [key, aliases] of Object.entries(LAB_NAME_MAP)) {
      if (key in vals) continue;
      if (aliases.some(a => name === a || name.includes(a))) {
        if (row.value != null && !isNaN(row.value)) {
          vals[key] = row.value;
          break;
        }
      }
    }
  }
  // 키·몸무게로 BMI 자동 계산
  if (!vals.bmi && vals.height && vals.weight && vals.height > 0) {
    const h = vals.height / 100;
    vals.bmi = Math.round((vals.weight / (h * h)) * 10) / 10;
  }
  return vals;
}

const getToday  = () => new Date().toISOString().split('T')[0];
const COMORBIDITY_OPTIONS = [
  { key: 'hasDiabetes',      label: '당뇨'    },
  { key: 'hasHypertension',  label: '고혈압'  },
  { key: 'hasHyperlipidemia', label: '고지혈증' },
];

const INIT_FORM = () => ({
  name:               '',
  gender:             'F',
  birthDate:          '',
  admissionType:      'ELECTIVE',
  admitDate:          getToday(),
  menopause:          null,
  symptoms:           '',
  hasDiabetes:        false,
  hasHypertension:    false,
  hasHyperlipidemia:  false,
});

// ── Excel / CSV 파싱 ──────────────────────────────────────────────────────────

function parseLabFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const wb   = XLSX.read(e.target.result, { type: 'array' });
        const ws   = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

        if (rows.length < 2) { reject(new Error('데이터가 없습니다.')); return; }

        const hdrs = rows[0].map(h => String(h).trim().toLowerCase());
        const idx  = (keywords) => hdrs.findIndex(h => keywords.some(k => h.includes(k)));

        const nameCol = idx(['검사', '항목', 'test', 'name']);
        const valCol  = idx(['결과', '수치', 'value', 'result']);
        const unitCol = idx(['단위', 'unit']);
        const dateCol = idx(['날짜', '일자', '측정', 'date']);

        const parsed = rows.slice(1)
          .filter(r => r.some(v => v !== ''))
          .map(r => ({
            test_name:     String(r[nameCol >= 0 ? nameCol : 0] || '').trim(),
            value:         parseFloat(r[valCol  >= 0 ? valCol  : 1]) || null,
            unit:          unitCol >= 0 ? String(r[unitCol] || '').trim() : '',
            recorded_date: dateCol >= 0 ? String(r[dateCol] || '').trim() : '',
          }))
          .filter(r => r.test_name && r.value !== null && !isNaN(r.value));

        resolve({ headers: rows[0].map(String), data: parsed });
      } catch { reject(new Error('파일을 읽을 수 없습니다.')); }
    };
    reader.onerror = () => reject(new Error('파일 읽기 실패'));
    reader.readAsArrayBuffer(file);
  });
}

// ── 컴포넌트 ──────────────────────────────────────────────────────────────────

export default function RegisterDrawer({ open, onClose, onSuccess }) {
  const { user } = useAuth();
  const fileInputRef = useRef(null);

  const [form,       setForm]       = useState(INIT_FORM);
  const [errors,     setErrors]     = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError,   setApiError]   = useState('');
  const [done,       setDone]       = useState(null);

  // 파일 업로드 상태
  const [labFile,      setLabFile]      = useState(null);
  const [labParsed,    setLabParsed]    = useState(null); // { headers, data }
  const [labValues,    setLabValues]    = useState({});   // 자동 인식된 15개 수치
  const [labFileError, setLabFileError] = useState('');
  const [dragOver,     setDragOver]     = useState(false);

  const set = (key, val) => {
    setForm(f => ({ ...f, [key]: val }));
    setErrors(e => ({ ...e, [key]: '' }));
  };


  // ── 파일 처리 ────────────────────────────────────────────────────────────────

  const handleFile = useCallback(async (file) => {
    setLabFileError('');
    setLabParsed(null);
    setLabFile(file);
    try {
      const result = await parseLabFile(file);
      if (result.data.length === 0) {
        setLabFileError('유효한 검사결과 행이 없습니다. 첫 행이 헤더인지 확인해주세요.');
        setLabFile(null);
      } else {
        setLabParsed(result);
        const lv = extractLabValues(result.data);
        setLabValues(lv);
      }
    } catch (err) {
      setLabFileError(err.message);
      setLabFile(null);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  // ── 유효성 검사 ───────────────────────────────────────────────────────────────

  const validate = () => {
    const e = {};
    if (!form.birthDate)
      e.birthDate = '생년월일을 입력해주세요';
    else {
      const yr = new Date(form.birthDate).getFullYear();
      if (yr < 1900 || yr > CURR_YEAR) e.birthDate = `생년월일을 확인해주세요 (1900–${CURR_YEAR})`;
    }
    if (!form.admitDate)
      e.admitDate = '입원일을 입력해주세요';
    if (form.menopause === null)
      e.menopause = '폐경 여부를 선택해주세요';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  // ── 제출 ─────────────────────────────────────────────────────────────────────

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setApiError('');
    try {
      // CSV에서 키/몸무게/BMI 추출 (없으면 null)
      const csvHeight = labValues.height || null;
      const csvWeight = labValues.weight || null;
      const csvBmi    = labValues.bmi
        || (csvHeight && csvWeight
          ? Math.round(csvWeight / ((csvHeight / 100) ** 2) * 10) / 10
          : null);

      const result = await registerPatient({
        gender:             form.gender,
        birth_year:         new Date(form.birthDate).getFullYear(),
        admission_type:     form.admissionType,
        admit_date:         form.admitDate,
        name:               form.name.trim() || null,
        symptoms:           form.symptoms.trim() || null,
        menopause:          form.menopause,
        registered_by:      user?.employee_id,
        has_diabetes:       form.hasDiabetes,
        has_hypertension:   form.hasHypertension,
        has_hyperlipidemia: form.hasHyperlipidemia,
        height:             csvHeight,
        weight:             csvWeight,
        bmi:                csvBmi,
      });

      // 검사결과 저장 (날짜 없는 행은 등록일로 채움)
      if (labParsed?.data?.length > 0) {
        const today = getToday();
        const rows = labParsed.data.map(r => ({
          ...r,
          recorded_date: r.recorded_date || today,
        }));
        await uploadLabData(result.subject_id, rows, user?.employee_id);
      }

      setDone(result);
      onSuccess?.();
    } catch (err) {
      setApiError(err.message || '등록에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setForm(INIT_FORM);
    setErrors({});
    setApiError('');
    setDone(null);
    setLabFile(null);
    setLabParsed(null);
    setLabValues({});
    setLabFileError('');
    onClose();
  };

  // ── 렌더링 ───────────────────────────────────────────────────────────────────

  return (
    <>
      {/* 오버레이 */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px] transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`}
        style={{ pointerEvents: open ? 'auto' : 'none' }}
        onClick={handleClose}
      />

      {/* 드로어 */}
      <div
        className={`fixed right-0 top-0 h-full w-[440px] z-50 bg-surface-1 border-l border-hairline flex flex-col shadow-2xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}
        style={{ pointerEvents: open ? 'auto' : 'none' }}
      >

        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 h-16 border-b border-hairline shrink-0">
          <h2 className="text-sm font-semibold text-ink">신규 환자 등록</h2>
          <button onClick={handleClose} className="text-ink-tertiary hover:text-ink-subtle transition-colors p-1">
            <X size={15} />
          </button>
        </div>

        {done ? (
          /* ── 성공 화면 ── */
          <div className="flex-1 flex flex-col items-center justify-center gap-4 px-8 text-center">
            <div className="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center">
              <CheckCircle size={26} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink mb-1">등록 완료</p>
              <p className="text-xs text-ink-subtle">
                {done.name ? <><span className="font-medium text-ink">{done.name}</span> · </> : ''}환자 ID{' '}
                <span className="font-mono font-medium text-ink">{done.subject_id}</span>로 등록됐습니다.
              </p>
              {labParsed && (
                <p className="text-xs text-emerald-600 mt-1 font-medium">
                  혈액검사 {labParsed.data.length}건 DB 저장 완료
                </p>
              )}
            </div>
            <button
              onClick={handleClose}
              className="mt-2 px-6 py-2.5 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors"
            >
              닫기
            </button>
          </div>
        ) : (
          <>
            {/* ── 폼 ── */}
            <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4">

              {/* 이름 */}
              <Field label="이름">
                <input
                  type="text"
                  value={form.name}
                  onChange={e => set('name', e.target.value)}
                  placeholder="홍길동"
                  className="w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors"
                />
              </Field>

              {/* 성별 */}
              <Field label="성별" required>
                <div className="grid grid-cols-2 gap-2">
                  {[{ v: 'F', l: '여성' }, { v: 'M', l: '남성' }].map(({ v, l }) => (
                    <button
                      key={v}
                      onClick={() => set('gender', v)}
                      className={`py-2.5 text-sm rounded-lg border transition-colors ${form.gender === v ? 'bg-primary text-white border-primary' : 'border-hairline text-ink-subtle hover:border-primary/40 hover:text-ink'}`}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </Field>

              {/* 생년월일 */}
              <Field label="생년월일" required error={errors.birthDate}>
                <input
                  type="date"
                  max={`${CURR_YEAR}-12-31`}
                  min="1900-01-01"
                  value={form.birthDate}
                  onChange={e => set('birthDate', e.target.value)}
                  className={`w-full px-3.5 py-2.5 bg-surface-2 border rounded-lg text-sm text-ink outline-none transition-colors ${errors.birthDate ? 'border-red-500/50 focus:border-red-500' : 'border-hairline focus:border-primary'}`}
                />
              </Field>

              {/* 폐경 유무 */}
              <Field label="폐경 유무" required error={errors.menopause}>
                <div className="grid grid-cols-2 gap-2">
                  {[{ v: true, l: '예' }, { v: false, l: '아니오' }].map(({ v, l }) => (
                    <button
                      key={String(v)}
                      onClick={() => { set('menopause', v); setErrors(e => ({ ...e, menopause: '' })); }}
                      className={`py-2.5 text-sm rounded-lg border transition-colors ${form.menopause === v ? 'bg-primary text-white border-primary' : 'border-hairline text-ink-subtle hover:border-primary/40 hover:text-ink'}`}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </Field>

              {/* 입원 유형 */}
              <Field label="입원 유형">
                <div className="relative">
                  <select
                    value={form.admissionType}
                    onChange={e => set('admissionType', e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors appearance-none cursor-pointer"
                  >
                    {ADMISSION_TYPES.map(({ value, label }) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-tertiary text-[10px]">▼</span>
                </div>
              </Field>

              {/* 입원일 */}
              <Field label="입원일" required error={errors.admitDate}>
                <input
                  type="date"
                  value={form.admitDate}
                  onChange={e => set('admitDate', e.target.value)}
                  className={`w-full px-3.5 py-2.5 bg-surface-2 border rounded-lg text-sm text-ink outline-none transition-colors ${errors.admitDate ? 'border-red-500/50 focus:border-red-500' : 'border-hairline focus:border-primary'}`}
                />
              </Field>

              {/* 기저질환 */}
              <Field label="기저질환">
                <div className="flex gap-3">
                  {COMORBIDITY_OPTIONS.map(({ key, label }) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => set(key, !form[key])}
                      className={`flex items-center gap-2 px-3.5 py-2.5 rounded-lg border text-sm transition-colors ${
                        form[key]
                          ? 'bg-primary/10 border-primary text-primary font-medium'
                          : 'border-hairline text-ink-subtle hover:border-primary/40 hover:text-ink'
                      }`}
                    >
                      <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${form[key] ? 'bg-primary border-primary' : 'border-hairline-strong'}`}>
                        {form[key] && <span className="text-white text-[10px] font-bold leading-none">✓</span>}
                      </span>
                      {label}
                    </button>
                  ))}
                </div>
              </Field>

              {/* 증상 */}
              <Field label="증상">
                <textarea
                  value={form.symptoms}
                  onChange={e => set('symptoms', e.target.value)}
                  placeholder="주요 증상을 입력해주세요"
                  rows={3}
                  className="w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors resize-none"
                />
              </Field>

              {/* 검사결과 파일 업로드 */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="flex items-center gap-1 text-[11px] font-medium text-ink-subtle uppercase tracking-[0.4px]">
                    검사결과 파일
                    <span className="font-normal text-ink-tertiary normal-case">(Excel / CSV)</span>
                  </label>
                  <a
                    href="/sample_labs.csv"
                    download="sample_labs.csv"
                    className="text-[10px] text-primary hover:underline"
                  >
                    샘플 다운로드
                  </a>
                </div>

                {!labParsed ? (
                  <div
                    onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`cursor-pointer rounded-xl border-2 border-dashed transition-colors py-7 flex flex-col items-center gap-2 ${dragOver ? 'border-primary bg-primary/5' : 'border-hairline-strong bg-surface-2 hover:border-primary/50'}`}
                  >
                    <div className="w-9 h-9 rounded-lg bg-surface-1 border border-hairline flex items-center justify-center">
                      <Upload size={16} className="text-ink-tertiary" />
                    </div>
                    <p className="text-xs text-ink-subtle">파일을 드래그하거나 클릭하여 업로드</p>
                    <p className="text-[10px] text-ink-tertiary">.xlsx · .xls · .csv</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      className="hidden"
                      onChange={e => { if (e.target.files[0]) handleFile(e.target.files[0]); }}
                    />
                  </div>
                ) : (
                  <div className="bg-surface-1 border border-hairline rounded-xl p-3.5">
                    {/* 파일 정보 */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0">
                          <FileSpreadsheet size={14} className="text-emerald-600" />
                        </div>
                        <div>
                          <p className="text-xs font-medium text-ink leading-tight">{labFile?.name}</p>
                          <p className="text-[10px] text-ink-tertiary mt-0.5">{labParsed.data.length}건 인식됨</p>
                        </div>
                      </div>
                      <button
                        onClick={() => { setLabFile(null); setLabParsed(null); setLabValues({}); setLabFileError(''); }}
                        className="text-ink-tertiary hover:text-ink-subtle transition-colors"
                      >
                        <X size={14} />
                      </button>
                    </div>

                    {/* 미리보기 */}
                    <div className="overflow-x-auto rounded-lg border border-hairline">
                      <table className="w-full text-[11px]">
                        <thead>
                          <tr className="bg-surface-2 border-b border-hairline">
                            <th className="px-2.5 py-1.5 text-left text-ink-tertiary font-medium">검사명</th>
                            <th className="px-2.5 py-1.5 text-right text-ink-tertiary font-medium">결과값</th>
                            <th className="px-2.5 py-1.5 text-left text-ink-tertiary font-medium">단위</th>
                          </tr>
                        </thead>
                        <tbody>
                          {labParsed.data.slice(0, 4).map((r, i) => (
                            <tr key={i} className="border-b border-hairline last:border-0">
                              <td className="px-2.5 py-1.5 text-ink">{r.test_name}</td>
                              <td className="px-2.5 py-1.5 text-right text-ink tabular-nums">{r.value}</td>
                              <td className="px-2.5 py-1.5 text-ink-subtle">{r.unit || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {labParsed.data.length > 4 && (
                        <p className="text-center text-[10px] text-ink-tertiary py-2 border-t border-hairline">
                          외 {labParsed.data.length - 4}건
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {labFileError && (
                  <p className="text-[10px] text-red-600 mt-1">{labFileError}</p>
                )}

                {/* 자동 인식 수치 그리드 */}
                {Object.keys(labValues).length > 0 && (
                  <div className="mt-3">
                    <p className="text-[11px] font-medium text-ink-subtle uppercase tracking-[0.4px] mb-2">
                      자동 인식된 수치 <span className="font-normal normal-case text-ink-tertiary">({Object.keys(labValues).length}/{LAB_DISPLAY_META.length}개)</span>
                    </p>
                    <div className="grid grid-cols-5 gap-1.5">
                      {LAB_DISPLAY_META.map(({ key, label, unit }) => {
                        const val = labValues[key];
                        return (
                          <div
                            key={key}
                            className={`rounded-lg px-2 py-1.5 text-center ${val != null ? 'bg-primary/8 border border-primary/20' : 'bg-surface-2 border border-hairline'}`}
                          >
                            <div className="text-[10px] text-ink-subtle mb-0.5">{label}</div>
                            <div className={`text-xs font-semibold font-mono leading-tight ${val != null ? 'text-primary' : 'text-ink-tertiary'}`}>
                              {val != null ? val : '—'}
                            </div>
                            {val != null && unit && (
                              <div className="text-[9px] text-ink-tertiary mt-0.5">{unit}</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {apiError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {apiError}
                </p>
              )}
            </div>

            {/* 푸터 */}
            <div className="flex gap-2 px-5 py-4 border-t border-hairline shrink-0">
              <button
                onClick={handleClose}
                className="flex-1 py-2.5 text-sm border border-hairline rounded-lg text-ink-subtle hover:text-ink hover:border-hairline-strong transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex-1 py-2.5 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? '등록 중…' : '등록'}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function Field({ label, unit, required, error, children }) {
  return (
    <div>
      <label className="flex items-center gap-1 text-[11px] font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5">
        {label}
        {required && <span className="text-red-500">*</span>}
        {unit && <span className="font-normal text-ink-tertiary normal-case">({unit})</span>}
      </label>
      {children}
      {error && <p className="text-[10px] text-red-600 mt-1">{error}</p>}
    </div>
  );
}
