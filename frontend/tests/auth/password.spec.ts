import { test, expect, type Page } from '@playwright/test';

const email = 'auth-fixture@example.invalid';
const password = 'Only-for-browser-tests-8472';
const teamId = '00000000-0000-4000-8000-000000000102';
async function businessApi(page: Page) {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const body = path.endsWith('/daily/preferences') ? {keywords: ['RAG'], paper_count: 20,
      conference_ratio: .3, configured: true, conference_venues: ['ICML'], conference_years: 5, latest_hours: 72, archive_days: 90} :
      path.endsWith('/daily/generation') ? {job: null} :
      path.endsWith('/available') || path.endsWith('/join-requests') ? {items: [], pending_count: 0} :
      path.endsWith('/daily') ? {day: '2026-11-24', team_must_read: [], personal: {items: [], exploration_target: 0, exploration_actual: 0}, persisted: false} :
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

test('a verified user can apply, withdraw, reapply and enter the team after approval', async ({page}) => {
  await signIn(page);
  let approved = false;
  let application: Record<string, unknown> | null = null;
  let submissions = 0;
  await page.route('**/api/v1/me', route => route.fulfill({json: {
    id: '00000000-0000-4000-8000-000000000101', email, display_name: '', email_opt_in: false,
    memberships: approved ? [{team_id: teamId, role: 'member', interests: {}}] : [],
  }}));
  await page.route('**/api/v1/teams/available', route => route.fulfill({json: {items: approved ? [] : [{id: teamId, name: '认证测试团队'}]}}));
  await page.route('**/api/v1/join-requests', route => route.fulfill({json: {items: application ? [{...application, team_name: '认证测试团队'}] : []}}));
  await page.route(`**/api/v1/teams/${teamId}/join-requests`, async route => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON()).toEqual({message: '我是新成员，研究 RAG。'});
    application = {id: `test-request-${++submissions}`, team_id: teamId, user_id: 'test-user',
      status: 'pending', message: route.request().postDataJSON().message,
      created_at: new Date().toISOString(), reviewed_at: null, reviewed_by: null};
    await route.fulfill({status: 201, json: application});
  });
  await page.route('**/api/v1/join-requests/test-request-*', async route => {
    expect(route.request().method()).toBe('DELETE');
    application = {...application!, status: 'cancelled'};
    await route.fulfill({json: application});
  });
  await page.reload();
  await page.getByLabel('申请说明：认证测试团队').fill('我是新成员，研究 RAG。');
  await page.getByRole('button', {name: '申请加入', exact: true}).click();
  await expect(page.getByRole('button', {name: '撤回申请', exact: true})).toBeVisible();
  await page.getByRole('button', {name: '撤回申请', exact: true}).click();
  await expect(page.getByText('上次申请已撤回。', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: '申请加入', exact: true}).click();
  await expect(page.getByRole('button', {name: '撤回申请', exact: true})).toBeVisible();
  approved = true; application = {...application!, status: 'approved'};
  await page.getByRole('button', {name: '刷新申请状态', exact: true}).click();
  await expect(page.getByRole('link', {name: '认证测试团队', exact: false})).toBeVisible();
  await expect(page.getByRole('heading', {name: '等待管理员加入'})).toHaveCount(0);
});

test('a signed-in user waiting for an invitation can explicitly refresh team membership', async ({page}) => {
  await signIn(page);
  let invited = false;
  await page.route('**/api/v1/me', async route => route.fulfill({json: {
    id: '00000000-0000-4000-8000-000000000101', email, display_name: '', email_opt_in: false,
    memberships: invited ? [{team_id: teamId, role: 'member', interests: {}}] : [],
  }}));
  await page.reload();
  await expect(page.getByRole('heading', {name: '等待管理员加入'})).toBeVisible();
  invited = true;
  await page.getByRole('button', {name: '检查邀请', exact: true}).click();
  await expect(page.getByRole('link', {name: '认证测试团队', exact: false})).toBeVisible();
  await expect(page.getByRole('heading', {name: '等待管理员加入'})).toHaveCount(0);
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

test('a member can refresh a shared daily edition and see the correct exploration percentage', async ({page}) => {
  await signIn(page);
  let ready = false;
  await page.route(`**/api/v1/teams/${teamId}/daily*`, async route => {
    if (!new URL(route.request().url()).pathname.endsWith('/daily')) return route.fallback();
    const items = Array.from({length: 5}, (_, index) => ({paper_id: `test-paper-${index}`,
      title: `共享日报论文 ${index}`, abstract: '摘要', source_url: 'https://arxiv.org/abs/2611.00001',
      score: .8, reason: '团队方向', votes: 0, claims: 0, analysis_state: 'metadata_only', is_exploration: index === 4}));
    await route.fulfill({json: {day: '2026-11-24', team_must_read: [],
      personal: {items: ready ? items : [], exploration_target: ready ? 1 : 0, exploration_actual: ready ? 1 : 0},
      persisted: ready, message: ready ? '已复用该日团队日报生成你的推荐，未新增 AI 调用。' : '日报尚未生成'}});
  });
  await page.getByRole('link', {name: '认证测试团队', exact: false}).click();
  await expect(page.getByRole('heading', {name: '该日期日报尚未生成'})).toBeVisible();
  ready = true;
  await page.getByRole('button', {name: '刷新日报', exact: true}).click();
  await expect(page.getByText('共享日报论文 0', {exact: true})).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('已复用该日团队日报生成你的推荐，未新增 AI 调用。');
  await expect(page.getByText('（目标 20%）', {exact: false})).toBeVisible();
});
