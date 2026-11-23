'use client';

import { useState } from 'react';
import { MessageSquarePlus, Reply, Lightbulb } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Annotation, UUID } from '@/lib/contracts/types';

interface Props {
  teamId: UUID;
  paperId: UUID;
  annotations: Annotation[];
  memberNames: Record<UUID, string>;
  onUpdated: () => Promise<void>;
  onPromoteToIdea: (prefill: { title: string; hypothesis: string; experiment: string; annotationId: UUID }) => void;
}

export function AnnotationThread({ teamId, paperId, annotations, memberNames, onUpdated, onPromoteToIdea }: Props) {
  const [body, setBody] = useState('');
  const [anchor, setAnchor] = useState('');
  const [replyTo, setReplyTo] = useState<UUID | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roots = annotations.filter((a) => !a.parent_id);
  const childrenMap = annotations.reduce<Record<UUID, Annotation[]>>((acc, item) => {
    if (item.parent_id) {
      acc[item.parent_id] = [...(acc[item.parent_id] || []), item];
    }
    return acc;
  }, {});

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.annotate(teamId, paperId, {
        body: body.trim(),
        ...(replyTo ? { parent_id: replyTo } : {}),
        ...(anchor.trim() ? { anchor: anchor.trim() } : {}),
      });
      setBody('');
      setAnchor('');
      setReplyTo(null);
      await onUpdated();
    } catch (err) {
      setError(formatApiError(err).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-2.5 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
        {replyTo && (
          <div className="flex items-center justify-between text-xs text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded">
            <span>正在回复批注 #{replyTo.slice(0, 6)}</span>
            <button type="button" onClick={() => setReplyTo(null)} className="underline">取消回复</button>
          </div>
        )}
        <input
          type="text"
          value={anchor}
          onChange={(e) => setAnchor(e.target.value)}
          placeholder="引用定位锚点（可选，如 Section 4.2 / Eq. 3）"
          className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <textarea
          rows={3}
          required
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="输入团队批注或讨论内容（纯文本安全渲染）..."
          className="w-full px-3 py-2 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
        >
          <MessageSquarePlus className="w-3.5 h-3.5" />发布批注
        </button>
      </form>

      {roots.length === 0 ? (
        <p className="text-xs text-slate-400 text-center py-4">暂无团队批注，欢迎发表第一条讨论。</p>
      ) : (
        <div className="space-y-3">
          {roots.map((ann) => {
            const replies = childrenMap[ann.id] || [];
            return (
              <div key={ann.id} className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-800">{memberNames[ann.user_id] || ann.user_id.slice(0, 8)}</span>
                    {ann.anchor && <span className="font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">{ann.anchor}</span>}
                  </div>
                  <span>{ann.created_at.slice(0, 10)}</span>
                </div>
                <p className="text-xs text-slate-700 whitespace-pre-wrap break-words leading-relaxed">{ann.body}</p>
                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => setReplyTo(ann.id)}
                    className="text-[11px] text-slate-500 hover:text-indigo-600 inline-flex items-center gap-1"
                  >
                    <Reply className="w-3 h-3" />回复
                  </button>
                  <button
                    type="button"
                    onClick={() => onPromoteToIdea({
                      title: ann.body.slice(0, 36),
                      hypothesis: ann.body,
                      experiment: '',
                      annotationId: ann.id,
                    })}
                    className="text-[11px] text-violet-600 hover:text-violet-800 inline-flex items-center gap-1"
                  >
                    <Lightbulb className="w-3 h-3" />转为团队 Idea
                  </button>
                </div>

                {replies.length > 0 && (
                  <div className="mt-2 pl-3 border-l-2 border-slate-200 space-y-2">
                    {replies.map((rep) => (
                      <div key={rep.id} className="text-xs bg-slate-50 rounded-lg p-2.5 space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span className="font-semibold text-slate-800">{memberNames[rep.user_id] || rep.user_id.slice(0, 8)}</span>
                          <span>{rep.created_at.slice(0, 10)}</span>
                        </div>
                        <p className="text-slate-700 whitespace-pre-wrap break-words">{rep.body}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
