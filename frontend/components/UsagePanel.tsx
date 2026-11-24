'use client';
import { useEffect, useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Integrations, Usage } from '@/lib/contracts/types';
import { StatusBanner } from './StatusBanner';
type Job = {id: string; kind: string; state: string; stats: Record<string, unknown>; started_at: string; finished_at: string | null};

export function UsagePanel({teamId}: {teamId: string}) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [integrations, setIntegrations] = useState<Integrations | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<{status: number | null; message: string} | null>(null);
  useEffect(() => {
    let active = true;
    const api = getBrowserCopilotClient();
    Promise.all([api.usage(teamId), api.integrations(teamId), api.jobs(teamId)])
      .then(([costs, connections, tasks]) => {
        if (active) { setUsage(costs); setIntegrations(connections); setJobs(tasks.items); }
      }).catch(err => { if (active) setError(formatApiError(err)); });
    return () => { active = false; };
  }, [teamId]);
  if (error) return <StatusBanner status={error.status} message={error.message} />;
  if (!usage || !integrations) return <p className="text-xs text-slate-500">正在读取用量和服务状态…</p>;
  const connections = [
    ['AI 解读', integrations.analysis_enabled ? '已启用' : integrations.analysis_key_configured ? '已配置密钥，尚未启用' : '等待配置密钥'],
    ['语义检索', integrations.semantic_search_available ? '已配置' : '未配置，关键词检索可用'],
    ['群日报', integrations.group_delivery_provider === 'none' ? '未配置机器人' : integrations.group_delivery_provider],
    ['个人日报邮件', integrations.email_digest_provider === 'none' ? '未配置发信服务' : integrations.email_digest_provider],
    ['跨论文周报', '支持按团队主题分组；生成解读后可综合分析'],
  ];
  return <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
      <h3 className="text-sm font-bold text-slate-900">服务接入状态</h3>
      {connections.map(([label, status]) => <div key={label} className="flex justify-between gap-4 text-xs">
        <span className="text-slate-600 shrink-0">{label}</span><span className="text-slate-800 text-right">{status}</span>
      </div>)}
    </section>
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
      <h3 className="text-sm font-bold text-slate-900">费用与预算</h3>
      {usage.daily_budget_cny && <p className="text-2xl font-bold text-indigo-700">¥{usage.daily_budget_cny}<span className="text-xs text-slate-500 font-normal ml-2">{usage.cost_basis === 'unpriced' ? '每日预算目标（待确认费率）' : '全项目每天上限'}</span></p>}
      <p className="text-xs text-slate-600">团队 Token 配额：{usage.team_limit.toLocaleString()}<br />全项目剩余可用额度：{usage.global_tokens_remaining.toLocaleString()} tokens</p>
      <p className="text-xs text-slate-500">{usage.cost_basis === 'unpriced' ? '当前接口费率尚未确认，无法计算金额上限。第三方接口需先确认费率才能启用。' : usage.cost_basis === 'configured_rates_upper_bound' ? '按已配置的输入、输出费率估算上界，实际账单以服务商为准。' : '费用按 Flash 高峰单价估算上界，实际账单以服务商为准。'}超时调用继续占用预留额度，未定价调用单独列出。</p>
      {usage.spending.length === 0 ? <p className="text-xs text-slate-400">暂无模型调用和费用记录。</p> : <div className="space-y-2">{usage.spending.map(day => <div key={day.day} className="rounded-xl bg-slate-50 p-3 text-xs space-y-1">
        <div className="flex justify-between"><span>{day.day}</span><strong>估算上界 ¥{Number(day.estimated_cny_upper).toFixed(4)}</strong></div>
        <p className="text-slate-500">{day.calls} 次调用 · 输入 {day.input_tokens.toLocaleString()} / 输出 {day.output_tokens.toLocaleString()} tokens</p>
        {day.unpriced_calls > 0 && <p className="text-amber-700">另有 {day.unpriced_calls} 次调用费用尚未确定</p>}
      </div>)}</div>}
    </section>
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
      <h3 className="text-sm font-bold text-slate-900">Token 账本 · {usage.llm_enabled ? 'AI 已启用' : 'AI 已关闭'}</h3>
      {usage.items.length === 0 ? <p className="text-xs text-slate-400">暂无用量记录。</p> : usage.items.map(item => <div key={item.day} className="space-y-1 text-xs">
        <div className="flex justify-between"><span>{item.day}</span><span>已用 {item.used.toLocaleString()} / 预留 {item.reserved.toLocaleString()}</span></div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-indigo-600" style={{width: `${Math.min(100, (item.used + item.reserved) / usage.team_limit * 100)}%`}} /></div>
      </div>)}
    </section>
    <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
      <h3 className="text-sm font-bold text-slate-900">后台任务</h3>
      {jobs.length === 0 ? <p className="text-xs text-slate-400">暂无执行记录。</p> : jobs.map(job => <div key={job.id} className="rounded-xl bg-slate-50 p-3 text-xs space-y-1">
        <div className="flex justify-between"><strong>{job.kind}</strong><span>{({succeeded: '已完成', failed: '失败', degraded: '部分完成', running: '执行中'} as Record<string, string>)[job.state] || job.state}</span></div>
        <p className="text-slate-500">{new Date(job.started_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai'})}</p>
        <details><summary className="text-slate-500 cursor-pointer">查看任务明细</summary><pre className="whitespace-pre-wrap break-all mt-2">{JSON.stringify(job.stats, null, 2)}</pre></details>
      </div>)}
    </section>
  </div>;
}
