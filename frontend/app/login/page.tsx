'use client';

import { Suspense, useEffect, useState, type FormEvent } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Sparkles } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { sanitizeReturnTo } from '@/lib/evidence';
import { isMockEnabled } from '@/lib/mock';

function LoginInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const returnTo = sanitizeReturnTo(searchParams.get('returnTo'), '/teams');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(searchParams.get('error'));
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [mode, setMode] = useState<'password' | 'email'>('password');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (isMockEnabled()) return;
    let active = true;
    async function restoreSession() {
      try {
        const {data} = await createClient().auth.getUser();
        if (active && data.user) router.replace(returnTo);
      } catch { /* Leave the login form available if configuration or the Auth network is unavailable. */ }
    }
    void restoreSession();
    return () => { active = false; };
  }, [router, returnTo]);

  async function handlePasswordLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setError(null);
    try {
      const {error: authError} = await createClient().auth.signInWithPassword({email: email.trim(), password});
      if (authError) {
        setError(authError.code === 'email_not_confirmed' ? '请先使用邮件登录完成邮箱验证。' :
          '邮箱或密码不正确。尚未设置密码时，请切换到邮件登录。');
      } else {
        setPassword(''); router.replace(returnTo); router.refresh();
      }
    } catch { setError('登录暂时失败，请稍后重试。'); }
    finally { setLoading(false); }
  }

  async function handleEmailLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isMockEnabled()) { router.push(returnTo); return; }
    setLoading(true);
    setError(null);
    setSent(false);
    try {
      const supabase = createClient();
      const callbackUrl = `${window.location.origin}/auth/callback?returnTo=${encodeURIComponent(returnTo)}`;
      const { error: authError } = await supabase.auth.signInWithOtp({
        email: email.trim(), options: { emailRedirectTo: callbackUrl },
      });
      if (authError) setError(authError.message);
      else setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录邮件发送失败，请稍后重试');
    } finally { setLoading(false); }
  }

  async function handleGoogleLogin() {
    if (isMockEnabled()) {
      router.push(returnTo);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const callbackUrl = `${window.location.origin}/auth/callback?returnTo=${encodeURIComponent(returnTo)}`;
      const { error: authError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: callbackUrl },
      });
      if (authError) setError(authError.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录初始化失败，请检查环境变量配置');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 p-8 shadow-sm space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">Team AI Research Copilot</h1>
            <p className="text-xs text-slate-500">团队论文追踪 · 批判性分析 · 组会协作</p>
          </div>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">
          使用邮箱和工作台密码登录。首次使用或尚未设置密码时，可先用邮件登录，再到个人设置里设置密码。
        </p>

        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
            {error}
          </div>
        )}

        {sent && (
          <div role="status" className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
            登录邮件已发送至 {email.trim()}。点击最新邮件中的“确认并登录”，也可以检查垃圾邮件文件夹。
          </div>
        )}
        {!isMockEnabled() && (
          <form onSubmit={mode === 'password' ? handlePasswordLogin : handleEmailLogin} className="space-y-3">
            <div className="flex rounded-xl bg-slate-100 p-1 gap-1 text-sm">
              {(['password', 'email'] as const).map(value => <button key={value} type="button" disabled={loading}
                aria-pressed={mode === value} onClick={() => {setMode(value); setError(null); setSent(false); setPassword('');}}
                className={`flex-1 rounded-lg py-2 ${mode === value ? 'bg-white shadow-sm text-indigo-700' : 'text-slate-600'}`}>
                {value === 'password' ? '密码登录' : '邮件登录 / 首次注册'}
              </button>)}
            </div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">邮箱地址</label>
            <input id="email" type="email" autoComplete="username" required value={email}
              onChange={(event) => { setEmail(event.target.value); setSent(false); }}
              placeholder="name@school.edu.cn" disabled={loading}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500" />
            {mode === 'password' && <>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700">工作台密码</label>
              <input id="password" type="password" autoComplete="current-password" required value={password}
                onChange={event => setPassword(event.target.value)} disabled={loading}
                className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500" />
            </>}
            <button type="submit" disabled={loading || sent}
              className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold transition disabled:opacity-50">
              {loading ? '请稍候...' : mode === 'password' ? '登录工作台' : sent ? '请查收登录邮件' : '发送登录链接'}
            </button>
            {mode === 'password' && <button type="button" onClick={() => {setMode('email'); setError(null); setPassword('');}}
              className="text-xs text-indigo-600 hover:underline">忘记密码或还没设置？用邮件登录</button>}
          </form>
        )}
        {(isMockEnabled() || process.env.NEXT_PUBLIC_ENABLE_GOOGLE_AUTH === 'true') && <button
          type="button"
          disabled={loading}
          onClick={handleGoogleLogin}
          className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold transition disabled:opacity-50"
        >
          {isMockEnabled() ? '进入独立 Mock 演示模式' : loading ? '正在跳转到 Google...' : '使用 Google 账号登录'}
        </button>}
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-sm text-slate-500">加载中...</div>}>
      <LoginInner />
    </Suspense>
  );
}
