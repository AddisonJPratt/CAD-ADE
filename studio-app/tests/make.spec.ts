import { test, expect } from '@playwright/test';

// Make mode (#14): Ask → Make (every gate, live) → Prove → Shelf → Studio, on a real holder.
// Projects and calibration land in MAGIC_PROJECTS_HOME and the print log in MAGIC_PRINT_LOG (tests/run.sh).
test('makes a holder, proves it, records a print and finds it on the Shelf', async ({ page, request }) => {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Workspace modes' }).getByRole('button', { name: 'Make' }).click();
  await expect(page.getByRole('heading', { name: 'What are we holding?' })).toBeVisible();

  // Ask refuses out-of-range measurements with the engine's own message.
  await page.getByLabel('Object name').fill('Bike pump');
  await page.getByLabel('Length').fill('250');
  await page.getByLabel('Diameter').fill('70');
  await page.getByRole('button', { name: 'Make my holder' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Diameter must be between 30 and 50 mm.' })).toBeVisible();
  await expect(page.getByLabel('Diameter')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByLabel('Diameter')).toBeFocused();

  await page.getByLabel('Diameter').fill('42');
  await page.getByRole('button', { name: 'Make my holder' }).click();
  await expect(page.getByRole('heading', { name: 'Making the Bike pump holder' })).toBeVisible();
  await expect(page.getByText('The design builds from its own settings')).toBeVisible();

  // Prove: only a fully checked version offers the print file.
  await expect(page.getByRole('heading', { name: 'Bike pump holder', exact: true, level: 1 })).toBeVisible({ timeout: 150000 });
  await expect(page.getByRole('heading', { name: 'Ready to print' })).toBeVisible();
  await expect(page.getByText('Sized for 42 mm diameter', { exact: false })).toBeVisible();
  await expect(page.getByRole('img', { name: /The checked Bike pump holder/ })).toHaveAttribute('data-ready', 'true', { timeout: 20000 });
  await page.getByText('Engineering render').click();
  await expect(page.getByRole('img', { name: 'Harness check render of the Bike pump holder' })).toBeVisible();
  const download = page.getByRole('link', { name: 'Download print file (STL)' });
  const stl = await request.get(await download.getAttribute('href') as string);
  expect(stl.ok()).toBeTruthy();
  expect((await stl.body()).length).toBeGreaterThan(1000);
  await page.screenshot({ path: test.info().outputPath('make-prove-desktop.png'), fullPage: true });

  // Recording a fit is deliberate: choose, then save.
  const save = page.getByRole('button', { name: 'Save result' });
  await expect(save).toBeDisabled();
  await page.getByRole('group', { name: 'Fit result' }).getByRole('button', { name: 'Too tight' }).click();
  await expect(page.getByText('moves the fit gap for your next holder by 0.2 mm', { exact: false })).toBeVisible();
  await save.click();
  await expect(page.getByText('Recorded:')).toContainText('Too tight');
  await expect(page.getByText(/moves up by 0.2 mm, to 0.45 mm per side/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Make an adjusted version' })).toBeVisible();

  // Shelf: the project with its version history and print result; it opens in Studio.
  await page.getByRole('navigation', { name: 'Make steps' }).getByRole('button', { name: 'Shelf' }).click();
  const item = page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: 'Bike pump holder', exact: true, level: 2 }) });
  await expect(item).toContainText('Last print: Too tight (version 2)');
  await item.getByText('2 versions').click();
  await expect(item.getByText('Sized for Bike pump: 42 mm diameter')).toBeVisible();
  await expect(item.getByText('Created from holder_clip')).toBeVisible();
  await item.getByRole('button', { name: 'Proof: Bike pump holder version 2' }).click();
  await expect(page.getByRole('heading', { name: 'Your print' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.mk-part[data-ready]')).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: test.info().outputPath('make-prove-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole('navigation', { name: 'Make steps' }).getByRole('button', { name: 'Shelf' }).click();
  await page.getByRole('button', { name: 'Open in Studio: Bike pump holder' }).click();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.locator('.project-switch summary')).toHaveText('Bike pump holder');
});
