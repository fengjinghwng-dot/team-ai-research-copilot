'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import { ArrowLeft, ExternalLink, AlertTriangle, Lightbulb, FileText } from 'lucide-react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { Analysis, PaperDetail, UUID } from '@/lib/contracts/types';
import { isReportStale, sanitizeExternalUrl } from '@/lib/evidence';
import { StatusBanner } from '@/components/StatusBanner';
import { EvidenceQuote } from '@/components/EvidenceQuote';
import { PaperVote } from '@/components/PaperVote';
import { ClaimButton } from '@/components/ClaimButton';
import { AnnotationThread } from '@/components/AnnotationThread';
import { IdeaComposer } from '@/components/IdeaComposer';

export default function PaperDetailPage() {
  const params = useParams<{ teamId: string; paperId: string }>();
  const pathname = usePathname();
  const { teamId, paperId } = params;

  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<UUID | null>(null);
  const [currentUserId, setCurrentUserId] = useState<UUID | null>(null);
  const [memberNames, setMemberNames] = useState<Record<UUID, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number | null; message: string } | null>(null);

  const [ideaModal, setIdeaModal] = useState<{
    open: boolean;
    title: string;
    hypothesis: string;
    experiment: string;
    annotationId?: UUID;
  }>({ open: false, title: '', hypothesis: '', experiment: '' });

  const loadDetail = useCallback(async () => {
    try {
      const api = getBrowserCopilotClient();
      const [d, me, membersRes] = await Promise.all([
        api.detail(teamId, paperId),
        api.me().catch(() => null),
        api.members(teamId).catch(() => ({ items: [] })),
      ]);
      setDetail(d);
      if (me) setCurrentUserId(me.id);
      const map: Record<UUID, string> = {};
      membersRes.items.forEach((m) => { map[m.id] = m.display_name; });
      setMemberNames(map);
      setSelectedAnalysisId((prev) => prev || d.analyses[0]?.id || null);
      setError(null);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [teamId, paperId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  if (loading) return <div className="text-sm text-slate-500 py-10 text-center">正在加载论文详情...</div>;
  if (error) return <StatusBanner status={error.status} message={error.message} loginReturnTo={pathname} />;
  if (!detail) return null;

  const { paper, analyses } = detail;
  const activeAnalysis: Analysis | undefined = analyses.find((a) => a.id === selectedAnalysisId) || analyses[0];
  const stale = activeAnalysis ? isReportStale(activeAnalysis.report, paper) : false;
  const safeSourceUrl = sanitizeExternalUrl(paper.source_url);

  return (
    <div className="space-y-5">
      <Link href={`/teams/${teamId}`} className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-indigo-600">
        <ArrowLeft className="w-3.5 h-3.5" />返回今日日报
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          {paper.arxiv_id && <span className="font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700">arXiv:{paper.arxiv_version || paper.arxiv_id}</span>}
          {paper.first_submitted_at && <span>首次提交：{paper.first_submitted_at.slice(0, 10)}</span>}
          {paper.updated_at && <span>更新：{paper.updated_at.slice(0, 10)}</span>}
          {safeSourceUrl && (
            <a href={safeSourceUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline inline-flex items-center gap-1">
              论文原文 <ExternalLink className="w-3 h-3" />
            </a>
          )}
          {paper.code_urls.map((u) => {
            const safe = sanitizeExternalUrl(u);
            return safe ? (
              <a key={safe} href={safe} target="_blank" rel="noopener noreferrer" className="text-emerald-700 hover:underline inline-flex items-center gap-1">
                代码仓库 <ExternalLink className="w-3 h-3" />
              </a>
            ) : null;
          })}
        </div>
        <h1 className="text-lg sm:text-xl font-bold text-slate-900 leading-snug">{paper.title}</h1>
        <p className="text-xs text-slate-500">作者：{paper.authors.join(', ') || '未知'}</p>
      </div>

      {/* Dual Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: AI Report or Metadata-Only State */}
        <div className="lg:col-span-8 space-y-5">
          {analyses.length === 0 || !activeAnalysis ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-3">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold">
                <FileText className="w-4 h-4" />尚无 AI 解读（metadata_only）
              </div>
              <h2 className="text-sm font-bold text-slate-900">原文摘要</h2>
              <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{paper.abstract}</p>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-6">
              {/* Analysis Version Switcher & Source Warnings */}
              <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-slate-100">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-indigo-600 text-white">
                    {activeAnalysis.tier === 'deep' ? '深度解读' : '中等解读'} · {activeAnalysis.model}
                  </span>
                  {activeAnalysis.report.source.kind === 'abstract' && (
                    <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                      仅基于摘要
                    </span>
                  )}
                  {activeAnalysis.report.source.truncated && (
                    <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                      全文节选
                    </span>
                  )}
                </div>

                {analyses.length > 1 && (
                  <select
                    value={activeAnalysis.id}
                    onChange={(e) => setSelectedAnalysisId(e.target.value)}
                    className="px-2.5 py-1 text-xs border border-slate-200 rounded-lg bg-slate-50"
                  >
                    {analyses.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.created_at.slice(0, 10)} · {a.tier} ({a.report.source.paper_version || '未知版本'})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {stale && (
                <div className="rounded-xl bg-amber-50 border border-amber-200 p-3.5 text-xs text-amber-900 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                  <span>
                    <strong>旧版本报告：</strong>当前报告基于版本 <span className="font-mono">{activeAnalysis.report.source.paper_version}</span> 生成，而论文已更新至 <span className="font-mono">{paper.arxiv_version}</span>，请勿将其视为最新版本的分析结果。
                  </span>
                </div>
              )}

              {/* Summary & Innovation */}
              <section className="space-y-2">
                <h2 className="text-sm font-bold text-slate-900">核心摘要与创新点</h2>
                <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{activeAnalysis.report.summary}</p>
                <p className="text-xs text-indigo-900 bg-indigo-50/70 border border-indigo-100 rounded-xl p-3 leading-relaxed">
                  <strong>核心创新：</strong>{activeAnalysis.report.innovation}
                </p>
              </section>

              {/* Methods */}
              {activeAnalysis.report.methods.length > 0 && (
                <section className="space-y-2.5 pt-4 border-t border-slate-100">
                  <h2 className="text-sm font-bold text-slate-900">核心方法</h2>
                  <div className="space-y-2.5">
                    {activeAnalysis.report.methods.map((m, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-slate-50/70 border border-slate-200/80 text-xs text-slate-800">
                        <p className="font-medium leading-relaxed">{m.statement}</p>
                        <EvidenceQuote evidence={m.evidence} source={activeAnalysis.report.source} paper={paper} />
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Paper Facts */}
              <section className="space-y-2.5 pt-4 border-t border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">论文事实 (Paper Facts)</span>
                </div>
                {activeAnalysis.report.paper_facts.length === 0 ? (
                  <p className="text-xs text-slate-400">暂无单独列出的论文事实条目。</p>
                ) : (
                  <div className="space-y-2.5">
                    {activeAnalysis.report.paper_facts.map((f, idx) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-emerald-50/40 border border-emerald-200/70 text-xs text-slate-800">
                        <p className="font-medium leading-relaxed">{f.statement}</p>
                        <EvidenceQuote evidence={f.evidence} source={activeAnalysis.report.source} paper={paper} />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Critical Gaps (paper_stated vs inference) */}
              <section className="space-y-2.5 pt-4 border-t border-slate-100">
                <h2 className="text-sm font-bold text-slate-900">局限与批判性分析</h2>
                {activeAnalysis.report.critical_gaps.length === 0 ? (
                  <p className="text-xs text-slate-400">暂无局限分析条目。</p>
                ) : (
                  <div className="space-y-2.5">
                    {activeAnalysis.report.critical_gaps.map((g, idx) => {
                      const isStated = g.kind === 'paper_stated';
                      return (
                        <div key={idx} className={`p-3.5 rounded-xl border text-xs ${isStated ? 'bg-emerald-50/30 border-emerald-200' : 'bg-amber-50/40 border-amber-200'}`}>
                          <span className={`inline-block mb-1.5 px-2 py-0.5 rounded text-[11px] font-semibold ${isStated ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                            {isStated ? '原文明确提及 (paper_stated)' : '合理推断 (inference)'}
                          </span>
                          <p className="font-medium text-slate-900 leading-relaxed">{g.statement}</p>
                          <EvidenceQuote evidence={g.evidence} source={activeAnalysis.report.source} paper={paper} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* Testable Hypotheses */}
              <section className="space-y-2.5 pt-4 border-t border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-100 text-violet-800">待验证假设 (Testable Hypotheses · 尚待实验验证)</span>
                </div>
                {activeAnalysis.report.testable_hypotheses.length === 0 ? (
                  <p className="text-xs text-slate-400">本报告未生成待验证假设。</p>
                ) : (
                  <div className="space-y-3">
                    {activeAnalysis.report.testable_hypotheses.map((h, idx) => (
                      <div key={idx} className="p-4 rounded-xl bg-violet-50/50 border border-violet-200 text-xs space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <p className="font-bold text-slate-900 text-sm">{h.statement}</p>
                          <button
                            type="button"
                            onClick={() => setIdeaModal({
                              open: true,
                              title: h.statement.slice(0, 48),
                              hypothesis: `${h.statement}\n依据：${h.rationale}`,
                              experiment: `实验：${h.experiment}\n指标：${h.metric}\n证伪条件：${h.falsification}`,
                            })}
                            className="px-2.5 py-1 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-[11px] font-semibold shrink-0 inline-flex items-center gap-1"
                          >
                            <Lightbulb className="w-3 h-3" />转存 Idea
                          </button>
                        </div>
                        <p className="text-slate-700"><strong>推理依据：</strong>{h.rationale}</p>
                        <p className="text-slate-700"><strong>验证实验：</strong>{h.experiment}</p>
                        <p className="text-slate-700"><strong>衡量指标：</strong>{h.metric}</p>
                        <p className="text-slate-700"><strong>证伪标准：</strong>{h.falsification}</p>
                        <EvidenceQuote evidence={h.evidence} source={activeAnalysis.report.source} paper={paper} />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Reviewer View */}
              <section className="pt-4 border-t border-slate-100 space-y-1.5">
                <h2 className="text-sm font-bold text-slate-900">审稿人综合视角</h2>
                <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">{activeAnalysis.report.reviewer_view}</p>
              </section>
            </div>
          )}
        </div>

        {/* Right: Team Collaboration Column */}
        <aside className="lg:col-span-4 space-y-5">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
            <h2 className="text-sm font-bold text-slate-900">团队价值投票</h2>
            <PaperVote
              teamId={teamId}
              paperId={paperId}
              voteTotal={detail.vote_total}
              myVote={detail.my_vote}
              onUpdated={loadDetail}
            />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
            <h2 className="text-sm font-bold text-slate-900">组会分享认领</h2>
            <ClaimButton
              teamId={teamId}
              paperId={paperId}
              currentUserId={currentUserId}
              claims={detail.claims}
              memberNames={memberNames}
              onUpdated={loadDetail}
            />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3">
            <h2 className="text-sm font-bold text-slate-900">团队批注与讨论（{detail.annotations.length}）</h2>
            <AnnotationThread
              teamId={teamId}
              paperId={paperId}
              annotations={detail.annotations}
              memberNames={memberNames}
              onUpdated={loadDetail}
              onPromoteToIdea={(prefill) => setIdeaModal({ open: true, ...prefill })}
            />
          </div>
        </aside>
      </div>

      <IdeaComposer
        open={ideaModal.open}
        teamId={teamId}
        defaultPaperId={paperId}
        defaultAnnotationId={ideaModal.annotationId}
        defaultTitle={ideaModal.title}
        defaultHypothesis={ideaModal.hypothesis}
        defaultExperiment={ideaModal.experiment}
        onClose={() => setIdeaModal((prev) => ({ ...prev, open: false }))}
        onCreated={async () => {}}
      />
    </div>
  );
}
