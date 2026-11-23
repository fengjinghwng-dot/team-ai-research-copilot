'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { UUID } from '@/lib/contracts/types';

interface Props {
  open: boolean;
  teamId: UUID;
  defaultPaperId?: UUID;
  defaultAnnotationId?: UUID;
  defaultTitle?: string;
  defaultHypothesis?: string;
  defaultExperiment?: string;
  onClose: () => void;
  onCreated: () => Promise<void>;
}

export function IdeaComposer({
  open,
  teamId,
  defaultPaperId = '',
  defaultAnnotationId,
  defaultTitle = '',
  defaultHypothesis = '',
  defaultExperiment = '',
  onClose,
  onCreated,
}: Props) {
  const [paperId, setPaperId] = useState(defaultPaperId);
  const [title, setTitle] = useState(defaultTitle);
  const [hypothesis, setHypothesis] = useState(defaultHypothesis);
  const [experiment, setExperiment] = useState(defaultExperiment);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPaperId(defaultPaperId);
      setTitle(defaultTitle);
      setHypothesis(defaultHypothesis);
      setExperiment(defaultExperiment);
      setError(null);
    }
  }, [open, defaultPaperId, defaultTitle, defaultHypothesis, defaultExperiment]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const api = getBrowserCopilotClient();
      await api.addIdea(teamId, {
        paper_id: paperId.trim(),
        title: title.trim(),
        hypothesis: hypothesis.trim(),
        experiment: experiment.trim(),
        ...(defaultAnnotationId ? { annotation_id: defaultAnnotationId } : {}),
      });
      await onCreated();
      onClose();
    } catch (err) {
      setError(formatApiError(err).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 max-w-lg w-full p-5 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">新建团队研究 Idea</h3>
          <button type="button" onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:bg-slate-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {!defaultPaperId && (
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">关联论文 ID (UUID)</label>
              <input
                required
                value={paperId}
                onChange={(e) => setPaperId(e.target.value)}
                placeholder="输入论文 UUID"
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Idea 标题</label>
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="简明概括改进方向"
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">待验证研究假设（Hypothesis）</label>
            <textarea
              required
              rows={3}
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              placeholder="说明原论文瓶颈与待验证假设"
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">最小对照实验设计（Experiment）</label>
            <textarea
              required
              rows={3}
              value={experiment}
              onChange={(e) => setExperiment(e.target.value)}
              placeholder="写明 Baseline、评测指标与可证伪条件"
              className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200">
              取消
            </button>
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
              {submitting ? '提交中...' : '保存到团队灵感池'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
