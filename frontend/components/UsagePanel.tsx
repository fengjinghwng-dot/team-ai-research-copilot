'use client';

import { useEffect, useState } from 'react';
import { Activity, Cpu } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { UUID } from '@/lib/contracts/types';
import { StatusBanner } from './StatusBanner';

interface Props {
  teamId: UUID;
}

export function UsagePanel({ teamId }: Props) {
  const [usage, setUsage] = useState<{
    items: { scope: string; day: string; used: number; reserved: number }[];
    team_limit: number;
    llm_enabled: boolean;
  } | null>(null);
  const [jobs, setJobs] = useState<{
    id: string;
    kind: string;
    state: string;
    stats: Record<string, unknown>;
    started_at: string;
    finished_at: string | null;
  }[]>([]);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const [u, j] = await Promise.all([api.usage(teamId), api.jobs(teamId)]);
        if (!active) return;
        setUsage(u);
        setJobs(j.items);
      } catch (err) {
        if (active) setError(formatApiError(err));
      }
    }
    load();
    return () => { active = false; };
  }, [teamId]);

  if (error) return <StatusBanner status={error.status} message={error.message} />;
  if (!usage) return <div className="text-xs text-slate-500">正在加载预算与任务状态...</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 inline-flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-600" />Token 预算账本
          </h3>
          <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${usage.llm_enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
            LLM {usage.llm_enabled ? '已启用' : '已关闭'}
          </span>
        </div>
        <p className="text-xs text-slate-500">每日团队配额上限：<strong className="text-slate-900 font-mono">{usage.team_limit.toLocaleString()}</strong> tokens</p>
        <div className="space-y-2.5">
          {usage.items.length === 0 ? (
            <p className="text-xs text-slate-400">暂无用量记录。</p>
          ) : (
            usage.items.map((item, idx) => {
              const pct = usage.team_limit > 0 ? Math.min(100, Math.round(((item.used + item.reserved) / usage.team_limit) * 100)) : 0;
              return (
                <div key={`${item.scope}-${item.day}-${idx}`} className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="font-mono text-slate-700">{item.day} · {item.scope}</span>
                    <span className="font-mono text-slate-600">已用 {item.used.toLocaleString()} / 预留 {item.reserved.toLocaleString()}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-600 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <h3 className="text-sm font-bold text-slate-900 inline-flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-600" />后台定时任务状态
        </h3>
        {jobs.length === 0 ? (
          <p className="text-xs text-slate-400">暂无任务执行记录。</p>
        ) : (
          <div className="space-y-2.5">
            {jobs.map((job) => (
              <div key={job.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">{job.kind}</span>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                    job.state === 'succeeded' ? 'bg-emerald-100 text-emerald-800' :
                    job.state === 'failed' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
                  }`}>{job.state}</span>
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  开始：{job.started_at.slice(0, 19).replace('T', ' ')}
                  {job.finished_at ? ` · 结束：${job.finished_at.slice(0, 19).replace('T', ' ')}` : ' · 运行中'}
                </div>
                <pre className="text-[11px] text-slate-600 bg-white p-2 rounded border border-slate-200/60 overflow-x-auto">
                  {JSON.stringify(job.stats)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
