'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { Plus } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Idea, IdeaStatus, Role, UUID } from '@/lib/contracts/types';
import { StatusBanner } from '@/components/StatusBanner';
import { IdeaComposer } from '@/components/IdeaComposer';

const STATUSES: { value: IdeaStatus; label: string }[] = [
  { value: 'backlog', label: '待评估 (backlog)' },
  { value: 'evaluating', label: '评估中 (evaluating)' },
  { value: 'planned', label: '已立项 (planned)' },
  { value: 'experimenting', label: '实验中 (experimenting)' },
  { value: 'archived', label: '已归档 (archived)' },
];

export default function IdeasPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;

  const [statusFilter, setStatusFilter] = useState<IdeaStatus | 'ALL'>('ALL');
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [members, setMembers] = useState<{ id: UUID; display_name: string; role: Role }[]>([]);
  const [composerOpen, setComposerOpen] = useState(false);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const api = getBrowserCopilotClient();
      const [ideaRes, memRes] = await Promise.all([
        api.ideas(teamId, statusFilter === 'ALL' ? undefined : statusFilter),
        api.members(teamId).catch(() => ({ items: [] })),
      ]);
      setIdeas(ideaRes.items);
      setMembers(memRes.items);
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    }
  }, [teamId, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpdate(idea: Idea, nextStatus: IdeaStatus, nextAssignee: UUID | null) {
    try {
      const api = getBrowserCopilotClient();
      await api.updateIdea(teamId, idea.id, nextStatus, nextAssignee);
      await load();
    } catch (err) {
      setError(formatApiError(err));
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white rounded-2xl border border-slate-200 p-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900">团队研究灵感池</h1>
          <p className="text-xs text-slate-500">管理从论文待验证假设或团队批注转存的研究构想与推进阶段</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as IdeaStatus | 'ALL')}
            className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg"
          >
            <option value="ALL">全部阶段</option>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setComposerOpen(true)}
            className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold inline-flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />新建 Idea
          </button>
        </div>
      </div>

      {error && <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />}

      {ideas.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-xs text-slate-500">
          当前筛选下暂无研究 Idea。
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {ideas.map((idea) => (
            <div key={idea.id} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <h2 className="text-base font-bold text-slate-900">{idea.title}</h2>
                  <Link href={`/teams/${teamId}/papers/${idea.paper_id}`} className="text-xs text-indigo-600 hover:underline font-mono">
                    查看来源论文 ({idea.paper_id.slice(0, 8)})
                  </Link>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={idea.status}
                    onChange={(e) => handleUpdate(idea, e.target.value as IdeaStatus, idea.assignee_id)}
                    className="px-2.5 py-1 text-xs bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    {STATUSES.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                  <select
                    value={idea.assignee_id || ''}
                    onChange={(e) => handleUpdate(idea, idea.status, e.target.value || null)}
                    className="px-2.5 py-1 text-xs bg-slate-50 border border-slate-200 rounded-lg"
                  >
                    <option value="">未指派负责人</option>
                    {members.map((m) => (
                      <option key={m.id} value={m.id}>{m.display_name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="text-xs text-slate-700 whitespace-pre-wrap"><strong>假设：</strong>{idea.hypothesis}</div>
              <div className="text-xs text-slate-700 whitespace-pre-wrap"><strong>实验设计：</strong>{idea.experiment}</div>
            </div>
          ))}
        </div>
      )}

      <IdeaComposer
        open={composerOpen}
        teamId={teamId}
        onClose={() => setComposerOpen(false)}
        onCreated={load}
      />
    </div>
  );
}
