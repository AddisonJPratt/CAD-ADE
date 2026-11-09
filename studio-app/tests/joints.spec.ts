import { test, expect } from '@playwright/test';
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// #54: "Join these two parts with a snap-fit" on a face picked on each part is a previewed
// assembly change; kept, the assembly gate measures the fit and the joint shows in the
// assembly panel at the needs-physical-test tier.
const repoPath = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));
const FIXTURE = 'tests/fixtures/assembly_joints';
// Its own scratch folder, outside the shared test project (see assembly.spec.ts).
const scratch = mkdtempSync(join(tmpdir(), 'magic-joints-'));
const folderFor = () => join(scratch, `snap-box-${test.info().workerIndex}-${test.info().retry}`);
test.afterEach(() => rmSync(folderFor(), { recursive: true, force: true }));

test('two picks and "join with a snap-fit" preview a joint; kept, it is measured and needs a physical test', async ({ page, request }) => {
  test.setTimeout(900000);  // two full gate runs of two designs and the assembly (the kept one at Studio's default sweep), plus the preview
  const folder = folderFor();
  expect((await request.post('/api/projects', { data: { folder, from_design: repoPath(`${FIXTURE}/designs/base_block.py`) } })).ok()).toBeTruthy();
  copyFileSync(repoPath(`${FIXTURE}/designs/cap_block.py`), `${folder}/designs/cap_block.py`);
  const unjoined = readFileSync(repoPath(`${FIXTURE}/assembly.py`), 'utf8').replace('    asm.join("snap_fit", "cap", "base")\n', '');
  writeFileSync(`${folder}/assembly.py`, unjoined);
  expect((await request.post('/api/projects/versions', { data: { project: folder, message: 'Add the cap and the assembly' } })).ok()).toBeTruthy();
  const checked = await request.post('/api/runs', { data: { project: folder, wait: true, samples: 11 }, timeout: 240000 });
  expect(checked.ok(), await checked.text()).toBeTruthy();

  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', { name: 'Open project' }).click();
  const views = page.getByRole('group', { name: 'Model view' });
  await expect(views.getByRole('button', { name: 'Assembly' })).toHaveAttribute('aria-pressed', 'true', { timeout: 30000 });
  // Faces are picked on the parts, each in its print frame: from the top, the cap's top shows through
  // the base's pocket.
  await views.getByRole('button', { name: 'Parts' }).click();
  const canvas = page.getByLabel('3D model').locator('canvas');
  await expect(canvas).toBeVisible();
  const cameras = page.getByRole('group', { name: 'Camera controls' });
  const settled = async () => { await page.waitForTimeout(700); let last = await canvas.screenshot(); await expect.poll(async () => { await page.waitForTimeout(400); const next = await canvas.screenshot(); const same = next.equals(last); last = next; return same; }, { timeout: 15000 }).toBe(true); };
  // Both bodies must be loaded before the first click, or it lands on whichever came first.
  await expect(page.getByRole('group', { name: 'Bodies' }).getByRole('button')).toHaveCount(2);
  await expect(page.getByText('Loading model…')).toHaveCount(0, { timeout: 30000 });
  await cameras.getByRole('button', { name: 'Top', exact: true }).click();
  await settled();
  await expect(page.getByText('Loading model…')).toHaveCount(0);
  const at = async (fx: number, fy: number) => { const box = (await canvas.boundingBox())!; return { x: box.width * fx, y: box.height * fy }; };
  await canvas.click({ position: await at(0.5, 0.5) });
  const chips = page.getByRole('list', { name: 'Selected on the model' });
  await expect(chips).toContainText('cap block');
  // From the front, above the cap's 6 mm, the face is the base's: up and to the left of the
  // first pick, clear of its action bar.
  await cameras.getByRole('button', { name: 'Front', exact: true }).click();
  await settled();
  await canvas.click({ position: await at(0.3, 0.45), modifiers: ['Shift'] });
  await expect(chips.getByRole('listitem')).toHaveCount(2);
  await expect(chips).toContainText('base block');

  await page.getByLabel('Change request').fill('Join these two parts with a snap-fit');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Propose change' }).click();
  expect((await posted).ok()).toBeTruthy();
  const review = page.getByRole('region', { name: 'Proposed edit' });
  await expect(review).toContainText('Add a snap-fit: cap to base', { timeout: 240000 });
  await expect(review).toContainText(/PLA sliding fit, 0\.25\smm per side/);
  await expect(review).toContainText('Needs a physical test');
  // Nothing is written until the change is kept.
  expect(readFileSync(`${folder}/assembly.py`, 'utf8')).not.toContain('asm.join');
  await page.screenshot({ path: test.info().outputPath('magic-join-preview.png') });

  await page.getByRole('button', { name: 'Accept change' }).click();
  await expect(page.getByText(/Now: passed/)).toBeVisible({ timeout: 600000 });
  expect(readFileSync(`${folder}/assembly.py`, 'utf8')).toContain('asm.join("snap_fit", "cap", "base")');

  await views.getByRole('button', { name: 'Assembly' }).click();
  const joints = page.getByRole('region', { name: 'Joints' });
  await expect(joints).toContainText('Snap-fit');
  await expect(joints).toContainText('Cap to Base');
  await expect(joints).toContainText(/PLA sliding fit, 0\.25\smm per side; measured 0\.2/);
  await expect(joints).toContainText('Needs physical test');
  await page.screenshot({ path: test.info().outputPath('magic-join-assembly.png') });
});
