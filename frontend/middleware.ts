import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({request});
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (process.env.NEXT_PUBLIC_USE_MOCK === 'true' || !url || !key ||
      !request.cookies.getAll().some(cookie => /^sb-.+-auth-token(?:\.\d+)?$/.test(cookie.name))) return response;
  const supabase = createServerClient(url, key, {
    cookieOptions: {maxAge: 60 * 60 * 24 * 30, sameSite: 'lax', path: '/', secure: process.env.NODE_ENV === 'production'},
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet: {name: string; value: string; options: CookieOptions}[]) {
        cookiesToSet.forEach(({name, value}) => request.cookies.set(name, value));
        response = NextResponse.next({request});
        cookiesToSet.forEach(({name, value, options}) => response.cookies.set(name, value, options));
      },
    },
  });
  try {await supabase.auth.getUser();} catch { /* Transient Auth failure is handled by the page, never an auth bypass. */ }
  response.headers.set('Cache-Control', 'private, no-store');
  return response;
}

export const config = {matcher: ['/', '/login', '/teams/:path*']};
