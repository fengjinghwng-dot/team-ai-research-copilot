'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Calendar, Compass, Flame, Clock, AlertTriangle, ExternalLink } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { DailyDigest, FeedItem } from '@/lib/contracts/types';
import { sanitizeExternalUrl } from '@/lib/evidence';
import { StatusBanner } from '@/components/StatusBanner';
import { teamDate } from '@/lib/date';

export default function TeamDailyPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;
  const [day, setDay] = useState(() => teamDate());
  const [digest, setDigest] = useState<DailyDigest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const data = await api.daily(teamId, day);
        if (active) setDigest(data);
      } catch (err) {
        if (active) setError(formatApiError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [teamId, day]);

  const personalTotal = digest?.personal.items.length ?? 0;
  const exploreActual = digest?.personal.exploration_actual ?? 0;
  const actualExplorePct = personalTotal > 0 ? Math.round((exploreActual / personalTotal) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white rounded-2xl border border-slate-200 p-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900">每日论文日报</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {digest?.generated_at ? `生成时间：${digest.generated_at.slice(0, 19).replace('T', ' ')} UTC` : '按日期切换查看团队必看与个人推荐'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-slate-400" />
          <input
            type="date"
            value={day}
            onChange={(e) => setDay(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {error && <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />}

      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-sm text-slate-500">
          正在加载 {day} 日报...
        </div>
      ) : digest && !digest.persisted && digest.team_must_read.length === 0 && digest.personal.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-amber-200 p-10 text-center space-y-2">
          <Clock className="w-8 h-8 text-amber-500 mx-auto" />
          <h2 className="text-base font-bold text-slate-900">该日期日报尚未生成</h2>
          <p className="text-xs text-slate-600">
            {digest.message || '后台定时流水线尚未生成当日日报，请稍后刷新或切换至前一日查看（前端不会在浏览器端触发 LLM 分析）。'}
          </p>
        </div>
      ) : digest ? (
        <div className="space-y-8">
          {/* Team Must Read */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-indigo-600" />
              <h2 className="text-base font-bold text-slate-900">团队必看（{digest.team_must_read.length}）</h2>
            </div>
            {digest.team_must_read.length === 0 ? (
              <p className="text-xs text-slate-500 bg-white rounded-xl border border-slate-200 p-4">今日暂无团队必看推荐。</p>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {digest.team_must_read.map((item) => (
                  <FeedCard key={item.paper_id} teamId={teamId} item={item} />
                ))}
              </div>
            )}
          </section>

          {/* Personal Recommendations */}
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-violet-600" />
                <h2 className="text-base font-bold text-slate-900">个人推荐（{personalTotal}）</h2>
              </div>
              <span className="text-xs text-slate-500">
                今日探索位实际占比：<strong>{exploreActual}/{personalTotal}（{actualExplorePct}%）</strong>
                （目标 {Math.round(digest.personal.exploration_target * 100)}%）
              </span>
            </div>
            {digest.personal.items.length === 0 ? (
              <p className="text-xs text-slate-500 bg-white rounded-xl border border-slate-200 p-4">今日暂无个人推荐论文。</p>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {digest.personal.items.map((item) => (
                  <FeedCard key={item.paper_id} teamId={teamId} item={item} />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function FeedCard({ teamId, item }: { teamId: string; item: FeedItem }) {
  const safeUrl = sanitizeExternalUrl(item.source_url);

  return (
    <article className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:border-indigo-200 transition space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5 flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            {item.analysis_state === 'metadata_only' ? (
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-200 text-slate-700">尚无 AI 解读</span>
            ) : (
              <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${item.analysis_tier === 'deep' ? 'bg-indigo-600 text-white' : 'bg-sky-100 text-sky-800'}`}>
                {item.analysis_tier === 'deep' ? '深度解读' : '中等解读'}
              </span>
            )}
            {item.is_exploration && (
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-50 text-violet-700 border border-violet-200">
                探索位
              </span>
            )}
            {item.analysis_stale && (
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200 inline-flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />旧版本报告
              </span>
            )}
            {item.arxiv_id && <span className="text-[11px] font-mono text-slate-400">arXiv:{item.arxiv_id}</span>}
            {item.first_submitted_at && <span className="text-[11px] text-slate-400">· {item.first_submitted_at.slice(0, 10)}</span>}
          </div>

          <h3 className="text-base font-bold text-slate-900 leading-snug">
            <Link href={`/teams/${teamId}/papers/${item.paper_id}`} className="hover:text-indigo-600 transition">
              {item.title}
            </Link>
          </h3>

          <p className="text-sm text-slate-700 leading-relaxed">
            {item.analysis_state === 'metadata_only' ? item.abstract : (item.summary || item.abstract)}
          </p>
          <p className="text-xs text-slate-500">推荐理由：{item.reason}</p>
        </div>

        <div className="text-right shrink-0 sm:pl-4 sm:border-l border-slate-100">
          <div className="text-2xl font-bold text-indigo-600">{item.score.toFixed(1)}</div>
          <div className="text-[11px] text-slate-400">综合分</div>
          <div className="text-[11px] text-slate-500 mt-1">票数 {item.votes} · 认领 {item.claims}</div>
        </div>
      </div>

      <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/teams/${teamId}/papers/${item.paper_id}`}
          className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition"
        >
          进入论文详情与讨论
        </Link>
        {safeUrl && (
          <a
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-500 hover:text-indigo-600 inline-flex items-center gap-1"
          >
            查看原文 <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </article>
  );
}
