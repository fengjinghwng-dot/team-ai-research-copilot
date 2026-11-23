'use client';

import { useEffect, useState } from 'react';
import { useParams, usePathname } from 'next/navigation';
import { Plus, Save, Trash2, UserPlus } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Role, UUID } from '@/lib/contracts/types';
import { StatusBanner } from '@/components/StatusBanner';
import { UsagePanel } from '@/components/UsagePanel';

interface EditableTopic {
  label: string;
  keywordsText: string;
  weight: number;
}

export default function AdminPage() {
  const params = useParams<{ teamId: string }>();
  const pathname = usePathname();
  const teamId = params.teamId;

  const [role, setRole] = useState<Role | null>(null);
  const [budget, setBudget] = useState(200000);
  const [topics, setTopics] = useState<EditableTopic[]>([]);
  const [members, setMembers] = useState<{ id: UUID; display_name: string; role: Role }[]>([]);
  const [newUserId, setNewUserId] = useState('');
  const [newUserRole, setNewUserRole] = useState<Role>('member');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  async function load() {
    try {
      const api = getBrowserCopilotClient();
      const [cfg, memRes] = await Promise.all([api.config(teamId), api.members(teamId)]);
      setRole(cfg.role);
      setBudget(cfg.team.daily_token_budget);
      setTopics(cfg.topics.map((t) => ({ label: t.label, keywordsText: t.keywords.join(', '), weight: t.weight })));
      setMembers(memRes.items);
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    }
  }

  useEffect(() => {
    load();
  }, [teamId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (role === 'member') {
    return <StatusBanner status={403} message="当前账号为普通成员，无权限访问团队管理后台。" />;
  }

  async function handleSaveConfig(e: React.FormEvent) {
    e.preventDefault();
    setNotice(null);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.setConfig(teamId, {
        daily_token_budget: Number(budget),
        topics: topics.map((t) => ({
          label: t.label.trim(),
          keywords: t.keywordsText.split(',').map((k) => k.trim()).filter(Boolean),
          weight: Number(t.weight),
        })),
      });
      setNotice('团队主线与每日 Token 配额已更新。');
    } catch (err) {
      setError(formatApiError(err));
    }
  }

  async function handleAddOrUpdateMember(e: React.FormEvent) {
    e.preventDefault();
    if (!newUserId.trim()) return;
    setNotice(null);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.addMember(teamId, newUserId.trim(), newUserRole);
      setNewUserId('');
      setNotice('成员角色已更新。');
      await load();
    } catch (err) {
      setError(formatApiError(err));
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold text-slate-900">团队管理后台</h1>
      {error && <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />}
      {notice && <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-2.5 text-xs text-emerald-800">{notice}</div>}

      {/* Usage & Jobs */}
      {role === 'admin' && <UsagePanel teamId={teamId} />}

      {/* Team Topics & Budget */}
      <form onSubmit={handleSaveConfig} className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">研究主线与每日 Token 配额</h2>
          <button
            type="button"
            onClick={() => setTopics((prev) => [...prev, { label: '', keywordsText: '', weight: 0.2 }])}
            className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-medium inline-flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />新增主线
          </button>
        </div>

        <div className="max-w-xs">
          <label className="block text-xs font-medium text-slate-700 mb-1">团队每日 Token 预算上限</label>
          <input
            type="number"
            min={10000}
            step={10000}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg font-mono"
          />
        </div>

        <div className="space-y-2.5">
          {topics.map((t, idx) => (
            <div key={idx} className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-center bg-slate-50 p-3 rounded-xl border border-slate-200/70">
              <input
                required
                placeholder="主线名称"
                value={t.label}
                onChange={(e) => setTopics((prev) => prev.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)))}
                className="sm:col-span-3 px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg"
              />
              <input
                required
                placeholder="关键词（英文逗号分隔）"
                value={t.keywordsText}
                onChange={(e) => setTopics((prev) => prev.map((x, i) => (i === idx ? { ...x, keywordsText: e.target.value } : x)))}
                className="sm:col-span-6 px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg"
              />
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                value={t.weight}
                onChange={(e) => setTopics((prev) => prev.map((x, i) => (i === idx ? { ...x, weight: Number(e.target.value) } : x)))}
                className="sm:col-span-2 px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg font-mono"
              />
              <button
                type="button"
                onClick={() => setTopics((prev) => prev.filter((_, i) => i !== idx))}
                className="sm:col-span-1 text-slate-400 hover:text-rose-600 flex justify-center"
                aria-label="删除主线"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <button type="submit" className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold inline-flex items-center gap-1.5">
          <Save className="w-3.5 h-3.5" />保存团队配置
        </button>
      </form>

      {/* Members Management */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4">
        <h2 className="text-sm font-bold text-slate-900">成员与角色管理</h2>
        <form onSubmit={handleAddOrUpdateMember} className="flex flex-wrap gap-2">
          <input
            required
            value={newUserId}
            onChange={(e) => setNewUserId(e.target.value)}
            placeholder="输入成员 User UUID（成员登录 /teams 后可见）"
            className="flex-1 min-w-[220px] px-3 py-1.5 text-xs border border-slate-200 rounded-lg font-mono"
          />
          <select
            value={newUserRole}
            onChange={(e) => setNewUserRole(e.target.value as Role)}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50"
          >
            <option value="member">普通成员 (member)</option>
            <option value="admin">管理员 (admin)</option>
          </select>
          <button type="submit" className="px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold inline-flex items-center gap-1.5">
            <UserPlus className="w-3.5 h-3.5" />添加 / 更新角色
          </button>
        </form>

        <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
          {members.map((m) => (
            <div key={m.id} className="px-4 py-2.5 bg-white flex items-center justify-between text-xs">
              <div>
                <span className="font-semibold text-slate-900">{m.display_name}</span>
                <span className="font-mono text-slate-400 ml-2">{m.id}</span>
              </div>
              <span className={`px-2 py-0.5 rounded font-semibold ${m.role === 'admin' ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>
                {m.role}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
