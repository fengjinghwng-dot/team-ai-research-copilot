'use client';

import { useState, type FormEvent } from 'react';
import { createClient } from '@/lib/supabase/client';
import { isMockEnabled } from '@/lib/mock';

export function PasswordSettings({compact = false}: {compact?: boolean}) {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [success, setSuccess] = useState(false);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setNotice(''); setSuccess(false);
    if (password.length < 8) {setNotice('密码至少需要 8 个字符。'); return;}
    if (password !== confirmation) {setNotice('两次输入的密码不一致。'); return;}
    if (isMockEnabled()) {setNotice('演示模式不会修改真实账号密码。'); return;}
    setBusy(true);
    try {
      const {error} = await createClient().auth.updateUser({password});
      if (error) {
        setNotice(error.code === 'reauthentication_needed' ? '请用邮件重新登录，再设置密码。' :
          error.code === 'same_password' ? '新密码与当前密码相同。' : '密码未能保存，请检查密码要求或重新登录后再试。');
      } else {
        setPassword(''); setConfirmation(''); setSuccess(true);
        setNotice('密码已保存。下次可以直接使用邮箱和密码登录，无需再点邮件。');
      }
    } catch {setNotice('密码保存暂时失败，请稍后重试。');}
    finally {setBusy(false);}
  }
  return <details open={!compact} className="bg-white rounded-2xl border border-slate-200 p-6">
    <summary className="text-sm font-bold text-slate-900 cursor-pointer">设置或修改登录密码</summary>
    <p className="mt-3 text-xs text-slate-500">为本工作台单独设置至少 8 个字符的密码。设置后可直接用邮箱和密码登录，邮件登录仍可备用。</p>
    <form onSubmit={save} className="mt-4 space-y-3">
      <label htmlFor="new-password" className="block text-xs font-medium text-slate-700">新密码</label>
      <input id="new-password" type="password" autoComplete="new-password" minLength={8} required disabled={busy}
        value={password} onChange={event => setPassword(event.target.value)}
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      <label htmlFor="confirm-password" className="block text-xs font-medium text-slate-700">再次输入新密码</label>
      <input id="confirm-password" type="password" autoComplete="new-password" minLength={8} required disabled={busy}
        value={confirmation} onChange={event => setConfirmation(event.target.value)}
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
      <button disabled={busy} className="rounded-xl bg-indigo-600 text-white px-4 py-2 text-xs font-semibold disabled:opacity-50">
        {busy ? '保存中...' : '保存登录密码'}
      </button>
      {notice && <p role="status" className={`text-xs ${success ? 'text-emerald-700' : 'text-slate-600'}`}>{notice}</p>}
    </form>
  </details>;
}
