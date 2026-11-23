'use client';

import { Suspense, useState, type FormEvent } from 'react';
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
          使用邮箱接收登录链接，支持 163、学校邮箱和 Gmail。首次登录会建立个人档案，团队访问权限由管理员分配。
        </p>

        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
            {error}
          </div>
        )}

        {sent && (
          <div role="status" className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-sm text-emerald-800">
            登录邮件已发送至 {email.trim()}。请在当前浏览器打开邮件中的链接，也可以检查垃圾邮件文件夹。
          </div>
        )}
        {!isMockEnabled() && (
          <form onSubmit={handleEmailLogin} className="space-y-3">
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">邮箱地址</label>
            <input id="email" type="email" autoComplete="email" required value={email}
              onChange={(event) => { setEmail(event.target.value); setSent(false); }}
              placeholder="name@school.edu.cn" disabled={loading}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500" />
            <button type="submit" disabled={loading || sent}
              className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold transition disabled:opacity-50">
              {loading ? '正在发送...' : sent ? '请查收登录邮件' : '发送登录链接'}
            </button>
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
