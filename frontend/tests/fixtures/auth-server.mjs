// Loopback-only test provider. Its fake HS256 tokens are never accepted by the real ES256 backend.
import http from 'node:http';

const email = 'auth-fixture@example.invalid';
const initialPassword = 'Only-for-browser-tests-8472';
let password = initialPassword, refreshes = 0, updates = 0;
const tokens = new Set();
const user = {id: '00000000-0000-4000-8000-000000000101', aud: 'authenticated', role: 'authenticated', email,
  created_at: '2026-01-01T00:00:00Z', email_confirmed_at: '2026-01-01T00:00:00Z',
  app_metadata: {provider: 'email', providers: ['email']}, user_metadata: {}, identities: []};
const encoded = value => Buffer.from(JSON.stringify(value)).toString('base64url');
function session() {
  const now = Math.floor(Date.now() / 1000);
  const token = `${encoded({alg: 'HS256', typ: 'JWT'})}.${encoded({sub: user.id, email, aud: 'authenticated', iat: now, exp: now + 3600})}.${Buffer.from('only-a-test-signature').toString('base64url')}`;
  tokens.add(token);
  return {access_token: token, token_type: 'bearer', expires_in: 3600, expires_at: now + 3600,
    refresh_token: 'only-a-test-refresh-token', user};
}
const server = http.createServer(async (request, response) => {
  response.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:3102');
  response.setHeader('Access-Control-Allow-Headers', 'authorization, apikey, content-type, x-client-info, x-supabase-api-version');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS');
  response.setHeader('Content-Type', 'application/json');
  const send = (status, body) => {response.writeHead(status); response.end(body === undefined ? '' : JSON.stringify(body));};
  if (request.method === 'OPTIONS') {send(204); return;}
  const url = new URL(request.url, 'http://127.0.0.1:54330');
  let raw = ''; for await (const part of request) raw += part;
  const body = raw ? JSON.parse(raw) : {};
  if (url.pathname === '/__test/reset') {password = initialPassword; refreshes = 0; updates = 0; tokens.clear(); send(200, {ok: true}); return;}
  if (url.pathname === '/__test/metrics') {send(200, {refreshes, updates}); return;}
  if (url.pathname === '/auth/v1/token') {
    if (url.searchParams.get('grant_type') === 'password' && body.email === email && body.password === password) {
      send(200, session()); return;
    }
    if (url.searchParams.get('grant_type') === 'refresh_token' && body.refresh_token === 'only-a-test-refresh-token') {
      refreshes++; send(200, session()); return;
    }
    send(400, {error_code: 'invalid_credentials', msg: 'Invalid login credentials'}); return;
  }
  if (url.pathname === '/auth/v1/logout') {tokens.clear(); send(204); return;}
  if (url.pathname === '/auth/v1/user' && tokens.has((request.headers.authorization || '').replace('Bearer ', ''))) {
    if (request.method === 'PUT' && typeof body.password === 'string') {
      if (body.password.length < 8) {send(422, {error_code: 'weak_password', msg: 'Weak password'}); return;}
      password = body.password; updates++;
    }
    send(200, user); return;
  }
  send(401, {error_code: 'bad_jwt', msg: 'Test session required'});
});
server.listen(54330, '127.0.0.1', () => console.log('AUTH_FIXTURE_READY'));
process.on('SIGTERM', () => server.close(() => process.exit(0)));
