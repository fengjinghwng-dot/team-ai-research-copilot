'use client';

import { useCallback, useEffect, useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Invitation, Role } from '@/lib/contracts/types';

export function MemberManager({teamId}: {teamId: string}) {
  const [members, setMembers] = useState<{id: string; display_name: string; role: Role}[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState('');
  const [loginUrl, setLoginUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const load = useCallback(async () => {
    const api = getBrowserCopilotClient();
    const [people, invites] = await Promise.all([api.members(teamId), api.invitations(teamId)]);
    setMembers(people.items); setInvitations(invites.items); setLoginUrl(invites.login_url);
  }, [teamId]);
  useEffect(() => { load().catch(error => setNotice(formatApiError(error).message)); }, [load]);
  async function perform(action: () => Promise<unknown>, message: string) {
    setBusy(true); setNotice('');
    try { await action(); await load(); setNotice(message); }
    catch (error) { setNotice(formatApiError(error).message); }
    finally { setBusy(false); }
  }
  const labels = {pending: '等待登录', accepted: '已加入', expired: '已过期', revoked: '已撤销'};
  return <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
    <h2 className="text-sm font-bold text-slate-900">成员邀请与权限</h2>
    <p className="text-xs text-slate-500">登记邮箱后，将登录地址发给成员；对方验证该邮箱并登录即可加入。邀请有效期 7 天，不会自动发送邮件。</p>
    <form className="flex flex-wrap gap-2" onSubmit={event => {
      event.preventDefault(); perform(() => getBrowserCopilotClient().invite(teamId, email), '邀请已创建，请将登录地址发给成员。');
    }}>
      <input aria-label="邀请成员邮箱" type="email" required value={email} onChange={event => setEmail(event.target.value)}
        placeholder="成员的学校邮箱、163 或 Gmail" className="flex-1 min-w-[220px] rounded-lg border border-slate-200 px-3 py-2 text-sm" />
      <button disabled={busy} className="rounded-lg bg-indigo-600 text-white px-4 py-2 text-xs disabled:opacity-50">创建邀请</button>
      <button type="button" disabled={!loginUrl} onClick={async () => {
        try { await navigator.clipboard.writeText(loginUrl); setNotice('登录地址已复制'); }
        catch { setNotice(`登录地址：${loginUrl}`); }
      }} className="rounded-lg border border-slate-200 px-3 py-2 text-xs">复制登录地址</button>
    </form>
    {notice && <p role="status" className="text-xs text-slate-600">{notice}</p>}
    {invitations.length > 0 && <div className="divide-y divide-slate-100">
      {invitations.map(item => <div key={item.id} className="flex justify-between gap-3 py-2 text-xs">
        <span className="break-all">{item.email} · {labels[item.state]}</span>
        {item.state === 'pending' && <button disabled={busy} onClick={() => perform(
          () => getBrowserCopilotClient().revokeInvitation(teamId, item.id), '邀请已撤销')}
          className="text-rose-600 shrink-0">撤销邀请</button>}
      </div>)}
    </div>}
    <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl">
      {members.map(member => <div key={member.id} className="flex items-center justify-between gap-3 p-3 text-xs">
        <span>{member.display_name || '未设置姓名的成员'}</span>
        <div className="flex items-center gap-3">
          <select aria-label={`${member.display_name || '成员'}的角色`} value={member.role} disabled={busy}
            onChange={event => perform(() => getBrowserCopilotClient().addMember(teamId, member.id, event.target.value as Role), '成员角色已更新')}
            className="border border-slate-200 rounded-lg p-1.5 bg-white">
            <option value="member">普通成员</option><option value="admin">管理员</option>
          </select>
          <button disabled={busy} className="text-rose-600" onClick={() => {
            if (window.confirm('确认将这位成员移出团队？对方将失去团队访问权限。')) perform(
              () => getBrowserCopilotClient().removeMember(teamId, member.id), '成员已移出团队');
          }}>移出</button>
        </div>
      </div>)}
    </div>
  </section>;
}
