'use client';

import { useState } from 'react';
import { CalendarCheck, XCircle } from 'lucide-react';
import { ApiError, formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Claim, UUID } from '@/lib/contracts/types';
import { teamDate } from '@/lib/date';

interface Props {
  teamId: UUID;
  paperId: UUID;
  currentUserId: UUID | null;
  claims: Claim[];
  memberNames: Record<UUID, string>;
  onUpdated: () => Promise<void>;
}

export function ClaimButton({ teamId, paperId, currentUserId, claims, memberNames, onUpdated }: Props) {
  const [meetingDate, setMeetingDate] = useState(() => teamDate());
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleClaim() {
    if (!meetingDate) return;
    setLoading(true);
    setNotice(null);
    try {
      const api = getBrowserCopilotClient();
      await api.claim(teamId, paperId, meeting_date_safe(meetingDate));
      await onUpdated();
      setNotice('认领成功');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await onUpdated();
        setNotice('该组会日期已被其他成员认领，已刷新最新分享人信息。');
      } else {
        setNotice(formatApiError(err).message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleUnclaim(claimId: UUID) {
    setLoading(true);
    setNotice(null);
    try {
      const api = getBrowserCopilotClient();
      await api.unclaim(teamId, claimId);
      await onUpdated();
      setNotice('已释放认领');
    } catch (err) {
      setNotice(formatApiError(err).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          value={meetingDate}
          onChange={(e) => setMeetingDate(e.target.value)}
          className="px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="button"
          disabled={loading}
          onClick={handleClaim}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <CalendarCheck className="w-3.5 h-3.5" />认领组会分享
        </button>
      </div>

      {claims.length > 0 && (
        <div className="space-y-1.5">
          {claims.map((c) => {
            const isMine = currentUserId === c.user_id;
            const ownerName = memberNames[c.user_id] || c.user_id.slice(0, 8);
            return (
              <div key={c.id} className="flex items-center justify-between gap-2 text-xs bg-indigo-50/70 border border-indigo-100 rounded-lg px-3 py-2">
                <div>
                  <span className="font-mono font-semibold text-indigo-800">{c.meeting_date}</span>
                  <span className="text-slate-600 ml-2">分享人：{ownerName}{isMine ? '（我）' : ''}</span>
                </div>
                {isMine && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleUnclaim(c.id)}
                    className="text-rose-600 hover:text-rose-800 inline-flex items-center gap-1 font-medium"
                  >
                    <XCircle className="w-3.5 h-3.5" />释放
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {notice && <p className="text-xs text-indigo-700">{notice}</p>}
    </div>
  );
}

function meeting_date_safe(d: string): string {
  return d.trim();
}
