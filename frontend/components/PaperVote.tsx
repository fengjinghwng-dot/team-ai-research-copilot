'use client';

import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { getBrowserCopilotClient, formatApiError } from '@/lib/api';
import type { UUID } from '@/lib/contracts/types';

interface Props {
  teamId: UUID;
  paperId: UUID;
  voteTotal: number;
  myVote: -1 | 0 | 1;
  onUpdated: () => Promise<void>;
}

export function PaperVote({ teamId, paperId, voteTotal, myVote, onUpdated }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleVote(next: -1 | 1) {
    const targetValue: -1 | 0 | 1 = myVote === next ? 0 : next;
    setSubmitting(true);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.vote(teamId, paperId, targetValue);
      await onUpdated();
    } catch (err) {
      setError(formatApiError(err).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleVote(1)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition inline-flex items-center gap-1.5 ${
            myVote === 1
              ? 'bg-emerald-600 text-white border-emerald-600'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <ThumbsUp className="w-3.5 h-3.5" />+1 值得看
        </button>
        <span className="px-2.5 py-1 rounded-lg bg-slate-100 text-xs font-mono font-bold text-slate-800">
          净票数 {voteTotal >= 0 ? `+${voteTotal}` : voteTotal}
        </span>
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleVote(-1)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition inline-flex items-center gap-1.5 ${
            myVote === -1
              ? 'bg-rose-600 text-white border-rose-600'
              : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
          }`}
        >
          <ThumbsDown className="w-3.5 h-3.5" />-1
        </button>
      </div>
      <p className="text-[11px] text-slate-400">投票会立即记录，推荐排序将在下一轮日报生成时更新。</p>
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </div>
  );
}
