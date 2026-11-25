'use client';

import { useState } from 'react';
import { formatApiError, getBrowserCopilotClient } from '@/lib/api';
import type { PaperAffiliations as Result } from '@/lib/contracts/types';
import { sanitizeExternalUrl } from '@/lib/evidence';

export function PaperAffiliations({ teamId, paperId }: { teamId: string; paperId: string }) {
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function lookup() {
    setBusy(true);
    setError('');
    try {
      setResult(await getBrowserCopilotClient().affiliations(teamId, paperId));
    } catch (err) {
      setError(formatApiError(err).message);
    } finally {
      setBusy(false);
    }
  }

  const source = result?.source_url && sanitizeExternalUrl(result.source_url);
  return <div className="space-y-2 text-xs text-slate-600">
    <button type="button" onClick={lookup} disabled={busy}
      className="rounded-lg bg-slate-100 px-3 py-1.5 font-medium text-slate-800 disabled:opacity-50">
      {busy ? '正在查询机构…' : '查询作者机构'}
    </button>
    {error && <p role="status">{error}</p>}
    {result?.state === 'not_listed' && <p role="status">公开论文记录未列出作者机构。</p>}
    {result?.state === 'unavailable' && <p role="status">机构数据源暂不可用，请稍后重试。</p>}
    {result?.state === 'available' && <>
      <dl className="space-y-1">
        {result.items.map(({author, institutions}, index) => <div key={`${author}-${index}`} className="flex flex-wrap gap-x-2">
          <dt className="font-medium text-slate-800">{author}</dt><dd>{institutions.join('、')}</dd>
        </div>)}
      </dl>
      {source && <a href={source} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">OpenAlex 论文记录</a>}
    </>}
  </div>;
}
