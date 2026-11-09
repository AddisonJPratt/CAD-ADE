import { test, expect } from '@playwright/test';

// A real 1×1 PNG: the browser decodes and downsizes it before it is sent.
const PHOTO = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');

// Make mode (#14): Ask → Make (every gate, live) → Prove → Shelf → Studio, on a real holder.
// Projects and calibration land in MAGIC_PROJECTS_HOME and the print log in MAGIC_PRINT_LOG (tests/run.sh).
test('makes a holder, proves it, records a print and finds it on the Shelf', async ({ page, request }) => {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Workspace modes' }).getByRole('button', { name: 'Make' }).click();
  await expect(page.getByRole('heading', { name: 'Make a wall holder' })).toBeVisible();

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

  // Before a print, the physical fit is only a claim that needs testing.
  await expect(page.getByRole('region', { name: 'Evidence' })).toContainText('Needs a physical test');
  await expect(page.getByRole('region', { name: 'Evidence' })).not.toContainText('Physically tested');

  // Recording a print (#15): rate each fit in a tap, then save; the primary fit is required.
  const save = page.getByRole('button', { name: 'Save result' });
  await expect(save).toBeDisabled();
  const grip = page.getByRole('group', { name: 'Clip around the object' });
  const screws = page.getByRole('group', { name: 'Screws in the mounting holes' });
  await screws.getByRole('button', { name: 'Perfect' }).click();
  await expect(save).toBeDisabled();
  await grip.getByRole('button', { name: 'Too tight' }).click();
  await expect(grip.getByRole('button', { name: 'Too tight' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText('moves the fit gap for your next holder by 0.2 mm', { exact: false })).toBeVisible();
  // Optional caliper readings of named features, against their modelled size, and a photo.
  await page.getByText('Add caliper measurements').click();
  await expect(page.getByText('Modelled 42.5 mm')).toBeVisible();
  await page.getByLabel('Clip bore').fill('70000');
  await save.click();
  await expect(page.getByRole('alert').filter({ hasText: 'Enter the clip bore in millimetres, up to 1000.' })).toBeVisible();
  await expect(page.getByLabel('Clip bore')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByLabel('Clip bore')).toBeFocused();
  await page.getByLabel('Clip bore').fill('42.31');
  await expect(page.getByRole('alert').filter({ hasText: 'Enter the clip bore' })).toHaveCount(0);
  await page.getByLabel('Add a photo').setInputFiles({ name: 'print.png', mimeType: 'image/png', buffer: PHOTO });
  await expect(page.getByRole('img', { name: 'Your photo of this print' })).toBeVisible();
  await page.getByRole('button', { name: 'Remove photo' }).click();
  await expect(page.getByLabel('Add a photo')).toBeFocused();
  await page.getByLabel('Add a photo').setInputFiles({ name: 'print.png', mimeType: 'image/png', buffer: PHOTO });
  await page.screenshot({ path: test.info().outputPath('make-print-form-desktop.png'), fullPage: true });
  await save.click();
  await expect(page.getByText('Recorded:')).toContainText('Too tight');
  await expect(page.getByText(/moves up by 0.2 mm, to 0.45 mm per side/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Make an adjusted version' })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Caliper measurements' })).toContainText('42.31');
  await expect(page.getByRole('table', { name: 'Caliper measurements' })).toContainText('−0.19');
  await expect(page.getByRole('img', { name: 'Photo recorded with this print' })).toBeVisible();
  // The matching claims are now physically tested.
  const evidence = page.getByRole('region', { name: 'Evidence' });
  await expect(evidence).toContainText('Physically tested');
  await expect(evidence).toContainText('Clip around the object: too tight');
  await expect(evidence).toContainText('Screws in the mounting holes: perfect');
  await expect(evidence).not.toContainText('Needs a physical test');

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
  await page.reload();
  await page.getByRole('navigation', { name: 'Workspace modes' }).getByRole('button', { name: 'Make' }).click();
  await page.getByRole('navigation', { name: 'Make steps' }).getByRole('button', { name: 'Shelf' }).click();
  await item.getByText('2 versions').click();
  await item.getByRole('button', { name: 'Proof: Bike pump holder version 2' }).click();
  await expect(page.getByRole('heading', { name: 'Your print' })).toBeVisible();
  expect(await page.locator('.mk').evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0);
  await expect(page.locator('.mk-part[data-ready]')).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({ path: test.info().outputPath('make-prove-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole('navigation', { name: 'Make steps' }).getByRole('button', { name: 'Shelf' }).click();
  await page.getByRole('button', { name: 'Open in Studio: Bike pump holder' }).click();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.locator('.project-switch summary')).toHaveText('Bike pump holder');
  // Studio's verdict and evidence show the same claims as physically tested.
  await expect(page.getByText('A real print was recorded: 1 of 2 rated fits were perfect.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Full evidence' }).click();
  const tested = page.getByRole('region', { name: 'Physically tested' });
  await expect(tested).toContainText('Physical fit: Clip around the object');
  await expect(tested).toContainText('Measured: Clip bore');
});

// #102: Ask says Make only does wall holders and sends anything else to Studio's New project form.
test('Ask points anything that is not a holder to New project in Studio', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('navigation', { name: 'Workspace modes' }).getByRole('button', { name: 'Make' }).click();
  await expect(page.getByText('Make only does wall holders for now')).toBeVisible();
  await page.getByRole('button', { name: 'New project', exact: true }).click();
  const form = page.getByRole('form', { name: 'New project' });
  await expect(form).toBeVisible();
  await expect(form.getByLabel('Name')).toBeFocused();
  await expect(form.getByRole('radio').first()).toBeChecked();
});
