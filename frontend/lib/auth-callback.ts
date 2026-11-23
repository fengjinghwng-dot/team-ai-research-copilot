type AuthResult = { error: { message: string } | null };
type CallbackAuth = {
  exchangeCodeForSession(code: string): Promise<AuthResult>;
  verifyOtp(params: { token_hash: string; type: 'email' }): Promise<AuthResult>;
};

export function callbackOrigin(requestUrl: string, configuredUrl = process.env.WORKSPACE_URL): string {
  // Standalone Next.js sees the container listener as its origin behind Render's proxy.
  // Use the configured public URL, never the internal 0.0.0.0 address in redirects.
  return new URL(configuredUrl || requestUrl).origin;
}

export async function authenticateCallback(params: URLSearchParams, auth: CallbackAuth): Promise<string | null> {
  if (params.has('error')) return '登录链接已过期或已使用，请重新发送登录邮件。';
  const tokenHash = params.get('token_hash');
  const code = params.get('code');
  let result: AuthResult;
  if (tokenHash && params.get('type') === 'email') {
    // Supabase's SSR email template uses a one-use token hash. Unlike PKCE codes,
    // this also works when the mailbox opens the link in a different browser.
    result = await auth.verifyOtp({ token_hash: tokenHash, type: 'email' });
  } else if (code) {
    result = await auth.exchangeCodeForSession(code);
  } else {
    return '登录链接不完整，请返回登录页重新发送邮件，并使用最新邮件中的链接。';
  }
  return result.error ? '登录链接验证失败或已过期，请重新发送登录邮件。' : null;
}
