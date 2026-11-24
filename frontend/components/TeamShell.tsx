'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getBrowserCopilotClient } from '@/lib/api';
import { usePathname, useRouter } from 'next/navigation';
import {
  Newspaper, Library, Lightbulb, CalendarDays, Settings, Shield, LogOut, Sparkles, ArrowLeftRight
} from 'lucide-react';
import type { Role, UUID } from '@/lib/contracts/types';
import { createClient } from '@/lib/supabase/client';
import { getMockRole, isMockEnabled, setMockRole } from '@/lib/mock';

interface Props {
  teamId: UUID;
  teamName: string;
  role: Role;
  children: React.ReactNode;
}

export function TeamShell({ teamId, teamName, role, children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const mockMode = isMockEnabled();
  const [pending, setPending] = useState(0);
  useEffect(() => {
    if (role !== 'admin') {setPending(0); return;}
    let active = true;
    const refresh = async () => {
      if (document.hidden) return;
      try {const result = await getBrowserCopilotClient().joinRequests(teamId); if (active) setPending(result.pending_count);}
      catch { /* The admin inbox displays errors; keep navigation usable. */ }
    };
    refresh();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    window.addEventListener('copilot:membership-reviewed', refresh);
    return () => {active = false; window.clearInterval(timer); window.removeEventListener('focus', refresh); window.removeEventListener('copilot:membership-reviewed', refresh);};
  }, [teamId, role]);

  const navItems = [
    { href: `/teams/${teamId}`, label: '今日日报', icon: Newspaper, exact: true },
    { href: `/teams/${teamId}/library`, label: '团队知识库', icon: Library },
    { href: `/teams/${teamId}/ideas`, label: '灵感池', icon: Lightbulb },
    { href: `/teams/${teamId}/meetings`, label: '周会与趋势', icon: CalendarDays },
    { href: `/teams/${teamId}/settings`, label: '个人设置', icon: Settings },
    ...(role === 'admin' ? [{ href: `/teams/${teamId}/admin`, label: '管理后台', icon: Shield }] : []),
  ];

  async function handleSignOut() {
    if (!mockMode) {
      const supabase = createClient();
      await supabase.auth.signOut();
    }
    router.push('/login');
  }

  function handleToggleMockRole() {
    const next: Role = getMockRole() === 'admin' ? 'member' : 'admin';
    setMockRole(next);
    window.location.reload();
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {mockMode && (
        <div className="bg-amber-500 text-white text-xs px-4 py-1.5 flex flex-wrap items-center justify-between gap-2">
          <span>当前处于独立 Mock 演示模式（未连接真实后端 API，上线前请将 NEXT_PUBLIC_USE_MOCK 设为 false）。</span>
          <button
            type="button"
            onClick={handleToggleMockRole}
            className="px-2.5 py-0.5 rounded bg-white/20 hover:bg-white/30 font-semibold"
          >
            切换演示角色（当前：{role}）
          </button>
        </div>
      )}

      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Link href={`/teams/${teamId}`} className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-bold text-slate-900 truncate">{teamName}</div>
                <div className="text-[11px] text-slate-500">AI Research Copilot</div>
              </div>
            </Link>
            <Link href="/teams" className="hidden sm:inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600 px-2 py-1 rounded-lg bg-slate-100">
              <ArrowLeftRight className="w-3 h-3" />切换团队
            </Link>
          </div>

          <nav className="hidden md:flex items-center gap-1 bg-slate-100 p-1 rounded-xl">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition ${
                    active ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />{item.label}
                  {item.label === '管理后台' && pending > 0 && <span aria-label={`${pending} 条入组申请`} className="rounded-full bg-rose-100 text-rose-700 px-1.5">{pending}</span>}
                </Link>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={handleSignOut}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 inline-flex items-center gap-1.5"
          >
            <LogOut className="w-3.5 h-3.5" />退出
          </button>
        </div>

        {/* Mobile horizontal nav */}
        <div className="md:hidden border-t border-slate-100 px-3 py-2 flex items-center gap-1 overflow-x-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium inline-flex items-center gap-1 shrink-0 ${
                  active ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />{item.label}
                {item.label === '管理后台' && pending > 0 && <span aria-label={`${pending} 条入组申请`} className="rounded-full bg-rose-100 text-rose-700 px-1.5">{pending}</span>}
              </Link>
            );
          })}
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {children}
      </main>
    </div>
  );
}
