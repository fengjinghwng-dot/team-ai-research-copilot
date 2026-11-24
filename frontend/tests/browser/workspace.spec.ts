import { test, expect } from '@playwright/test';

const team = '/teams/demo-team-0001';

test('admin can rename a team and see the new name in navigation and team selection', async ({page}) => {
  await page.goto(`${team}/admin`);
  const input = page.getByLabel('团队名称', {exact: true});
  await expect(input).toHaveValue('AI Research Lab (演示团队)');
  await input.fill('协作研究组');
  await page.getByRole('button', {name: '保存团队配置', exact: true}).click();
  await expect(page.getByText('团队配置已更新。')).toBeVisible();
  await expect(page.getByRole('banner').getByRole('link', {name: '协作研究组 AI Research Copilot'})).toBeVisible();
  await page.getByRole('link', {name: '切换团队', exact: true}).click();
  await expect(page.getByRole('link', {name: /协作研究组/})).toHaveAttribute('href', team);
});

test('admin approves an application and the member list updates', async ({page}) => {
  await page.goto(`${team}/admin`);
  await expect(page.getByText('演示申请人 · applicant@example.invalid', {exact: true})).toBeVisible();
  await expect(page.getByText('研究检索增强生成，希望加入每周论文讨论。')).toBeVisible();
  await page.getByRole('button', {name: '通过', exact: true}).click();
  await expect(page.getByText('暂无待处理的入组申请')).toBeVisible();
  await expect(page.getByText('已通过申请，对方现在可以进入团队。')).toBeVisible();
  await expect(page.getByRole('combobox', {name: '演示申请人的角色'})).toHaveValue('member');
});

test('admin can reject an application and disable the discovery setting', async ({page}) => {
  await page.goto(`${team}/admin`);
  await page.getByRole('button', {name: '拒绝', exact: true}).click();
  await expect(page.getByText('已拒绝这份申请。')).toBeVisible();
  await expect(page.getByRole('combobox', {name: '演示申请人的角色'})).toHaveCount(0);
  const toggle = page.getByRole('checkbox', {name: /允许成员搜索本团队并申请加入/});
  await toggle.uncheck();
  await page.getByRole('button', {name: '保存团队配置'}).click();
  await expect(page.getByText('团队配置已更新。')).toBeVisible();
  await expect(toggle).not.toBeChecked();
});

test('reading state, private notes and library filters work in explicit demo mode', async ({page}) => {
  await page.goto(`${team}/papers/demo-paper-metaonly`);
  await expect(page.getByText('当前处于独立 Mock 演示模式', {exact: false})).toBeVisible();
  await expect(page.getByText('尚无 AI 解读', {exact: false})).toBeVisible();
  await page.getByRole('button', {name: '收藏论文', exact: true}).click();
  await expect(page.getByRole('button', {name: '已收藏', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', {name: '标为已读', exact: true}).click();
  await expect(page.getByRole('button', {name: '已读', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await page.getByLabel('个人笔记（仅自己可见）').fill('我的研究笔记 <script>不会执行</script>');
  await page.getByRole('button', {name: '保存个人笔记'}).click();
  await expect(page.getByRole('button', {name: '保存个人笔记'})).toBeDisabled();
  await page.getByRole('link', {name: '团队知识库', exact: true}).click();
  await page.getByLabel('只看我的收藏').check();
  await expect(page.getByText('共 1 篇', {exact: true})).toBeVisible();
  await page.getByLabel('只看未读').check();
  await expect(page.getByText('没有符合当前条件的论文。')).toBeVisible();
});

test('admin can create and revoke an email-bound invitation and inspect integration readiness', async ({page}) => {
  await page.goto(`${team}/admin`);
  await expect(page.getByRole('heading', {name: '服务接入状态'})).toBeVisible();
  await expect(page.getByRole('heading', {name: '费用与预算'})).toBeVisible();
  await page.getByLabel('邀请成员邮箱').fill('teammate@example.invalid');
  await page.getByRole('button', {name: '创建邀请', exact: true}).click();
  await expect(page.getByText('teammate@example.invalid · 等待入组', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: '撤销邀请', exact: true}).click();
  await expect(page.getByText('teammate@example.invalid · 已撤销', {exact: true})).toBeVisible();
});

test('member sees a permission error on admin page, and reading list can be exported', async ({page}) => {
  await page.addInitScript(() => localStorage.setItem('copilot_mock_role', 'member'));
  await page.goto(`${team}/admin`);
  await expect(page.getByText('当前账号为普通成员，无权限访问团队管理后台。')).toBeVisible();
  await expect(page.getByRole('link', {name: '管理后台', exact: true})).toHaveCount(0);
  await page.goto(`${team}/meetings`);
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: '下载 Markdown'}).click();
  expect((await download).suggestedFilename()).toMatch(/team-reading-list-.*\.md$/);
});

test('discussion can be promoted into the shared idea backlog', async ({page}) => {
  await page.goto(`${team}/papers/demo-paper-metaonly`);
  await page.getByPlaceholder('输入团队批注或讨论内容（纯文本安全渲染）...').fill('对照实验：固定检索预算比较两种策略。');
  await page.getByRole('button', {name: '发布批注', exact: true}).click();
  await expect(page.getByText('对照实验：固定检索预算比较两种策略。', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: /转.*Idea/}).first().click();
  await page.getByPlaceholder('简明概括改进方向').fill('检索预算对照实验');
  await page.getByPlaceholder('写明 Baseline、评测指标与可证伪条件').fill('同一数据集固定预算，对照两种检索方法的准确率。');
  await page.getByRole('button', {name: '保存到团队灵感池'}).click();
  await page.getByRole('link', {name: '灵感池', exact: true}).click();
  await expect(page.getByText('检索预算对照实验', {exact: true})).toBeVisible();
});
