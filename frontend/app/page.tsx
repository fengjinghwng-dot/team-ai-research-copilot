import { redirect } from 'next/navigation';
import { isMockEnabled } from '@/lib/mock';
import { createServerSupabaseClient } from '@/lib/supabase/server';

export default async function HomePage() {
  if (isMockEnabled()) {
    redirect('/teams');
  }
  let signedIn = false;
  try {
    const supabase = await createServerSupabaseClient();
    const { data } = await supabase.auth.getUser();
    signedIn = Boolean(data.user);
  } catch {
    // 缺少环境变量时回退到登录页提示
  }
  redirect(signedIn ? '/teams' : '/login');
}
