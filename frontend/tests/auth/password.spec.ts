import { test, expect, type Page } from '@playwright/test';

const email = 'auth-fixture@example.invalid';
const password = 'Only-for-browser-tests-8472';
const teamId = '00000000-0000-4000-8000-000000000102';
async function businessApi(page: Page) {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/daily') ? {day: '2026-11-24', team_must_read: [], personal: {items: [], exploration_target: 0, exploration_actual: 0}, persisted: false} :
      path.endsWith('/me') ? {id: '00000000-0000-4000-8000-000000000101', email,
      display_name: '认证测试用户', email_opt_in: false, memberships: [{team_id: teamId, role: 'member', interests: {}}]} :
      {team: {id: teamId, name: '认证测试团队', daily_token_budget: 10000}, role: 'member', topics: [], interests: {}, exploration_ratio: .2};
    await route.fulfill({json: body});
  });
}
async function signIn(page: Page) {
  await businessApi(page);
  await page.goto('/login');
  await page.getByLabel('邮箱地址', {exact: true}).fill(email);
  await page.getByLabel('工作台密码', {exact: true}).fill(password);
  await page.getByRole('button', {name: '登录工作台', exact: true}).click();
  await expect(page).toHaveURL(/\/teams$/);
  await expect(page.getByRole('heading', {name: '选择你的科研团队'})).toBeVisible();
}
test.beforeEach(async ({request}) => {await request.post('http://127.0.0.1:54330/__test/reset');});

test('password login reports invalid credentials and keeps email fallback available', async ({page}) => {
  await page.goto('/login');
  await page.getByLabel('邮箱地址', {exact: true}).fill(email);
  await page.getByLabel('工作台密码', {exact: true}).fill('incorrect-test-password');
  await page.getByRole('button', {name: '登录工作台', exact: true}).click();
  await expect(page.getByText('邮箱或密码不正确。尚未设置密码时，请切换到邮件登录。')).toBeVisible();
  await page.getByRole('button', {name: '邮件登录 / 首次注册', exact: true}).click();
  await expect(page.getByRole('button', {name: '发送登录链接', exact: true})).toBeVisible();
});

test('verified user can set a password, sign out and sign in with the new password', async ({page, request}) => {
  await signIn(page);
  await page.getByText('设置或修改登录密码', {exact: true}).click();
  await page.getByLabel('新密码', {exact: true}).fill('Updated-only-test-password-2026');
  await page.getByLabel('再次输入新密码', {exact: true}).fill('different-test-password');
  await page.getByRole('button', {name: '保存登录密码'}).click();
  await expect(page.getByText('两次输入的密码不一致。')).toBeVisible();
  await page.getByLabel('再次输入新密码', {exact: true}).fill('Updated-only-test-password-2026');
  await page.getByRole('button', {name: '保存登录密码'}).click();
  await expect(page.getByText('密码已保存。下次可以直接使用邮箱和密码登录，无需再点邮件。')).toBeVisible();
  expect((await (await request.get('http://127.0.0.1:54330/__test/metrics')).json()).updates).toBe(1);
  await page.getByRole('link', {name: '认证测试团队', exact: false}).click();
  await page.getByRole('button', {name: /退出/}).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('邮箱地址', {exact: true}).fill(email);
  await page.getByLabel('工作台密码', {exact: true}).fill('Updated-only-test-password-2026');
  await page.getByRole('button', {name: '登录工作台', exact: true}).click();
  await expect(page).toHaveURL(/\/teams$/);
});

test('persistent cookies survive a browser restart and middleware refreshes an expired access token', async ({page, context, browser, request}) => {
  await signIn(page);
  const saved = await context.storageState();
  const cookie = saved.cookies.find(item => /^sb-.+-auth-token$/.test(item.name));
  expect(cookie).toBeTruthy();
  expect(cookie!.expires).toBeGreaterThan(Date.now() / 1000 + 86400);
  const data = JSON.parse(Buffer.from(cookie!.value.replace(/^base64-/, ''), 'base64url').toString('utf-8'));
  const parts = data.access_token.split('.');
  const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf-8'));
  payload.exp = Math.floor(Date.now() / 1000) - 3600;
  parts[1] = Buffer.from(JSON.stringify(payload)).toString('base64url');
  data.access_token = parts.join('.'); data.expires_at = payload.exp;
  cookie!.value = 'base64-' + Buffer.from(JSON.stringify(data)).toString('base64url');
  const restored = await browser.newContext({storageState: saved});
  try {
    const nextPage = await restored.newPage();
    await businessApi(nextPage);
    await nextPage.goto('/');
    await expect(nextPage).toHaveURL(/\/teams$/);
    expect((await (await request.get('http://127.0.0.1:54330/__test/metrics')).json()).refreshes).toBeGreaterThan(0);
    const updated = (await restored.cookies()).find(item => item.name === cookie!.name);
    expect(updated?.value).not.toBe(cookie!.value);
  } finally {await restored.close();}
});
