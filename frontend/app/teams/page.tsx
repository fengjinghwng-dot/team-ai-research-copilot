'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Users, ArrowRight, Clock } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Me, Role, UUID } from '@/lib/contracts/types';
import { StatusBanner } from '@/components/StatusBanner';
import { PasswordSettings } from '@/components/PasswordSettings';
import { TeamApplications } from '@/components/TeamApplications';

interface TeamSummary {
  teamId: UUID;
  name: string;
  role: Role;
}

export default function TeamsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshCount, setRefreshCount] = useState(0);
  const refreshMembership = useCallback(() => setRefreshCount(value => value + 1), []);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const user = await api.me();
        if (!active) return;
        setMe(user);
        setError(null);

        const resolved = await Promise.all(
          user.memberships.map(async (m) => {
            try {
              const cfg = await api.config(m.team_id);
              return { teamId: m.team_id, name: cfg.team.name, role: m.role };
            } catch {
              return { teamId: m.team_id, name: `团队 ${m.team_id.slice(0, 8)}`, role: m.role };
            }
          })
        );
        if (active) setTeams(resolved);
      } catch (err) {
        if (active) setError(formatApiError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [refreshCount]);

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900">选择你的科研团队</h1>
          {me && <p className="text-xs text-slate-500 mt-1">当前账号：{me.display_name || me.email}</p>}
        </div>

        {error && <StatusBanner status={error.status} message={error.message} loginReturnTo="/teams" />}

        {loading ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-sm text-slate-500">
            正在加载团队信息...
          </div>
        ) : !error && teams.length === 0 ? (
          <div className="bg-white rounded-2xl border border-amber-200 p-8 text-center space-y-3">
            <Clock className="w-8 h-8 text-amber-500 mx-auto" />
            <h2 className="text-base font-bold text-slate-900">等待管理员加入</h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              在下方选择团队并提交入组申请，等待管理员通过。也可以请管理员邀请你的完整邮箱：{me?.email}，再点击“检查邀请”。
            </p>
            <button type="button" onClick={() => setRefreshCount(value => value + 1)}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">检查邀请</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {teams.map((t) => (
              <Link
                key={t.teamId}
                href={`/teams/${t.teamId}`}
                className="bg-white rounded-2xl border border-slate-200 p-5 hover:border-indigo-300 hover:shadow-sm transition flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-slate-900">{t.name}</div>
                    <div className="text-xs text-slate-500">角色：{t.role === 'admin' ? '管理员' : '普通成员'}</div>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </Link>
            ))}
          </div>
        )}
        {me && <TeamApplications onMembershipChange={refreshMembership} />}
        {me && <PasswordSettings compact />}
      </div>
    </div>
  );
}
