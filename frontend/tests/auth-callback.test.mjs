import test from 'node:test';
import assert from 'node:assert/strict';
import { authenticateCallback, callbackOrigin } from '../lib/auth-callback.ts';
import { sanitizeReturnTo } from '../lib/evidence.ts';

test('Render callback redirects to the configured public host', () => {
  assert.equal(callbackOrigin('https://0.0.0.0:10000/auth/callback',
    'https://team-ai-research-copilot.onrender.com'), 'https://team-ai-research-copilot.onrender.com');
});

test('return destinations reject external hosts and control-character normalization tricks', () => {
  assert.equal(sanitizeReturnTo('/teams?day=2026-11-24'), '/teams?day=2026-11-24');
  for (const path of ['https://outside.invalid', '//outside.invalid', '/\\outside.invalid', '/\t/outside.invalid', '/\0outside']) {
    assert.equal(sanitizeReturnTo(path), '/teams');
  }
});

test('SSR email token is verified without a PKCE exchange', async () => {
  const auth = {
    verifyOtp: async (params) => {
      assert.deepEqual(params, { token_hash: 'test-placeholder', type: 'email' });
      return { error: null };
    },
    exchangeCodeForSession: async () => assert.fail('Email token must not be treated as an OAuth code'),
  };
  assert.equal(await authenticateCallback(new URLSearchParams('token_hash=test-placeholder&type=email'), auth), null);
});

test('OAuth codes still use the PKCE exchange', async () => {
  const auth = {
    verifyOtp: async () => assert.fail('OAuth code must not be treated as an email token'),
    exchangeCodeForSession: async (code) => {
      assert.equal(code, 'test-placeholder');
      return { error: null };
    },
  };
  assert.equal(await authenticateCallback(new URLSearchParams('code=test-placeholder'), auth), null);
});

test('missing or expired links never authenticate, and errors do not expose token content', async () => {
  const auth = {
    verifyOtp: async () => ({ error: { message: 'internal response containing a sensitive placeholder' } }),
    exchangeCodeForSession: async () => assert.fail('No code was supplied'),
  };
  assert.match(await authenticateCallback(new URLSearchParams(), auth), /登录链接不完整/);
  assert.match(await authenticateCallback(new URLSearchParams('error=access_denied&error_code=otp_expired'), auth), /已过期/);
  const message = await authenticateCallback(new URLSearchParams('token_hash=test-placeholder&type=email'), auth);
  assert.match(message, /验证失败/);
  assert.ok(!message.includes('sensitive'));
});
