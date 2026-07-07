/**
 * api.js — FastAPI 백엔드 클라이언트
 *
 * MIMIC-IV 필드 → 프론트엔드 UI 필드 변환도 여기서 처리한다.
 * MIMIC-IV는 환자 이름을 익명화하므로 subject_id 기반으로 표시한다.
 *
 * 백엔드 연결 실패 시 에러를 상위 컴포넌트로 전파해 화면에 오류 배너를 표시한다.
 * (loginUser만 예외 — 네트워크 단절 시 개발용 목업 인증으로 폴백)
 */

import { MOCK_USERS } from './mockData';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API 오류 (${res.status})`);
  }
  return res.json();
}

// ── 한국 여성 이름 목업 생성기 (subject_id → 결정적 이름) ────────────────────

const _SURNAMES = ['김','이','박','최','정','강','조','윤','장','임','한','오','서','신','권','황','안','송','류','전','홍','고','문','양','손','배','백','허','유','남','심','노','하','곽','성','차','주','우','구','민','나','진','엄','채','원','천','방','공','석','변'];
const _GIVEN    = ['지현','서연','수연','지은','민지','수빈','지영','예은','수진','지혜','은지','민서','예지','유나','지수','나은','소연','혜진','지원','유진','미나','지선','지아','소현','혜원','수아','은혜','지효','나래','소희','예린','지민','서현','은비','다현','혜린','유경','수경','민아','예원','지윤','소영','혜수','은수','지연','나영','유빈','민혜','수현','아름'];

function _mockKoreanName(subject_id) {
  const n = Number(subject_id);
  return _SURNAMES[n % _SURNAMES.length] + _GIVEN[Math.floor(n / _SURNAMES.length) % _GIVEN.length];
}

// ── 생년월일 포맷 헬퍼 ───────────────────────────────────────────────────────────
// birth_year가 YYYYMMDD(8자리)면 직접 파싱, 아니면 subject_id 기반 결정적 월/일 계산
const _MDAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
function _computeBirthYm(subjectId, anchorYear, diagAttAge, birthYearRaw) {
  if (birthYearRaw != null && birthYearRaw >= 10000000) {
    return String(birthYearRaw); // "19590620"
  }
  // 폴백: anchor_year - diag_att_age + subject_id 기반 결정적 월/일
  const refYear   = anchorYear ?? new Date().getFullYear();
  const birthYear = diagAttAge != null ? refYear - diagAttAge : null;
  if (!birthYear) return '정보 없음';
  const n     = Number(subjectId);
  const month = (n % 12) + 1;
  const day   = (Math.floor(n / 12) % _MDAYS[month - 1]) + 1;
  return `${birthYear}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`;
}

// ── 케이스 코드 포맷 헬퍼 ───────────────────────────────────────────────────────
// 11자리 합성 hadm_id(ova_ultrasound용): ADM-15599266_001
// 그 외 hadm_id: ADM-23417804
function _fmtCaseCode(hadmId) {
  const s = String(hadmId);
  if (s.length === 11) return `ADM-${s.slice(0, 8)}_${s.slice(8)}`;
  return `ADM-${s}`;
}

// ── 데이터 변환 헬퍼 ─────────────────────────────────────────────────────────

/**
 * MIMIC-IV 스크리닝 환자 한 행 → 프론트엔드 테이블 행
 */
function mapScreeningPatient(p) {
  const id     = String(p.subject_id);
  const ca125  = p.ca125_value ?? null;
  const rmi    = p.rmi_score   != null ? Math.round(p.rmi_score) : null;
  const riskTier = p.risk_level ?? null;

  const lastUpdated = (p.rmi_calculated_at || p.admittime || '').split('T')[0] || '';
  const admitDate   = (p.status_updated_at || '').split('T')[0] || '—';

  return {
    id,
    name:        p.patient_name || _mockKoreanName(p.subject_id),
    age:          p.age ?? 0,
    dept:        'GY',                      // MIMIC-IV에는 과 정보가 없어 기본값 사용
    ca125,
    rmi:          rmi ?? 0,
    menopause:    p.menopause_factor === 3,
    riskTier:     riskTier ?? 'UNKNOWN',
    status:       p.status ?? '신규',
    lastUpdated,
    admitDate,
    // 원본 필드 (상세 페이지 이동 등에 사용)
    subject_id:   p.subject_id,
    hadm_id:      p.hadm_id,
    gender:       p.gender,
    anchor_year:  p.anchor_year,
  };
}

/**
 * MIMIC-IV 환자 상세 + 날짜별 검사/활력징후 → 상세 페이지 데이터
 */
function mapPatientDetail(p, labsByDate, vitalsByDate) {
  const birthYm = _computeBirthYm(p.subject_id, p.anchor_year, p.diag_att_age, p.birth_year);

  const ca125 = (p.ca125_value != null && !Number.isNaN(Number(p.ca125_value)))
    ? p.ca125_value : null;
  const rmiScore = (p.rmi_score != null && !Number.isNaN(Number(p.rmi_score)))
    ? Math.round(p.rmi_score) : null;

  return {
    pt_id:           `PT-${String(p.subject_id).padStart(6, '0')}`,
    patient_reg_no:  p.hadm_id ? _fmtCaseCode(p.hadm_id) : `PT-${p.subject_id}`,
    patient_name:    p.patient_name || _mockKoreanName(p.subject_id),
    birth_ym:        birthYm,
    diag_att_age:    p.diag_att_age ?? '—',
    risk_level:      p.risk_level ?? null,
    status:          p.status     ?? '신규',
    last_updated:    (p.rmi_calculated_at || p.status_updated_at || '').split('T')[0] || '—',
    labResultsByDate: labsByDate  ?? [],
    vitalsByDate:     vitalsByDate ?? [],
    // RMI 계산값 (fetch_patient_detail latest_rmi CTE에서 옴)
    rmi: {
      us_score:        p.us_score        ?? null,
      menopause_factor: p.menopause_factor ?? null,
      ca125_value:     ca125,
      rmi_score:       rmiScore,
      risk_level:      p.risk_level      ?? null,
    },
    height: p.height ?? null,
    weight: p.weight ?? null,
    bmi:    p.bmi    ?? null,
    // 원본 필드
    subject_id:      p.subject_id,
    gender:          p.gender,
    hadm_id:         p.hadm_id,
  };
}

// ── 공개 API ─────────────────────────────────────────────────────────────────

/**
 * 스크리닝 환자 목록 (프론트엔드 형식으로 변환)
 */
export async function getPatients(page = 1, limit = 20) {
  const data = await apiFetch(`/api/patients?page=${page}&limit=${limit}`);
  const patients = Array.isArray(data.data) ? data.data.map(mapScreeningPatient) : [];
  return {
    patients,
    total:      data.total      ?? patients.length,
    page:       data.page       ?? page,
    limit:      data.limit      ?? limit,
    totalPages: data.total_pages ?? 1,
  };
}

/**
 * 환자 상세 (기본정보 + 날짜별 검사 + 날짜별 활력징후를 병렬로 가져옴)
 * _shape_patient_detail 출력을 그대로 사용하되 birth_ym·pt_id·patient_name만 보정
 */
export async function getPatientDetail(subjectId) {
  const [patientRaw, labsByDate, vitalsByDate] = await Promise.all([
    apiFetch(`/api/patients/${subjectId}`),
    apiFetch(`/api/patients/${subjectId}/labs/by-date`),
    apiFetch(`/api/patients/${subjectId}/vitals/by-date`),
  ]);

  const birthYm = _computeBirthYm(
    patientRaw.subject_id ?? subjectId,
    patientRaw.anchor_year,
    patientRaw.diag_att_age,
    patientRaw.birth_year,
  );

  return {
    ...patientRaw,                            // rmi·diag_att_age·status·last_updated 등 그대로
    pt_id:           `PT-${String(patientRaw.subject_id).padStart(6, '0')}`,
    birth_ym:        birthYm,
    patient_name:    patientRaw.patient_name || _mockKoreanName(subjectId),
    labResultsByDate: labsByDate ?? patientRaw.labResultsByDate ?? [],
    vitalsByDate:    vitalsByDate ?? [],
  };
}

/**
 * 스크리닝 상태 변경
 */
export async function updatePatientStatus(subjectId, status, updatedBy = null) {
  return apiFetch(`/api/patients/${subjectId}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status, updated_by: updatedBy }),
  });
}

/**
 * RMI 계산 결과 저장
 */
export async function saveRmiScore(subjectId, { ca125Value, usScore, menopauseFactor, hadmId, notes }) {
  return apiFetch(`/api/patients/${subjectId}/rmi`, {
    method: 'POST',
    body: JSON.stringify({
      ca125_value:      ca125Value,
      us_score:         usScore,
      menopause_factor: menopauseFactor,
      hadm_id:          hadmId,
      notes,
    }),
  });
}

/**
 * 로그인 (DB 인증). 백엔드 연결 불가 시 목업 인증으로 폴백.
 */
export async function loginUser(employeeId, password) {
  try {
    return await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ employee_id: employeeId, password }),
    });
  } catch (err) {
    // 백엔드 자체가 꺼진 경우(TypeError)만 목업으로 폴백
    if (err instanceof TypeError) {
      console.warn('[api] 백엔드 연결 실패 — 목업 인증으로 폴백');
      const found = MOCK_USERS.find(
        u => u.employee_id === employeeId && u.password === password
      );
      if (found) return { employee_id: found.employee_id, name: found.name, role: found.role };
      throw new Error('사번 또는 비밀번호가 올바르지 않습니다.');
    }
    throw err;
  }
}

/**
 * 비밀번호 변경
 */
export async function changePassword(employeeId, currentPassword, newPassword) {
  try {
    return await apiFetch('/api/auth/change-password', {
      method: 'PUT',
      body: JSON.stringify({ employee_id: employeeId, current_password: currentPassword, new_password: newPassword }),
    });
  } catch (err) {
    if (err instanceof TypeError) throw new Error('서버에 연결할 수 없습니다.');
    throw err;
  }
}

/**
 * 프로필 수정 (이름 변경)
 */
export async function updateProfile(employeeId, name) {
  try {
    return await apiFetch('/api/auth/profile', {
      method: 'PUT',
      body: JSON.stringify({ employee_id: employeeId, name }),
    });
  } catch (err) {
    if (err instanceof TypeError) throw new Error('서버에 연결할 수 없습니다.');
    throw err;
  }
}

/**
 * 신규 환자 등록 (간호사 전용)
 */
export async function registerPatient({ gender, birth_year, admission_type, admit_date, name, symptoms, menopause, registered_by, has_diabetes, has_hypertension, has_hyperlipidemia, height, weight, bmi }) {
  return apiFetch('/api/patients/register', {
    method: 'POST',
    body: JSON.stringify({ gender, birth_year, admission_type, admit_date, name, symptoms, menopause, registered_by, has_diabetes, has_hypertension, has_hyperlipidemia, height, weight, bmi }),
  });
}

/**
 * 파싱된 검사결과 rows 업로드
 */
export async function uploadLabData(subjectId, rows, uploadedBy = null) {
  return apiFetch(`/api/patients/${subjectId}/labs/upload`, {
    method: 'POST',
    body: JSON.stringify({ rows, uploaded_by: uploadedBy }),
  });
}

/**
 * 환자 기본정보 (CDSS 페이지에서 환자명 표시용)
 * MIMIC 익명 환자는 subject_id 기반 한국 이름으로 변환해서 반환
 */
export async function getPatientBasic(subjectId) {
  const data = await apiFetch(`/api/patients/${subjectId}`);
  return {
    ...data,
    // CDSS 페이지가 rmi.*를 최상위 필드로 접근하므로 flatten
    rmi_score:        data.rmi?.rmi_score        ?? null,
    us_score:         data.rmi?.us_score         ?? null,
    menopause_factor: data.rmi?.menopause_factor ?? null,
    ca125_value:      data.rmi?.ca125_value      ?? null,
    patient_name:     data.patient_name || _mockKoreanName(subjectId),
    birth_ym:         _computeBirthYm(data.subject_id ?? subjectId, data.anchor_year, data.diag_att_age, data.birth_year),
  };
}

/**
 * 날짜별 검사결과 (CDSS 혈액수치 표시용)
 */
export async function getLabsByDate(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/labs/by-date`);
}

/**
 * 스크리닝 상태 조회
 */
export async function getPatientStatus(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/status`);
}

/**
 * 의뢰서 저장 (저장 후 상태가 '의뢰완료'로 자동 변경됨)
 */
export async function cancelReferral(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/referral`, { method: 'DELETE' });
}

export async function saveReferral(subjectId, { doctorId, urgency, destination, content, hadmId = null }) {
  return apiFetch(`/api/patients/${subjectId}/referral`, {
    method: 'POST',
    body: JSON.stringify({
      doctor_id:   doctorId,
      urgency,
      destination: destination || null,
      content:     content || null,
      hadm_id:     hadmId,
    }),
  });
}

/**
 * 동반질환 조회 — 당뇨(E11%), 고혈압(I10%), 고지혈증(E78%)
 */
export async function getComorbidities(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/comorbidities`);
}

/**
 * 초음파 AI 분석 결과 조회 (ova_cdss_results 최신 1건)
 */
export async function getCdssResult(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/cdss-result`);
}

/**
 * TyG XGBoost 악성 종양 예측
 * 반환: { probability_pct, prediction, risk_tier, tyg_index, features_used, missing_features }
 */
export async function runCdssPredict(subjectId) {
  return apiFetch(`/api/patients/${subjectId}/predict`, { method: 'POST' });
}

/**
 * 전체 환자 일괄 예측 — 환자목록 위험도 퍼센트 표시용
 * 반환: { [subject_id]: probability_pct }
 */
export async function getAllPredictions() {
  return apiFetch('/api/predictions');
}

/**
 * 헬스체크
 */
export async function checkApiHealth() {
  return apiFetch('/health');
}

/**
 * Orthanc에 초음파 이미지가 등록된 subject_id Set 반환
 */
export async function getDicomSubjectIds() {
  const data = await apiFetch('/api/dicom/has-images');
  return new Set((data.subject_ids ?? []).map(Number));
}

export async function getLandingStats() {
  return apiFetch('/api/stats/summary');
}
