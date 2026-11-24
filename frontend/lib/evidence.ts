import type { Paper, PaperReport } from './contracts/types';

/** 过滤不安全链接协议，仅允许 http/https */
export function sanitizeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      return parsed.toString();
    }
    return null;
  } catch {
    return null;
  }
}

/** 校验站内 returnTo，防止开放重定向 */
export function sanitizeReturnTo(raw: string | null | undefined, fallback = '/teams'): string {
  if (!raw) return fallback;
  const trimmed = raw.trim();
  if (!trimmed.startsWith('/') || trimmed.startsWith('//') || /[\\\u0000-\u001f\u007f]/.test(trimmed)) {
    return fallback;
  }
  return trimmed;
}

/**
 * 严格按 FRONTEND_HANDOFF.md 第 3 条构造原文证据定位链接：
 * - HTML: 使用 source_url 对应 /html/{version}#anchor
 * - PDF: 使用 https://arxiv.org/pdf/{version}#page=N
 * - LaTeX / abstract: 不构造跳转链接，仅显示来源名
 */
export function buildEvidenceLink(
  source: PaperReport['source'],
  paper: Paper,
  anchor: string
): { href: string | null; label: string } {
  const version = source.paper_version || paper.arxiv_version || paper.arxiv_id;
  if (source.kind === 'html' && version) {
    const cleanAnchor = anchor.replace(/^#/, '');
    const base = sanitizeExternalUrl(paper.source_url);
    if (base && base.includes('arxiv.org')) {
      return {
        href: `https://arxiv.org/html/${encodeURIComponent(version)}#${encodeURIComponent(cleanAnchor)}`,
        label: `HTML · #${cleanAnchor}`,
      };
    }
    if (base) {
      return {
        href: `${base.replace(/#.*$/, '')}#${encodeURIComponent(cleanAnchor)}`,
        label: `HTML · #${cleanAnchor}`,
      };
    }
  }
  if (source.kind === 'pdf' && version) {
    const pageMatch = anchor.match(/(?:page|p\.?)[\s:=]*(\d+)/i) || anchor.match(/(\d+)/);
    const pageNum = pageMatch ? pageMatch[1] : '1';
    return {
      href: `https://arxiv.org/pdf/${encodeURIComponent(version)}#page=${pageNum}`,
      label: `PDF · Page ${pageNum}`,
    };
  }
  if (source.kind === 'latex') {
    return { href: null, label: `LaTeX · ${anchor}` };
  }
  return { href: null, label: `Abstract · ${anchor}` };
}

export function isReportStale(report: PaperReport, paper: Paper): boolean {
  if (!report.source.paper_version || !paper.arxiv_version) return false;
  return report.source.paper_version !== paper.arxiv_version;
}
