'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Download, TrendingUp } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { UUID } from '@/lib/contracts/types';
import { StatusBanner } from '@/components/StatusBanner';
import { teamDate } from '@/lib/date';

interface WeeklyItem {
  team_id: UUID;
  week: string;
  payload: {
    reading_list_markdown: string;
    state: string;
    hypotheses_verified: false;
    grouping_method?: 'vector' | 'team_topics';
    trends: {
      bottleneck: string;
      paper_ids: UUID[];
      hypothesis: string;
      experiment: string;
      metric: string;
      falsification: string;
    }[];
  };
}

export default function MeetingsPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;

  const [markdown, setMarkdown] = useState('');
  const [weeklyItems, setWeeklyItems] = useState<WeeklyItem[]>([]);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const [md, wk] = await Promise.all([api.readingList(teamId), api.weekly(teamId)]);
        if (!active) return;
        setMarkdown(md);
        setWeeklyItems(wk.items);
      } catch (err) {
        if (active) setError(formatApiError(err));
      }
    }
    load();
    return () => { active = false; };
  }, [teamId]);

  function handleDownload() {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `team-reading-list-${teamDate()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {error && <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />}

      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold text-slate-900">周会阅读材料（Markdown）</h1>
            <p className="text-xs text-slate-500">以纯文本安全展示，可直接下载发至群聊或组会文档</p>
          </div>
          <button
            type="button"
            disabled={!markdown}
            onClick={handleDownload}
            className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold inline-flex items-center gap-1.5 disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" />下载 Markdown
          </button>
        </div>
        <pre className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 whitespace-pre-wrap overflow-x-auto font-mono">
          {markdown || '暂无本周阅读清单。'}
        </pre>
      </div>

      <div className="space-y-4">
        <h2 className="text-base font-bold text-slate-900 inline-flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-violet-600" />跨论文趋势与共性瓶颈
        </h2>
        {weeklyItems.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 text-xs text-slate-500">暂无周度趋势分析。</div>
        ) : (
          weeklyItems.map((wk) => (
            <div key={wk.week} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-slate-900">周期：{wk.week}</span>
                <span className="text-[11px] px-2 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200">
                  所有跨论文假设均未验证（hypotheses_verified: false）
                </span>
              </div>
              <div className="space-y-3">
                <p className="text-xs text-slate-500">{wk.payload.grouping_method === 'vector' ? '根据论文向量聚类' : '根据团队研究主题分组'}；结论均需人工核实。</p>
                {wk.payload.trends.length === 0 && <p className="text-xs text-slate-500">尚无足够的已解读论文可生成趋势。组会清单仍可下载。</p>}
                {wk.payload.trends.map((t, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 text-xs space-y-1.5">
                    <div className="font-bold text-slate-900">共性瓶颈：{t.bottleneck}</div>
                    <p className="text-slate-700"><strong>待验证假设：</strong>{t.hypothesis}</p>
                    <p className="text-slate-700"><strong>实验方案：</strong>{t.experiment}</p>
                    <p className="text-slate-700"><strong>指标：</strong>{t.metric} · <strong>证伪条件：</strong>{t.falsification}</p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {t.paper_ids.map((pid) => (
                        <Link key={pid} href={`/teams/${teamId}/papers/${pid}`} className="font-mono text-indigo-600 hover:underline">
                          论文 {pid.slice(0, 8)}
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
