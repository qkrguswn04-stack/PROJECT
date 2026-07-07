'use client';
import { useState, useEffect, useRef } from 'react';
import { Bell, Settings, X, ChevronRight, AlertTriangle, User, Lock, LogOut } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/AuthContext';
import { getPatients, changePassword, updateProfile } from '@/lib/api';

const ROLE_LABEL = { doctor: '의사', nurse: '간호사', admin: '관리자' };

export default function Header() {
  const { user, role, logout, updateUser } = useAuth();
  const router = useRouter();

  const [patients,     setPatients]     = useState([]);
  const [bellOpen,     setBellOpen]     = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [modal,        setModal]        = useState(null);

  const [profileName, setProfileName] = useState('');
  const [pwForm,      setPwForm]      = useState({ current: '', next: '', confirm: '' });
  const [submitting,  setSubmitting]  = useState(false);
  const [formStatus,  setFormStatus]  = useState(null);

  const bellRef     = useRef(null);
  const settingsRef = useRef(null);

  const highRisk   = patients.filter(p => p.riskTier === 'HIGH');
  const badgeCount = highRisk.length;

  useEffect(() => {
    getPatients(1, 300).then(({ patients }) => setPatients(patients)).catch(() => {});
  }, []);

  useEffect(() => {
    const close = (e) => {
      if (bellRef.current     && !bellRef.current.contains(e.target))     setBellOpen(false);
      if (settingsRef.current && !settingsRef.current.contains(e.target)) setSettingsOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const openModal = (type) => {
    setSettingsOpen(false);
    setFormStatus(null);
    if (type === 'profile')  setProfileName(user?.name ?? '');
    if (type === 'password') setPwForm({ current: '', next: '', confirm: '' });
    setModal(type);
  };

  const handlePasswordChange = async () => {
    if (pwForm.next !== pwForm.confirm) { setFormStatus({ type: 'err', msg: '새 비밀번호가 일치하지 않습니다.' }); return; }
    if (pwForm.next.length < 4)         { setFormStatus({ type: 'err', msg: '비밀번호는 4자 이상이어야 합니다.' }); return; }
    setSubmitting(true); setFormStatus(null);
    try {
      await changePassword(user.employee_id, pwForm.current, pwForm.next);
      setFormStatus({ type: 'ok', msg: '비밀번호가 변경됐습니다.' });
      setTimeout(() => setModal(null), 1200);
    } catch (err) {
      setFormStatus({ type: 'err', msg: err.message || '변경에 실패했습니다.' });
    } finally { setSubmitting(false); }
  };

  const handleProfileUpdate = async () => {
    if (!profileName.trim()) { setFormStatus({ type: 'err', msg: '이름을 입력해주세요.' }); return; }
    setSubmitting(true); setFormStatus(null);
    try {
      await updateProfile(user.employee_id, profileName.trim());
      updateUser({ ...user, name: profileName.trim() });
      setFormStatus({ type: 'ok', msg: '프로필이 업데이트됐습니다.' });
      setTimeout(() => setModal(null), 1200);
    } catch (err) {
      setFormStatus({ type: 'err', msg: err.message || '업데이트에 실패했습니다.' });
    } finally { setSubmitting(false); }
  };

  return (
    <>
      {/* ── 상단 바 ─────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 flex items-center justify-end gap-0.5 h-16 px-5 bg-canvas border-b border-hairline">

        {/* 사용자 정보 */}
        {user && (
          <div className="flex items-center gap-1.5 mr-2 pr-3 border-r border-hairline">
            <span className="text-sm font-medium text-ink">{user.name}</span>
            <span className="text-xs text-ink-tertiary">{ROLE_LABEL[role] ?? role}</span>
          </div>
        )}

        {/* 알림 벨 */}
        <div className="relative" ref={bellRef}>
          <button
            onClick={() => { setBellOpen(v => !v); setSettingsOpen(false); }}
            className="relative flex items-center justify-center w-8 h-8 rounded-lg hover:bg-surface-2 transition-colors text-ink-tertiary hover:text-ink-subtle"
          >
            <Bell size={15} />
            {badgeCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 bg-red-500 text-white text-[8px] font-bold rounded-full flex items-center justify-center leading-none">
                {badgeCount > 9 ? '9+' : badgeCount}
              </span>
            )}
          </button>

          {bellOpen && (
            <div className="absolute right-0 top-10 w-76 bg-surface-1 border border-hairline rounded-xl shadow-2xl z-50 overflow-hidden" style={{ width: '304px' }}>
              <div className="px-4 py-3 border-b border-hairline flex items-center justify-between">
                <div>
                  <p className="text-base font-semibold text-ink">고위험 환자 알림</p>
                  {badgeCount > 0 && <p className="text-xs text-red-600 mt-0.5">{badgeCount}명 즉각 확인 필요</p>}
                </div>
                <button onClick={() => setBellOpen(false)} className="text-ink-tertiary hover:text-ink-subtle transition-colors p-0.5">
                  <X size={13} />
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {badgeCount === 0 ? (
                  <div className="py-8 text-center text-sm text-ink-tertiary">새로운 알림이 없습니다</div>
                ) : (
                  highRisk.slice(0, 10).map(p => (
                    <Link
                      key={p.id}
                      href={`/patients/${p.id}`}
                      onClick={() => setBellOpen(false)}
                      className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2 transition-colors border-b border-hairline last:border-0"
                    >
                      <div className="w-6 h-6 rounded-full bg-red-50 flex items-center justify-center shrink-0">
                        <AlertTriangle size={11} className="text-red-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-base font-medium text-ink truncate">{p.name}</p>
                        <p className="text-xs text-ink-tertiary mt-0.5">
                          {p.id} · CA-125 {p.ca125 != null ? p.ca125.toLocaleString() : '—'} · RMI {p.rmi > 0 ? p.rmi.toLocaleString() : '—'}
                        </p>
                      </div>
                      <ChevronRight size={11} className="text-ink-tertiary shrink-0" />
                    </Link>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* 설정 */}
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => { setSettingsOpen(v => !v); setBellOpen(false); }}
            className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-surface-2 transition-colors text-ink-tertiary hover:text-ink-subtle"
          >
            <Settings size={15} />
          </button>

          {settingsOpen && (
            <div className="absolute right-0 top-10 w-44 bg-surface-1 border border-hairline rounded-xl shadow-2xl z-50 overflow-hidden py-1">
              <button
                onClick={() => openModal('profile')}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-base text-ink-subtle hover:text-ink hover:bg-surface-2 transition-colors text-left"
              >
                <User size={14} className="text-ink-tertiary" />
                프로필 수정
              </button>
              <button
                onClick={() => openModal('password')}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-base text-ink-subtle hover:text-ink hover:bg-surface-2 transition-colors text-left"
              >
                <Lock size={14} className="text-ink-tertiary" />
                비밀번호 변경
              </button>
              <div className="border-t border-hairline my-1" />
              <button
                onClick={() => { logout(); router.push('/login'); }}
                className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-base text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors text-left"
              >
                <LogOut size={14} />
                로그아웃
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── 모달 ────────────────────────────────────────────────────────── */}
      {modal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onMouseDown={e => { if (e.target === e.currentTarget) setModal(null); }}
        >
          <div className="bg-surface-1 border border-hairline rounded-xl shadow-2xl w-full max-w-sm mx-4">

            {modal === 'profile' && (
              <>
                <ModalHeader title="프로필 수정" onClose={() => setModal(null)} />
                <div className="px-5 pb-5">
                  <label className="block text-[11px] font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5">이름</label>
                  <input
                    type="text"
                    value={profileName}
                    onChange={e => setProfileName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleProfileUpdate()}
                    placeholder="이름 입력"
                    className="w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors"
                  />
                  <FormMsg status={formStatus} />
                  <button
                    onClick={handleProfileUpdate}
                    disabled={submitting}
                    className="mt-4 w-full py-2.5 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded-lg disabled:opacity-40 transition-colors"
                  >
                    {submitting ? '저장 중…' : '저장'}
                  </button>
                </div>
              </>
            )}

            {modal === 'password' && (
              <>
                <ModalHeader title="비밀번호 변경" onClose={() => setModal(null)} />
                <div className="px-5 pb-5 space-y-3">
                  {[
                    { key: 'current', label: '현재 비밀번호', ph: '현재 비밀번호' },
                    { key: 'next',    label: '새 비밀번호',   ph: '새 비밀번호 (4자 이상)' },
                    { key: 'confirm', label: '비밀번호 확인', ph: '새 비밀번호 재입력' },
                  ].map(({ key, label, ph }) => (
                    <div key={key}>
                      <label className="block text-[11px] font-medium text-ink-subtle uppercase tracking-[0.4px] mb-1.5">{label}</label>
                      <input
                        type="password"
                        value={pwForm[key]}
                        onChange={e => setPwForm(v => ({ ...v, [key]: e.target.value }))}
                        onKeyDown={e => e.key === 'Enter' && handlePasswordChange()}
                        placeholder={ph}
                        className="w-full px-3.5 py-2.5 bg-surface-2 border border-hairline rounded-lg text-sm text-ink outline-none focus:border-primary transition-colors"
                      />
                    </div>
                  ))}
                  <FormMsg status={formStatus} />
                  <button
                    onClick={handlePasswordChange}
                    disabled={submitting}
                    className="w-full py-2.5 text-sm font-medium bg-primary hover:bg-primary-hover text-white rounded-lg disabled:opacity-40 transition-colors"
                  >
                    {submitting ? '변경 중…' : '비밀번호 변경'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function ModalHeader({ title, onClose }) {
  return (
    <div className="flex items-center justify-between px-5 py-4 border-b border-hairline">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <button onClick={onClose} className="text-ink-tertiary hover:text-ink-subtle transition-colors">
        <X size={15} />
      </button>
    </div>
  );
}

function FormMsg({ status }) {
  if (!status) return null;
  return (
    <p className={`text-xs mt-2 ${status.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
      {status.msg}
    </p>
  );
}
