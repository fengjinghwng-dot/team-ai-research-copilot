'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { AvailableTeam, JoinRequest } from '@/lib/contracts/types';

export function TeamApplications({onMembershipChange}: {onMembershipChange: () => void}) {
  const [teams, setTeams] = useState<AvailableTeam[]>([]);
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [messages, setMessages] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [loaded, setLoaded] = useState(false);
  const seenApprovals = useRef(new Set<string>());
  const sequence = useRef(0);
  const load = useCallback(async () => {
    const current = ++sequence.current;
    const api = getBrowserCopilotClient();
    const [available, mine] = await Promise.all([api.availableTeams(), api.myJoinRequests()]);
    if (current !== sequence.current) return;
    setTeams(available.items); setRequests(mine.items); setLoaded(true);
    const fresh = mine.items.filter(item => item.status === 'approved' && !seenApprovals.current.has(item.id));
    fresh.forEach(item => seenApprovals.current.add(item.id));
    if (fresh.length) onMembershipChange();
  }, [onMembershipChange]);
  useEffect(() => {
    const refresh = () => {if (!document.hidden) load().catch(error => setNotice(formatApiError(error).message));};
    refresh();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    return () => {sequence.current++; window.clearInterval(timer); window.removeEventListener('focus', refresh);};
  }, [load]);
  async function perform(action: () => Promise<unknown>, message: string) {
    setBusy(true); setNotice('');
    try {await action(); await load(); setNotice(message);}
    catch (error) {setNotice(formatApiError(error).message);}
    finally {setBusy(false);}
  }
  // Keep the newest application for each team, including withdrawn/rejected history.
  const latest = new Map<string, JoinRequest>();
  requests.forEach(item => {if (!latest.has(item.team_id)) latest.set(item.team_id, item);});
  const entries = new Map(teams.map(team => [team.id, team.name]));
  requests.filter(item => item.status === 'pending').forEach(item => entries.set(item.team_id, item.team_name || '科研团队'));
  if (loaded && !entries.size && !notice) return null;
  return <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-bold text-slate-900">申请加入团队</h2>
      <button type="button" disabled={busy} onClick={() => perform(load, '申请状态已刷新')}
        className="text-xs text-indigo-600 disabled:opacity-50">刷新申请状态</button>
    </div>
    <p className="text-xs text-slate-500">选择开放申请的团队并提交说明。管理员通过后即可进入；此页面每 30 秒检查审批结果。</p>
    {notice && <p role="status" className="text-xs text-slate-600">{notice}</p>}
    {[...entries].map(([id, name]) => {
      const item = latest.get(id);
      return <div key={id} className="rounded-xl border border-slate-200 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-900">{name}</h3>
        {item?.status === 'pending' ? <div className="flex items-center justify-between text-xs gap-3">
          <span className="text-amber-700">申请已提交，等待管理员审批</span>
          <button disabled={busy} onClick={() => perform(() => getBrowserCopilotClient().cancelJoinRequest(item.id), '申请已撤回')}
            className="text-slate-500 disabled:opacity-50">撤回申请</button>
        </div> : <form className="space-y-2" onSubmit={event => {
          event.preventDefault(); perform(() => getBrowserCopilotClient().requestJoin(id, messages[id] || ''), '申请已提交，等待管理员审批');
        }}>
          {item?.status === 'rejected' && <p className="text-xs text-rose-600">上次申请未通过，可补充说明后重新申请。</p>}
          {item?.status === 'cancelled' && <p className="text-xs text-slate-500">上次申请已撤回。</p>}
          <textarea aria-label={`申请说明：${name}`} maxLength={1000} rows={2} value={messages[id] || ''}
            onChange={event => setMessages(value => ({...value, [id]: event.target.value}))}
            placeholder="申请说明（选填）：姓名、课题组或研究方向"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          <button disabled={busy} className="rounded-lg bg-indigo-600 px-4 py-2 text-xs text-white disabled:opacity-50">申请加入</button>
        </form>}
      </div>;
    })}
  </section>;
}
