const { test, expect } = require('@playwright/test');

test('LLM settings and solve flow', async ({ page }) => {
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));

  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
  await expect(page.getByText('钻具落断事故处置系统')).toBeVisible();
  await expect(page.getByText('Wiki 健康')).toBeVisible();

  await page.getByRole('button', { name: 'LLM 设置' }).click();
  await expect(page.getByRole('dialog', { name: 'LLM 设置' })).toBeVisible();
  await page.getByLabel('供应商', { exact: true }).selectOption('custom');
  await page.getByLabel('模型', { exact: true }).fill('qa-ui-model');
  await page.getByLabel('Base URL', { exact: true }).fill('https://llm.example.test/v1');
  await page.getByLabel('API Key', { exact: true }).fill('sk-ui-test-1234567890');
  await page.getByRole('button', { name: '保存设置' }).click();
  await expect(page.getByRole('button', { name: 'LLM 已配置' })).toBeVisible();

  await page.getByRole('button', { name: '新建会话' }).click();
  await page.getByPlaceholder('补充现场信息，或询问处置细节...').fill('某水平井钻具断落，鱼顶2450m，井斜角63度，井液密度1.18g/cm3，疑似公扣损坏，请生成打捞处置方案。');
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('已完成处置方案生成')).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('最终决策')).toBeVisible();

  const citation = page.getByText('解卡操作规程').first();
  await citation.click();
  await expect(page.getByRole('button', { name: '返回聊天' })).toBeVisible({ timeout: 10000 });

  expect(errors).toEqual([]);
});
