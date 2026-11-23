'use client';

import Link from 'next/link';
import { AlertCircle, ShieldAlert, Search } from 'lucide-react';

interface Props {
  status: number | null;
  message: string;
  onFallbackKeyword?: () => void;
  loginReturnTo?: string;
}

export function StatusBanner({ status, message, onFallbackKeyword, loginReturnTo }: Props) {
  const isAuth = status === 401;
  const isForbidden = status === 403;
  const isUnavailable = status === 503;

  return (
    <div className={`rounded-xl border p-4 text-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
      isForbidden ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-rose-50 border-rose-200 text-rose-900'
    }`}>
      <div className="flex items-start gap-2.5">
        {isForbidden ? <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
        <span>{message}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {isAuth && (
          <Link
            href={`/login${loginReturnTo ? `?returnTo=${encodeURIComponent(loginReturnTo)}` : ''}`}
            className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800"
          >
            重新登录
          </Link>
        )}
        {isUnavailable && onFallbackKeyword && (
          <button
            type="button"
            onClick={onFallbackKeyword}
            className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 inline-flex items-center gap-1"
          >
            <Search className="w-3.5 h-3.5" />改用关键词检索
          </button>
        )}
      </div>
    </div>
  );
}
