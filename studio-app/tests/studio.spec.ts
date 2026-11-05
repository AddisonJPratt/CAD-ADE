import { test, expect } from '@playwright/test';

test('opens a project and inspects an older version', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.getByText('All checks passed', { exact: true })).toBeVisible();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  const oldModel = page.waitForResponse(r => r.url().includes('version-artifacts') && r.url().includes('path=') && r.ok());
  await page.getByRole('button', { name: /Version 1/ }).click();
  const response = await oldModel;
  expect((await response.body()).length).toBeGreaterThan(100);
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible();
  await expect(page.getByText('All checks passed', { exact: true })).toBeVisible();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  await page.waitForTimeout(3000);
  await page.screenshot({path: '/tmp/magic-studio-desktop.png'});
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({path: '/tmp/magic-studio-mobile.png', fullPage:true});
});
