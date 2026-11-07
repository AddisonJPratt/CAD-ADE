import { test, expect } from '@playwright/test';

test('opens a project and inspects an older version', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await expect(page.getByRole('heading', { name: 'Version 3' })).toBeVisible();
  await expect(page.getByLabel('Material')).toHaveValue('PLA');
  await page.getByLabel('Material').selectOption('PETG');
  await expect(page.getByText('Material set to PETG for future checks.')).toBeVisible();
  await page.getByLabel('Material').selectOption('PLA');
  await expect(page.getByText('Checks failed', { exact: true })).toBeVisible();
  const currentModel = page.waitForResponse(r => r.url().includes('version-artifacts') && r.url().includes('path=') && r.ok());
  await page.getByRole('button', { name: /Version 2/ }).click();
  const currentBytes = await (await currentModel).body();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.getByText('All checks passed', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Computed checks' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Needs a physical test' })).toBeVisible();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: /Version 1/ }).click();
  await expect(page.getByRole('button', { name: 'Rebuild model' })).toBeVisible();
  const oldModel = page.waitForResponse(r => r.url().includes('version-artifacts') && r.url().includes('path=') && r.ok());
  await page.getByRole('button', { name: 'Rebuild model' }).click();
  const response = await oldModel;
  const oldBytes = await response.body();
  expect(oldBytes.length).toBeGreaterThan(100);
  expect(oldBytes.equals(currentBytes)).toBe(false);
  await expect(page.getByRole('button', { name: /Version 3/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible();
  await expect(page.getByText('All checks passed', { exact: true })).toBeVisible();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  await page.waitForTimeout(3000);
  const canvas = page.getByLabel('3D model').locator('canvas');
  const before = await canvas.screenshot();
  await page.getByText('Move camera', { exact: true }).focus();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Zoom in' }).focus();
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  const afterZoom = await canvas.screenshot();
  await page.getByRole('button', { name: 'Orbit left' }).focus();
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await canvas.screenshot()).equals(afterZoom)).toBe(false);
  await page.getByText('Move camera', { exact: true }).click();
  await page.screenshot({path: '/tmp/magic-studio-desktop.png'});
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({path: '/tmp/magic-studio-mobile.png', fullPage:true});
});

test('modes preserve the project and selected version, and Mission Control shows saved sources', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: /Version 2/ }).click();
  await page.getByRole('button', { name: 'Mission Control' }).click();
  await expect(page.getByRole('heading', { name: 'Mission Control' })).toBeVisible();
  await expect(page.locator('.version-context')).toContainText('Version 2');
  await expect(page.getByRole('heading', { name: 'Brief card' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'briefs/café.yaml' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Gate report' })).toBeVisible();
  await expect(page.locator('.expert').getByText('2 Geometry', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Design code' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Espressif ESP32-DevKitC V4' })).toBeVisible();
  await expect(page.getByText('length: 48.26 mm — datasheet-verified')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Measured test part' })).toBeVisible();
  await expect(page.getByText('width: 17.2 mm — user-measured')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'good_two_parts.py', exact: true }).last()).toBeVisible();
  await expect(page.getByText('24.0', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Make', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Make' })).toBeVisible();
  await page.getByRole('button', { name: 'Studio', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.getByLabel('Project folder')).toHaveValue(process.env.MAGIC_TEST_PROJECT!);
});

test('catalogue remains available when version details fail', async ({ page }) => {
  await page.route('**/api/projects/version-details?*', route => route.fulfill({status: 500, contentType: 'application/json', body: '{"error":"Unavailable"}'}));
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: 'Mission Control' }).click();
  await expect(page.getByRole('alert')).toContainText('Unavailable');
  await expect(page.getByRole('heading', { name: 'Measured test part' })).toBeVisible();
  await expect(page.getByText(/catalogue\.json · Modified/)).toBeVisible();
});

test('mission control explains a project without an assembly file', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: 'Mission Control' }).click();
  await expect(page.getByRole('heading', { name: 'Parts list' })).toBeVisible();
  await expect(page.getByText('This project has no assembly file.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download CSV' })).toHaveCount(0);
});

test('mission control shows the parts list derived from the assembly', async ({ page }) => {
  const list = { assembly: 'assembly.py', source_sha256: 'a'.repeat(64), rows: [
    { category: 'Printed part', item: 'Wall clip', quantity: 1, specification: 'FDM print; barrel_dia 38, clearance 0.25, clip_height 32, wall 2.4', source: 'designs/holder_clip.py', instances: ['clip'] },
    { category: 'Hardware', item: 'M3 socket-head screw, 12 mm', quantity: 2, specification: 'ISO 4762 socket head cap screw, M3, 12 mm under the head', source: 'library/standard_parts.json', instances: ['screw_1', 'screw_2'] },
    { category: 'Purchased component', item: 'ESP32 board', quantity: 1, specification: '27.94 x 48.26 x 15 mm outline', source: 'https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf', instances: ['board'] }] };
  await page.route('**/api/projects/parts-list?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) }));
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: 'Mission Control' }).click();
  const table = page.getByRole('table');
  await expect(table.getByRole('rowheader', { name: 'Purchased components' })).toBeVisible();
  await expect(table.getByRole('row', { name: /2 M3 socket-head screw, 12 mm/ })).toBeVisible();
  await expect(table.getByRole('link', { name: 'Datasheet' })).toHaveAttribute('href', /espressif/);
  const csv = page.getByRole('link', { name: 'Download CSV' });
  await expect(csv).toHaveAttribute('href', /format=csv/);
  expect(new URL(await csv.getAttribute('href')!, page.url()).searchParams.get('project')).toBe(process.env.MAGIC_TEST_PROJECT);
});
