'use client';

import { useEffect, useState } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Role } from '@/lib/contracts/types';
import { TeamShell } from '@/components/TeamShell';
import { StatusBanner } from '@/components/StatusBanner';

export default function TeamLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;
  const [teamName, setTeamName] = useState('加载中...');
  const [role, setRole] = useState<Role>('member');
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const cfg = await api.config(teamId);
        if (!active) return;
        setTeamName(cfg.team.name);
        setRole(cfg.role);
        setError(null);
      } catch (err) {
        if (active) setError(formatApiError(err));
      } finally {
        if (active) setReady(true);
      }
    }
    load();
    const onConfigUpdated = (event: Event) => {
      if ((event as CustomEvent<{teamId: string}>).detail?.teamId === teamId) load();
    };
    window.addEventListener('copilot:team-config-updated', onConfigUpdated);
    return () => { active = false; window.removeEventListener('copilot:team-config-updated', onConfigUpdated); };
  }, [teamId]);

  if (!ready) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">正在加载团队工作区...</div>;
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-2xl mx-auto">
          <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />
        </div>
      </div>
    );
  }

  return (
    <TeamShell teamId={teamId} teamName={teamName} role={role}>
      {children}
    </TeamShell>
  );
}
