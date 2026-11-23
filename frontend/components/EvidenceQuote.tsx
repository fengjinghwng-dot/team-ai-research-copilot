'use client';

import { ExternalLink, Quote } from 'lucide-react';
import type { Evidence, Paper, PaperReport } from '@/lib/contracts/types';
import { buildEvidenceLink } from '@/lib/evidence';

interface Props {
  evidence: Evidence;
  source: PaperReport['source'];
  paper: Paper;
}

export function EvidenceQuote({ evidence, source, paper }: Props) {
  const link = buildEvidenceLink(source, paper, evidence.anchor);

  return (
    <div className="mt-2 rounded-lg bg-slate-50 border border-slate-200/80 px-3 py-2 text-xs text-slate-600 space-y-1">
      <div className="flex items-start gap-1.5">
        <Quote className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />
        <p className="italic leading-relaxed break-words">{evidence.quote}</p>
      </div>
      <div className="flex items-center justify-end">
        {link.href ? (
          <a
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-[11px] text-indigo-600 hover:underline"
          >
            {link.label}
            <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <span className="font-mono text-[11px] text-slate-500">{link.label}</span>
        )}
      </div>
    </div>
  );
}
