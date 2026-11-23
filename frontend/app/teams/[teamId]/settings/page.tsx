'use client';

import { useEffect, useState } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { Save } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import { StatusBanner } from '@/components/StatusBanner';

export default function SettingsPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;

  const [displayName, setDisplayName] = useState('');
  const [emailOptIn, setEmailOptIn] = useState(true);
  const [interests, setInterests] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const api = getBrowserCopilotClient();
        const [me, cfg] = await Promise.all([api.me(), api.config(teamId)]);
        if (!active) return;
        setDisplayName(me.display_name);
        setEmailOptIn(me.email_opt_in);
        const initInterests: Record<string, number> = { ...cfg.interests };
        cfg.topics.forEach((t) => {
          if (!(t.label in initInterests)) initInterests[t.label] = t.weight;
        });
        setInterests(initInterests);
      } catch (err) {
        if (active) setError(formatApiError(err));
      }
    }
    load();
    return () => { active = false; };
  }, [teamId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.setProfile(teamId, {
        display_name: displayName.trim(),
        interests,
        email_opt_in: emailOptIn,
      });
      setNotice('个人兴趣与订阅设置已保存，将在下一轮日报生成时生效。');
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-5">
      <h1 className="text-lg font-bold text-slate-900">个人兴趣与邮件订阅</h1>
      {error && <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />}

      <form onSubmit={handleSave} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">显示名称</label>
          <input
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="space-y-3">
          <div className="text-xs font-semibold text-slate-800">个人方向兴趣权重（0 – 1）</div>
          {Object.entries(interests).map(([topic, val]) => (
            <div key={topic} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-700">{topic}</span>
                <span className="font-mono font-bold text-indigo-700">{Math.round(val * 100)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={val}
                onChange={(e) => setInterests((prev) => ({ ...prev, [topic]: Number(e.target.value) }))}
                className="w-full accent-indigo-600"
              />
            </div>
          ))}
        </div>

        <label className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={emailOptIn}
            onChange={(e) => setEmailOptIn(e.target.checked)}
            className="rounded accent-indigo-600"
          />
          每日自动接收团队与个人论文邮件日报
        </label>

        {notice && <p className="text-xs text-emerald-700">{notice}</p>}

        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <Save className="w-3.5 h-3.5" />{saving ? '保存中...' : '保存个人设置'}
        </button>
      </form>
    </div>
  );
}
