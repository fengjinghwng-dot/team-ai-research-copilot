'use client';

import { ApiError, createCopilotClient } from './contracts/api';
import { createClient } from './supabase/client';
import { createMockCopilotClient, isMockEnabled } from './mock';

export { ApiError };

export function getBrowserCopilotClient() {
  if (isMockEnabled()) {
    return createMockCopilotClient();
  }
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error('缺少 NEXT_PUBLIC_API_BASE_URL 环境变量配置');
  }
  const supabase = createClient();
  return createCopilotClient(baseUrl, async () => {
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  });
}

export function formatApiError(err: unknown): { status: number | null; message: string } {
  if (err instanceof ApiError) {
    if (err.status === 401) return { status: 401, message: '登录状态已失效，请重新登录。' };
    if (err.status === 403) return { status: 403, message: '无权限执行此操作或访问该页面。' };
    if (err.status === 404) return { status: 404, message: '当前团队不存在该记录。' };
    if (err.status === 409) {
      return { status: 409, message: typeof err.detail === 'string' ? err.detail : '操作冲突，已自动刷新最新状态。' };
    }
    if (err.status === 422) {
      if (Array.isArray(err.detail)) {
        const msgs = err.detail.map((item: { loc?: unknown[]; msg?: string }) =>
          `${Array.isArray(item.loc) ? item.loc.join('.') : '字段'}: ${item.msg || '格式错误'}`
        );
        return { status: 422, message: `提交字段有误：${msgs.join('；')}` };
      }
      return { status: 422, message: typeof err.detail === 'string' ? err.detail : '输入字段校验失败。' };
    }
    if (err.status === 503) {
      return { status: 503, message: typeof err.detail === 'string' ? err.detail : '服务暂不可用，请稍后重试。' };
    }
    return { status: err.status, message: typeof err.detail === 'string' ? err.detail : `请求失败 (${err.status})` };
  }
  if (err instanceof Error) {
    return { status: null, message: err.message };
  }
  return { status: null, message: '发生未知错误' };
}
