import { NextResponse } from 'next/server';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import { sanitizeReturnTo } from '@/lib/evidence';
import { authenticateCallback, callbackOrigin } from '@/lib/auth-callback';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const origin = callbackOrigin(request.url);
  const returnTo = sanitizeReturnTo(searchParams.get('returnTo'), '/teams');

  let error: string | null;
  try {
    const supabase = await createServerSupabaseClient();
    error = await authenticateCallback(searchParams, supabase.auth);
  } catch {
    error = '登录验证暂时失败，请稍后重新发送登录邮件。';
  }
  const destination = error ? `/login?error=${encodeURIComponent(error)}` : returnTo;
  return NextResponse.redirect(`${origin}${destination}`, {
    headers: { 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store' },
  });
}
