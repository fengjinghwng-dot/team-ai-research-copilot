import { redirect } from 'next/navigation';
import { isMockEnabled } from '@/lib/mock';
import { createServerSupabaseClient } from '@/lib/supabase/server';

export default async function HomePage() {
  if (isMockEnabled()) {
    redirect('/teams');
  }
  try {
    const supabase = await createServerSupabaseClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) {
      redirect('/teams');
    }
  } catch {
    // 缺少环境变量时回退到登录页提示
  }
  redirect('/login');
}
