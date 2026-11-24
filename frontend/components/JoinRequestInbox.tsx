'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { JoinRequest } from '@/lib/contracts/types';

export function JoinRequestInbox({teamId}: {teamId: string}) {
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const sequence = useRef(0);
  const load = useCallback(async () => {
    const current = ++sequence.current;
    const result = await getBrowserCopilotClient().joinRequests(teamId);
    if (current !== sequence.current) return;
    setRequests(result.items); setCount(result.pending_count);
  }, [teamId]);
  useEffect(() => {
    const refresh = () => {if (!document.hidden) load().catch(error => setNotice(formatApiError(error).message));};
    refresh();
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    return () => {sequence.current++; window.clearInterval(timer); window.removeEventListener('focus', refresh);};
  }, [load]);
  async function review(item: JoinRequest, decision: 'approve' | 'reject') {
    setBusy(true); setNotice('');
    try {
      await getBrowserCopilotClient().reviewJoinRequest(teamId, item.id, decision);
      await load();
      window.dispatchEvent(new Event('copilot:membership-reviewed'));
      setNotice(decision === 'approve' ? '已通过申请，对方现在可以进入团队。' : '已拒绝这份申请。');
    } catch (error) {setNotice(formatApiError(error).message); await load().catch(() => {});}
    finally {setBusy(false);}
  }
  return <section className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
    <div className="flex justify-between items-center gap-3">
      <h2 className="text-sm font-bold text-slate-900">入组申请 <span className="text-indigo-600">{count} 条待处理</span></h2>
      <button type="button" disabled={busy} onClick={() => load().then(() => setNotice('申请列表已刷新')).catch(error => setNotice(formatApiError(error).message))}
        className="text-xs text-indigo-600 disabled:opacity-50">刷新申请</button>
    </div>
    <p className="text-xs text-slate-500">成员登录后可在团队选择页申请。通过后成为普通成员；列表每 30 秒自动刷新。</p>
    {notice && <p role="status" className="text-xs text-slate-600">{notice}</p>}
    {!requests.length && <p className="text-sm text-slate-500">暂无待处理的入组申请</p>}
    <div className="divide-y divide-slate-100">
      {requests.map(item => <div key={item.id} className="py-3 space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900 break-all">{item.applicant_name || '未设置姓名'} · {item.applicant_email}</p>
            <p className="text-xs text-slate-400 mt-1">{new Date(item.created_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai'})}（北京时间）</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button disabled={busy} onClick={() => review(item, 'approve')} className="rounded-lg bg-indigo-600 text-white px-4 py-2 text-xs disabled:opacity-50">通过</button>
            <button disabled={busy} onClick={() => review(item, 'reject')} className="rounded-lg border border-slate-200 text-rose-600 px-4 py-2 text-xs disabled:opacity-50">拒绝</button>
          </div>
        </div>
        <p className="text-sm text-slate-600 whitespace-pre-wrap break-words">{item.message || '未填写申请说明'}</p>
      </div>)}
    </div>
  </section>;
}
