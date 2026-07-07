export const MOCK_USERS = [
  { employee_id: "2025001", password: "1234", name: "박지현", role: "doctor" },
  { employee_id: "2025002", password: "1234", name: "김민준", role: "doctor" },
  { employee_id: "2025003", password: "1234", name: "관리자",  role: "admin"  },
  { employee_id: "2025004", password: "1234", name: "이수진", role: "nurse"  },
];

function riskTier(rmi) {
  if (rmi >= 200) return "HIGH";
  if (rmi >= 25)  return "MODERATE";
  return "LOW";
}

function makePatient(id, name, age, dept, ca125, ultrasoundScore, menopause, status, lastUpdated) {
  const M = menopause ? 3 : 1;
  const rmi = ultrasoundScore * M * ca125;
  return { id, name, age, dept, ca125, ultrasoundScore, menopause, rmi, riskTier: riskTier(rmi), status, lastUpdated };
}

export const MOCK_PATIENTS = [
  makePatient("P001", "김지수", 58, "GY",   892,  3, true,  "신규",    "2026-06-11"),
  makePatient("P002", "박소연", 43, "OB",   78,   1, false, "관찰중",  "2026-06-09"),
  makePatient("P003", "이미래", 67, "GY",   1240, 3, true,  "신규",    "2026-06-11"),
  makePatient("P004", "최유나", 52, "내과", 22,   1, false, "검토완료","2026-05-22"),
  makePatient("P005", "정하은", 39, "OB",   18,   1, false, "제외",    "2026-04-10"),
  makePatient("P006", "강민서", 71, "GY",   678,  3, true,  "신규",    "2026-06-07"),
  makePatient("P007", "오서연", 48, "OB",   45,   1, true,  "관찰중",  "2026-05-28"),
  makePatient("P008", "한지은", 63, "GY",   340,  3, true,  "신규",    "2026-03-15"),
  makePatient("P009", "윤미현", 55, "OB",   38,   1, true,  "관찰중",  "2026-06-03"),
  makePatient("P010", "신예린", 34, "OB",   12,   1, false, "검토완료","2026-05-18"),
];

function lab(test_name, value, unit, ref_range, status, recorded_at = '2026-06-10') {
  return { test_name, value, unit, ref_range, status, recorded_at };
}

function labSet(date, ca125, hdl, alb, ast, alt, cr, bun, hb, wbc, plt, ptinr) {
  const s = (v, lo, hi) => v > hi ? 'high' : v < lo ? 'low' : 'normal';
  return {
    date,
    results: [
      lab('CA-125', ca125, 'U/mL',   '0–35',      s(ca125, 0,   35),   date),
      lab('HDL',    hdl,   'mg/dL',  '40–60',     s(hdl,  40,   60),   date),
      lab('Alb',    alb,   'g/dL',   '3.5–5.0',   s(alb,  3.5,  5.0),  date),
      lab('AST',    ast,   'U/L',    '0–40',      s(ast,  0,    40),   date),
      lab('ALT',    alt,   'U/L',    '0–40',      s(alt,  0,    40),   date),
      lab('Cr',     cr,    'mg/dL',  '0.5–1.1',   s(cr,   0.5,  1.1),  date),
      lab('BUN',    bun,   'mg/dL',  '8–25',      s(bun,  8,    25),   date),
      lab('Hb',     hb,    'g/dL',   '12.0–16.0', s(hb,   12.0, 16.0), date),
      lab('WBC',    wbc,   '10³/μL', '4.0–10.0',  s(wbc,  4.0,  10.0), date),
      lab('PLT',    plt,   '10³/μL', '150–400',   s(plt,  150,  400),  date),
      lab('PT-INR', ptinr, '',       '0.8–1.2',   s(ptinr,0.8,  1.2),  date),
    ],
  };
}

export const MOCK_PATIENT_DETAILS = {
  P001: {
    pt_id: 'P001', patient_reg_no: 'OVA-49210', patient_name: '김지수',
    birth_ym: '1968-03', diag_att_age: 58, risk_level: 'HIGH', status: '신규', last_updated: '2026-06-11',
    labResultsByDate: [
      labSet('2026-06-10',  892, 36, 3.2, 46, 38, 0.9, 27, 10.2,  9.8, 392, 1.12),
      labSet('2026-05-01',  620, 40, 3.5, 38, 32, 0.9, 22, 11.0,  8.5, 350, 1.08),
      labSet('2026-03-20',  380, 44, 3.8, 32, 28, 0.8, 18, 11.8,  7.8, 310, 1.05),
    ],
    rmiCalculation: { ca125_value: 892, us_score: 3, m_factor: 3, rmi_score: 8028, risk_level: 'HIGH' },
    vitalsByDate: [
      { date: '2026-06-11', bp: '142/88', hr: 92, temp: 37.1, rr: 20, spo2: 96, recorded_at: '2026-06-11 08:45' },
      { date: '2026-05-01', bp: '136/84', hr: 88, temp: 36.9, rr: 18, spo2: 97, recorded_at: '2026-05-01 09:10' },
      { date: '2026-03-20', bp: '130/82', hr: 84, temp: 36.8, rr: 17, spo2: 97, recorded_at: '2026-03-20 10:30' },
    ],
  },
  P002: {
    pt_id: 'P002', patient_reg_no: 'OVA-38715', patient_name: '박소연',
    birth_ym: '1983-02', diag_att_age: 43, risk_level: 'MODERATE', status: '관찰중', last_updated: '2026-06-09',
    labResultsByDate: [
      labSet('2026-06-09',  78, 55, 4.1, 28, 22, 0.8, 14, 13.2, 6.5, 245, 1.02),
      labSet('2026-05-12',  65, 58, 4.2, 26, 20, 0.8, 13, 13.5, 6.2, 238, 1.00),
      labSet('2026-04-05',  52, 60, 4.3, 24, 19, 0.8, 12, 13.8, 6.0, 230, 0.98),
    ],
    rmiCalculation: { ca125_value: 78, us_score: 1, m_factor: 1, rmi_score: 78, risk_level: 'MODERATE' },
    vitalsByDate: [
      { date: '2026-06-09', bp: '118/76', hr: 78, temp: 36.8, rr: 16, spo2: 98, recorded_at: '2026-06-09 10:20' },
      { date: '2026-05-12', bp: '116/74', hr: 76, temp: 36.7, rr: 16, spo2: 98, recorded_at: '2026-05-12 11:05' },
      { date: '2026-04-05', bp: '114/72', hr: 74, temp: 36.6, rr: 15, spo2: 99, recorded_at: '2026-04-05 09:50' },
    ],
  },
  P003: {
    pt_id: 'P003', patient_reg_no: 'OVA-52891', patient_name: '이미래',
    birth_ym: '1959-05', diag_att_age: 67, risk_level: 'HIGH', status: '신규', last_updated: '2026-06-11',
    labResultsByDate: [
      labSet('2026-06-11', 1240, 32, 2.9, 58, 47, 1.2, 32,  9.5, 12.4, 445, 1.28),
      labSet('2026-05-08',  980, 35, 3.1, 48, 40, 1.1, 28, 10.2, 11.0, 410, 1.22),
      labSet('2026-04-01',  720, 38, 3.4, 42, 35, 1.0, 24, 10.8,  9.8, 380, 1.18),
    ],
    rmiCalculation: { ca125_value: 1240, us_score: 3, m_factor: 3, rmi_score: 11160, risk_level: 'HIGH' },
    vitalsByDate: [
      { date: '2026-06-11', bp: '150/94', hr: 104, temp: 37.4, rr: 22, spo2: 94, recorded_at: '2026-06-11 09:10' },
      { date: '2026-05-08', bp: '144/90', hr: 98,  temp: 37.2, rr: 20, spo2: 95, recorded_at: '2026-05-08 08:30' },
      { date: '2026-04-01', bp: '138/86', hr: 92,  temp: 37.0, rr: 18, spo2: 96, recorded_at: '2026-04-01 10:15' },
    ],
  },
  P004: {
    pt_id: 'P004', patient_reg_no: 'OVA-41032', patient_name: '최유나',
    birth_ym: '1974-07', diag_att_age: 52, risk_level: 'LOW', status: '검토완료', last_updated: '2026-05-22',
    labResultsByDate: [
      labSet('2026-05-22', 22, 62, 4.5, 24, 18, 0.7, 12, 14.1, 7.2, 210, 1.00),
      labSet('2026-04-10', 20, 64, 4.6, 22, 17, 0.7, 11, 14.3, 7.0, 205, 0.98),
      labSet('2026-03-05', 18, 65, 4.7, 21, 16, 0.7, 11, 14.5, 6.8, 200, 0.97),
    ],
    rmiCalculation: { ca125_value: 22, us_score: 1, m_factor: 1, rmi_score: 22, risk_level: 'LOW' },
    vitalsByDate: [
      { date: '2026-05-22', bp: '115/72', hr: 68, temp: 36.6, rr: 14, spo2: 99, recorded_at: '2026-05-22 11:00' },
      { date: '2026-04-10', bp: '114/72', hr: 67, temp: 36.5, rr: 14, spo2: 99, recorded_at: '2026-04-10 10:20' },
      { date: '2026-03-05', bp: '112/70', hr: 66, temp: 36.5, rr: 14, spo2: 99, recorded_at: '2026-03-05 09:45' },
    ],
  },
  P005: {
    pt_id: 'P005', patient_reg_no: 'OVA-29847', patient_name: '정하은',
    birth_ym: '1987-04', diag_att_age: 39, risk_level: 'LOW', status: '제외', last_updated: '2026-04-10',
    labResultsByDate: [
      labSet('2026-04-10', 18, 68, 4.8, 20, 15, 0.6, 10, 13.8, 6.8, 230, 0.98),
      labSet('2026-03-01', 16, 70, 4.9, 19, 14, 0.6, 10, 14.0, 6.5, 225, 0.97),
    ],
    rmiCalculation: { ca125_value: 18, us_score: 1, m_factor: 1, rmi_score: 18, risk_level: 'LOW' },
    vitalsByDate: [
      { date: '2026-04-10', bp: '110/70', hr: 72, temp: 36.5, rr: 15, spo2: 99, recorded_at: '2026-04-10 14:30' },
      { date: '2026-03-01', bp: '108/68', hr: 70, temp: 36.4, rr: 14, spo2: 99, recorded_at: '2026-03-01 13:50' },
    ],
  },
  P006: {
    pt_id: 'P006', patient_reg_no: 'OVA-61403', patient_name: '강민서',
    birth_ym: '1955-09', diag_att_age: 71, risk_level: 'HIGH', status: '신규', last_updated: '2026-06-07',
    labResultsByDate: [
      labSet('2026-06-07', 678, 40, 3.4, 52, 44, 1.0, 24, 11.1, 10.8, 358, 1.18),
      labSet('2026-05-02', 510, 43, 3.6, 44, 38, 0.9, 20, 11.8,  9.5, 320, 1.12),
      labSet('2026-03-25', 340, 46, 3.8, 36, 32, 0.9, 18, 12.2,  8.8, 290, 1.08),
    ],
    rmiCalculation: { ca125_value: 678, us_score: 3, m_factor: 3, rmi_score: 6102, risk_level: 'HIGH' },
    vitalsByDate: [
      { date: '2026-06-07', bp: '146/90', hr: 88, temp: 37.0, rr: 19, spo2: 95, recorded_at: '2026-06-07 08:55' },
      { date: '2026-05-02', bp: '142/88', hr: 86, temp: 36.9, rr: 18, spo2: 96, recorded_at: '2026-05-02 09:20' },
      { date: '2026-03-25', bp: '138/86', hr: 84, temp: 36.8, rr: 17, spo2: 96, recorded_at: '2026-03-25 10:00' },
    ],
  },
  P007: {
    pt_id: 'P007', patient_reg_no: 'OVA-44582', patient_name: '오서연',
    birth_ym: '1978-11', diag_att_age: 48, risk_level: 'MODERATE', status: '관찰중', last_updated: '2026-05-28',
    labResultsByDate: [
      labSet('2026-05-28', 45, 50, 4.0, 32, 28, 0.8, 16, 12.8, 7.5, 268, 1.05),
      labSet('2026-04-20', 38, 52, 4.1, 30, 25, 0.8, 15, 13.0, 7.2, 260, 1.03),
      labSet('2026-03-10', 30, 54, 4.2, 28, 23, 0.8, 14, 13.2, 7.0, 252, 1.01),
    ],
    rmiCalculation: { ca125_value: 45, us_score: 1, m_factor: 3, rmi_score: 135, risk_level: 'MODERATE' },
    vitalsByDate: [
      { date: '2026-05-28', bp: '122/78', hr: 80, temp: 36.9, rr: 16, spo2: 97, recorded_at: '2026-05-28 13:15' },
      { date: '2026-04-10', bp: '118/76', hr: 78, temp: 36.7, rr: 15, spo2: 98, recorded_at: '2026-04-10 10:30' },
      { date: '2026-02-20', bp: '120/78', hr: 76, temp: 36.6, rr: 15, spo2: 98, recorded_at: '2026-02-20 09:00' },
    ],
  },
  P008: {
    pt_id: 'P008', patient_reg_no: 'OVA-58124', patient_name: '한지은',
    birth_ym: '1963-01', diag_att_age: 63, risk_level: 'HIGH', status: '신규', last_updated: '2026-03-15',
    labResultsByDate: [
      labSet('2026-03-15', 340, 42, 3.3, 44, 36, 1.1, 23, 10.8, 9.2, 380, 1.15),
      labSet('2026-02-10', 280, 44, 3.5, 40, 32, 1.0, 20, 11.2, 8.8, 350, 1.10),
      labSet('2026-01-08', 220, 46, 3.7, 36, 28, 1.0, 18, 11.8, 8.2, 320, 1.07),
    ],
    rmiCalculation: { ca125_value: 340, us_score: 3, m_factor: 3, rmi_score: 3060, risk_level: 'HIGH' },
    vitalsByDate: [
      { date: '2026-03-15', bp: '138/86', hr: 90, temp: 37.2, rr: 18, spo2: 96, recorded_at: '2026-03-15 09:40' },
      { date: '2026-02-10', bp: '144/90', hr: 92, temp: 37.0, rr: 19, spo2: 95, recorded_at: '2026-02-10 10:15' },
      { date: '2026-01-08', bp: '140/88', hr: 88, temp: 36.9, rr: 18, spo2: 96, recorded_at: '2026-01-08 08:50' },
    ],
  },
  P009: {
    pt_id: 'P009', patient_reg_no: 'OVA-47309', patient_name: '윤미현',
    birth_ym: '1971-06', diag_att_age: 55, risk_level: 'MODERATE', status: '관찰중', last_updated: '2026-06-03',
    labResultsByDate: [
      labSet('2026-06-03', 38, 48, 4.2, 30, 25, 0.9, 18, 13.0, 8.1, 292, 1.08),
      labSet('2026-05-05', 32, 50, 4.3, 28, 23, 0.9, 16, 13.2, 7.8, 285, 1.05),
      labSet('2026-04-08', 26, 52, 4.4, 26, 21, 0.9, 15, 13.5, 7.5, 278, 1.03),
    ],
    rmiCalculation: { ca125_value: 38, us_score: 1, m_factor: 3, rmi_score: 114, risk_level: 'MODERATE' },
    vitalsByDate: [
      { date: '2026-06-03', bp: '126/80', hr: 76, temp: 36.7, rr: 16, spo2: 98, recorded_at: '2026-06-03 10:50' },
      { date: '2026-05-05', bp: '124/78', hr: 74, temp: 36.6, rr: 16, spo2: 98, recorded_at: '2026-05-05 09:30' },
      { date: '2026-04-08', bp: '122/76', hr: 72, temp: 36.5, rr: 15, spo2: 99, recorded_at: '2026-04-08 11:00' },
    ],
  },
  P010: {
    pt_id: 'P010', patient_reg_no: 'OVA-31256', patient_name: '신예린',
    birth_ym: '1992-08', diag_att_age: 34, risk_level: 'LOW', status: '검토완료', last_updated: '2026-05-18',
    labResultsByDate: [
      labSet('2026-05-18', 12, 72, 4.6, 18, 14, 0.6, 11, 14.2, 5.9, 218, 0.95),
      labSet('2026-04-15', 11, 74, 4.7, 17, 13, 0.6, 10, 14.4, 5.7, 212, 0.94),
      labSet('2026-03-12', 10, 75, 4.8, 16, 12, 0.6, 10, 14.6, 5.5, 208, 0.93),
    ],
    rmiCalculation: { ca125_value: 12, us_score: 1, m_factor: 1, rmi_score: 12, risk_level: 'LOW' },
    vitalsByDate: [
      { date: '2026-05-18', bp: '108/68', hr: 65, temp: 36.4, rr: 14, spo2: 99, recorded_at: '2026-05-18 15:20' },
      { date: '2026-04-15', bp: '110/70', hr: 66, temp: 36.5, rr: 14, spo2: 99, recorded_at: '2026-04-15 14:00' },
      { date: '2026-03-12', bp: '112/70', hr: 67, temp: 36.5, rr: 15, spo2: 99, recorded_at: '2026-03-12 10:45' },
    ],
  },
};
