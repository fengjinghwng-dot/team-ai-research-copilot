'use client';

import { useEffect, useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { DailyPreferences, DailyPreferencesResponse, PersonalDailyJob } from '@/lib/contracts/types';
import { StatusBanner } from './StatusBanner';

export function PersonalDailyControls({teamId, mode, onGenerated}: {
  teamId: string; mode: 'settings' | 'generate'; onGenerated?: (day: string) => void;
}) {
  const [keywords, setKeywords] = useState('');
  const [count, setCount] = useState(20);
  const [ratio, setRatio] = useState(.3);
  const [sourceInfo, setSourceInfo] = useState<DailyPreferencesResponse | null>(null);
  const [job, setJob] = useState<PersonalDailyJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState<{status: number | null; message: string} | null>(null);
  const activeJob = job?.state === 'queued' || job?.state === 'running';
  const prefix = mode === 'settings' ? 'preferences' : 'generate';

  useEffect(() => {
    let active = true;
    const api = getBrowserCopilotClient();
    Promise.all([api.dailyPreferences(teamId),
      mode === 'generate' ? api.latestDailyGeneration(teamId) : Promise.resolve({job: null})])
      .then(([preferences, status]) => {
        if (!active) return;
        setKeywords(preferences.keywords.join('，'));
        setCount(preferences.paper_count);
        setRatio(preferences.conference_ratio);
        setSourceInfo(preferences);
        setJob(status.job);
      }).catch(err => {if (active) setError(formatApiError(err));});
    return () => {active = false;};
  }, [teamId, mode]);

  useEffect(() => {
    if (!job || !activeJob) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const id = job.id;
    async function poll() {
      try {
        const updated = await getBrowserCopilotClient().dailyGeneration(teamId, id);
        if (!active) return;
        setJob(updated);
        setError(null);
        if (updated.state === 'succeeded' || updated.state === 'degraded') {
          setNotice(updated.state === 'degraded' ? '个人日报已生成，请查看实际篇数及来源提示。' : '个人日报已生成。');
          onGenerated?.(updated.day);
        } else if (updated.state === 'failed') {
          setNotice(updated.error || '生成失败，请稍后重试。');
        } else {
          timer = setTimeout(poll, 2000);
        }
      } catch (err) {
        if (active) {setError(formatApiError(err)); timer = setTimeout(poll, 5000);}
      }
    }
    timer = setTimeout(poll, 1000);
    return () => {active = false; clearTimeout(timer);};
  }, [teamId, job?.id, activeJob, onGenerated]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const input: DailyPreferences = {
      keywords: [...new Set(keywords.split(/[,，;；\n]+/).map(word => word.trim()).filter(Boolean))],
      paper_count: count, conference_ratio: ratio,
    };
    setBusy(true);
    setError(null);
    setNotice('');
    try {
      const api = getBrowserCopilotClient();
      if (mode === 'settings') {
        await api.saveDailyPreferences(teamId, input);
        setNotice('日报偏好已保存，立即生成和下一轮定时日报都会使用这些设置。');
      } else {
        setJob(await api.generateDaily(teamId, input));
        setNotice('已保存方向与篇数并加入生成队列，可在此查看进度。');
      }
    } catch (err) {setError(formatApiError(err));}
    finally {setBusy(false);}
  }

  return <form onSubmit={submit} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
    <div>
      <h2 className="text-sm font-bold text-slate-900">{mode === 'settings' ? '个人日报偏好' : '按方向生成个人日报'}</h2>
      <p className="text-xs text-slate-500 mt-1">{mode === 'settings'
        ? '为当前团队设置自己的选文方向、每日篇数和来源比例。'
        : '保存当前方向与篇数，立即检索并生成今日日报。完成后自动刷新，无需等待定时任务。'}</p>
    </div>
    {error && <StatusBanner status={error.status} message={error.message} />}
    <div>
      <label htmlFor={prefix + '-keywords'} className="block text-xs font-medium text-slate-700 mb-1">方向关键词</label>
      <textarea id={prefix + '-keywords'} required rows={2} value={keywords}
        disabled={busy || activeJob || !sourceInfo} onChange={event => setKeywords(event.target.value)}
        placeholder="例如：RAG，LLM Agent，模型评测（可输入中英文，用逗号分隔）"
        className="w-full rounded-xl border border-slate-200 p-3 text-sm" />
      <p className="text-xs text-slate-500 mt-1">支持 1–12 个关键词，每个最多 80 字；按任一方向匹配。常见中文 AI 术语会扩展英文别名，也可直接填写英文或缩写。</p>
    </div>
    <div className="grid sm:grid-cols-2 gap-4">
      <div>
        <label htmlFor={prefix + '-count'} className="block text-xs font-medium text-slate-700 mb-1">每日论文篇数</label>
        <input id={prefix + '-count'} required type="number" min={1} max={50} step={1} value={count}
          disabled={busy || activeJob || !sourceInfo} onChange={event => setCount(Number(event.target.value))}
          className="w-full rounded-xl border border-slate-200 p-2 text-sm" />
        <p className="text-xs text-slate-500 mt-1">1–50 篇；符合条件的论文不足时显示实际篇数。</p>
      </div>
      <div>
        <label htmlFor={prefix + '-ratio'} className="block text-xs font-medium text-slate-700 mb-2">
          来源比例：顶会 {Math.round(ratio * 100)}% / 最新 {Math.round((1 - ratio) * 100)}%
        </label>
        <input id={prefix + '-ratio'} aria-label="顶会论文比例" type="range" min={0} max={1} step={.05}
          value={ratio} disabled={busy || activeJob || !sourceInfo}
          onChange={event => setRatio(Number(event.target.value))} className="w-full accent-indigo-600" />
      </div>
    </div>
    {sourceInfo && <details className="text-xs text-slate-500">
      <summary className="cursor-pointer">选文范围与比例说明</summary>
      <p className="mt-2">顶会范围：{sourceInfo.conference_venues.join('、')}，近 {sourceInfo.conference_years} 年，
        依据来源会议元数据识别主会论文。最新论文为最近 {sourceInfo.latest_hours} 小时首次提交的 arXiv 论文。
        顶会论文优先归入顶会类别，每篇只计一次；单类不足时由另一类补齐，并展示实际比例。
        模型预算不足时保留摘要和已有解读。</p>
    </details>}
    {activeJob && <p role="status" className="text-xs text-indigo-700">{job?.state === 'queued' ? '排队中…' : '正在检索与生成个人日报…'}</p>}
    {notice && <p role="status" className="text-xs text-indigo-700">{notice}</p>}
    <button type="submit" disabled={busy || activeJob || !sourceInfo}
      className="rounded-xl bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">
      {busy ? '提交中…' : activeJob ? '生成中…' : mode === 'settings' ? '保存日报偏好' : '立即生成日报'}
    </button>
  </form>;
}
