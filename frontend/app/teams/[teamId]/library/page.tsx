'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Search, Sparkles } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Paper, UUID } from '@/lib/contracts/types';
import { StatusBanner } from '@/components/StatusBanner';

export default function LibraryPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;

  const [mode, setMode] = useState<'keyword' | 'semantic'>('keyword');
  const [query, setQuery] = useState('');
  const [limit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [semanticItems, setSemanticItems] = useState<{ paper: Paper; analysis_id: UUID; summary: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  const runKeywordSearch = useCallback(async (qVal: string, offVal: number) => {
    setLoading(true);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      const res = await api.papers(teamId, qVal, limit, offVal);
      setPapers(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [teamId, limit]);

  async function runSemanticSearch(qVal: string) {
    if (!qVal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      const res = await api.search(teamId, qVal.trim());
      setSemanticItems(res.items);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (mode === 'keyword') {
      runKeywordSearch(query, offset);
    }
  }, [mode, offset, runKeywordSearch]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    if (mode === 'keyword') runKeywordSearch(query, 0);
    else runSemanticSearch(query);
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-lg font-bold text-slate-900">团队论文知识库</h1>
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs">
            <button
              type="button"
              onClick={() => { setMode('keyword'); setError(null); }}
              className={`px-3 py-1.5 rounded-lg font-medium ${mode === 'keyword' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'}`}
            >
              关键词分页检索
            </button>
            <button
              type="button"
              onClick={() => { setMode('semantic'); setError(null); }}
              className={`px-3 py-1.5 rounded-lg font-medium inline-flex items-center gap-1 ${mode === 'semantic' ? 'bg-white text-violet-700 shadow-sm' : 'text-slate-600'}`}
            >
              <Sparkles className="w-3.5 h-3.5" />语义检索
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={mode === 'keyword' ? '按标题或摘要关键词检索...' : '输入自然语言研究问题进行语义检索...'}
              className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <button type="submit" className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold">
            搜索
          </button>
        </form>
      </div>

      {error && (
        <StatusBanner
          status={error.status}
          message={error.message}
          loginReturnTo={pathname}
          onFallbackKeyword={
            error.status === 503
              ? () => {
                  setMode('keyword');
                  setError(null);
                  runKeywordSearch(query, 0);
                }
              : undefined
          }
        />
      )}

      {loading ? (
        <div className="text-center text-sm text-slate-500 py-8">检索中...</div>
      ) : mode === 'keyword' ? (
        <div className="space-y-3">
          {papers.map((p) => (
            <div key={p.id} className="bg-white rounded-2xl border border-slate-200 p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                {p.arxiv_id && <span>arXiv:{p.arxiv_id}</span>}
                {p.first_submitted_at && <span>· {p.first_submitted_at.slice(0, 10)}</span>}
              </div>
              <Link href={`/teams/${teamId}/papers/${p.id}`} className="text-sm font-bold text-slate-900 hover:text-indigo-600 block">
                {p.title}
              </Link>
              <p className="text-xs text-slate-600 line-clamp-2">{p.abstract}</p>
            </div>
          ))}
          <div className="flex items-center justify-between text-xs text-slate-500 pt-2">
            <span>共 {total} 篇</span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="px-3 py-1 rounded-lg bg-white border border-slate-200 disabled:opacity-40"
              >
                上一页
              </button>
              <button
                type="button"
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
                className="px-3 py-1 rounded-lg bg-white border border-slate-200 disabled:opacity-40"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {semanticItems.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-6">输入研究问题并点击搜索以查看语义匹配结果。</p>
          ) : (
            semanticItems.map((item) => (
              <div key={item.analysis_id} className="bg-white rounded-2xl border border-slate-200 p-4 space-y-1.5">
                <Link href={`/teams/${teamId}/papers/${item.paper.id}`} className="text-sm font-bold text-slate-900 hover:text-indigo-600 block">
                  {item.paper.title}
                </Link>
                <p className="text-xs text-slate-700">{item.summary}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
