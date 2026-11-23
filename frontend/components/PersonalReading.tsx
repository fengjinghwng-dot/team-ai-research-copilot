'use client';

import { useState } from 'react';
import { Bookmark, CheckCheck, Save } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { PaperState } from '@/lib/contracts/types';

export function PersonalReading({teamId, paperId, initial}: {
  teamId: string; paperId: string; initial?: PaperState;
}) {
  const [state, setState] = useState<PaperState>(initial || {saved: false, is_read: false, note: '', updated_at: null});
  const [note, setNote] = useState(initial?.note || '');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  async function update(patch: Partial<Pick<PaperState, 'saved' | 'is_read' | 'note'>>) {
    setBusy(true);
    setNotice('');
    try {
      const result = await getBrowserCopilotClient().setPaperState(teamId, paperId, patch);
      setState(result);
      setNotice('已保存');
    } catch (error) { setNotice(formatApiError(error).message); }
    finally { setBusy(false); }
  }
  return <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
    <h2 className="text-sm font-bold text-slate-900">我的阅读记录</h2>
    <div className="flex gap-2 text-xs">
      <button type="button" disabled={busy} aria-pressed={state.saved} onClick={() => update({saved: !state.saved})}
        className="inline-flex gap-1 items-center rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-50">
        <Bookmark className="w-3.5 h-3.5" />{state.saved ? '已收藏' : '收藏论文'}</button>
      <button type="button" disabled={busy} aria-pressed={state.is_read} onClick={() => update({is_read: !state.is_read})}
        className="inline-flex gap-1 items-center rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-50">
        <CheckCheck className="w-3.5 h-3.5" />{state.is_read ? '已读' : '标为已读'}</button>
    </div>
    <label htmlFor="private-note" className="block text-xs font-medium text-slate-700">个人笔记（仅自己可见）</label>
    <textarea id="private-note" value={note} maxLength={10000} disabled={busy} rows={5}
      onChange={event => setNote(event.target.value)} placeholder="记录自己的理解或尚未准备共享的想法…"
      className="w-full rounded-xl border border-slate-200 p-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500" />
    <button type="button" disabled={busy || note === state.note} onClick={() => update({note})}
      className="inline-flex gap-1 items-center rounded-lg bg-indigo-600 text-white text-xs px-3 py-2 disabled:opacity-40">
      <Save className="w-3.5 h-3.5" />保存个人笔记</button>
    {notice && <p role="status" className="text-xs text-slate-600">{notice}</p>}
  </div>;
}
