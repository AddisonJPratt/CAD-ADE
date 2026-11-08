// Outline (lasso), note pin and measure tools in the real Studio (#26), on the stepped-blocks fixture:
// a riser standing on a wider base, whose riser height the geometry gate measures.
import { test, expect, type Page, type Locator } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// Its own project outside MAGIC_TEST_PROJECT, so this file can run beside studio.spec.ts.
const folder = join(mkdtempSync(join(tmpdir(), 'magic-tools-')), 'stepped');
const source = decodeURIComponent(new URL('../../tests/fixtures/stepped_blocks.py', import.meta.url).pathname);
test.describe.configure({ mode: 'serial' });

async function openProject(page: Page) {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', { name: 'Open project' }).click();
  const canvas = page.getByLabel('3D model').locator('canvas');
  await expect(canvas).toBeVisible({ timeout: 30000 });  // software WebGL: the first model load can take a while
  return canvas;
}
/** Camera presets animate: wait until two consecutive frames agree. */
async function settled(page: Page, canvas: Locator) {
  await page.waitForTimeout(700); let last = await canvas.screenshot();
  await expect.poll(async () => { await page.waitForTimeout(400); const next = await canvas.screenshot(); const same = next.equals(last); last = next; return same; }, { timeout: 15000 }).toBe(true);
}
async function topView(page: Page, canvas: Locator) {
  // Let the opening fit finish first: drei's Bounds animation, still running, would pull the camera back off Top.
  await settled(page, canvas);
  await page.getByRole('group', { name: 'Camera controls' }).getByRole('button', { name: 'Top', exact: true }).click();
  await settled(page, canvas);
  const box = (await canvas.boundingBox())!;
  return (fx: number, fy: number) => ({ x: box.width * fx, y: box.height * fy });
}

let version = '';
let gateMeasured = 0;

test('setup: the fixture is checked and the gate measures the riser height', async ({ request }) => {
  test.setTimeout(240000);
  expect((await request.post('/api/projects', { data: { folder, from_design: source } })).ok()).toBeTruthy();
  const run = await request.post('/api/runs', { data: { project: folder, wait: true, samples: 12 }, timeout: 200000 });
  expect(run.ok(), await run.text()).toBeTruthy();
  expect((await run.json()).verdict.pass).toBe(true);
  const versions = await (await request.get(`/api/projects/versions?project=${encodeURIComponent(folder)}`)).json();
  version = versions.versions[0].id;
  // The gate's own report, saved with the version: what the measure tool must agree with.
  const report = await (await request.get(`/api/projects/version-artifacts?${new URLSearchParams({ project: folder, version, path: 'stepped_blocks/report.json' })}`)).json();
  gateMeasured = report.geometry.dimensions.find((d: { name: string }) => d.name === 'riser_height').measured;
  expect(gateMeasured).toBeCloseTo(13.5, 6);
});

test('the measure tool reads the gap between two faces as the gate measured it, with the angle', async ({ page }) => {
  const canvas = await openProject(page);
  const at = await topView(page, canvas);
  await page.getByRole('button', { name: 'Measure distance and angle' }).click();
  const hint = page.locator('.select-hint');
  await expect(hint).toHaveText(/Click the first face/);
  // The riser's top is the middle of the top view; the base's ledge is somewhere between it and the canvas edge.
  let reading = '';
  for (const fx of [0.33, 0.3, 0.27, 0.36, 0.24, 0.39, 0.21]) {
    await canvas.click({ position: at(0.5, 0.5) });
    await expect(hint).toHaveText(/Click the second face/);
    await canvas.click({ position: at(fx, 0.5) });
    reading = (await hint.textContent()) || '';
    if (reading.startsWith('Gap between parallel faces')) break;
  }
  // One decimal, as on the model; parallel faces need no angle in the words.
  const match = reading.match(/^Gap between parallel faces ([\d.]+) mm · click to measure again$/);
  expect(match, reading).not.toBeNull();
  expect(Math.abs(Number(match![1]) - gateMeasured)).toBeLessThanOrEqual(0.1);
  await expect(page.locator('.dimension-label')).toHaveText(`${gateMeasured.toFixed(1)} mm`);
  // Both picks ride in the composer like any selection; Escape leaves the tool.
  await expect(page.getByRole('list', { name: 'Selected on the model' }).getByRole('listitem')).toHaveCount(2);
  await page.screenshot({ path: test.info().outputPath('magic-measure.png') });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Measure distance and angle' })).toHaveAttribute('aria-pressed', 'false');

  // The measurement and its angle reach the agent.
  await page.getByLabel('Change request').fill('riser_height 14');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Propose change' }).click();
  const proposal = await (await posted).json();
  expect(proposal.selection.measurement.kind).toBe('gap between parallel faces');
  expect(Math.abs(proposal.selection.measurement.value - gateMeasured)).toBeLessThanOrEqual(0.1);
  expect(proposal.selection.measurement.angle).toBe(0);
  expect(proposal.selection.pins).toEqual([]);
  await expect(page.getByRole('button', { name: 'Reject change' })).toBeEnabled({ timeout: 120000 });
  await page.getByRole('button', { name: 'Reject change' }).click();
  await expect(page.getByRole('region', { name: 'Proposed edit' })).toHaveCount(0);
});

test('a note pin persists with the version and is sent to the agent', async ({ page, request }) => {
  const canvas = await openProject(page);
  const at = await topView(page, canvas);
  await page.getByRole('button', { name: 'Pin a note' }).click();
  await canvas.click({ position: at(0.5, 0.5) });
  const draft = page.getByRole('form', { name: 'New note' });
  await expect(draft).toBeVisible();
  await expect(draft.getByRole('button', { name: 'Pin note' })).toBeDisabled();
  await draft.getByLabel('Note text').fill('Add a 1 mm chamfer around this top edge');
  await draft.getByLabel('Note text').press('Enter');
  const marker = page.getByRole('button', { name: 'Note 1: Add a 1 mm chamfer around this top edge' });
  await expect(marker).toBeVisible();
  await expect(page.locator('.composer-footer small')).toHaveText('1 pinned note goes with every request');
  // Kept beside the version, on the riser's top where it was clicked.
  const stored = await (await request.get(`/api/projects/pins?${new URLSearchParams({ project: folder, version })}`)).json();
  expect(stored.pins).toHaveLength(1);
  expect(stored.pins[0]).toMatchObject({ instance: 'riser', note: 'Add a 1 mm chamfer around this top edge' });
  expect(stored.pins[0].point[2]).toBeCloseTo(21.5, 3);  // on the riser's top, where it was clicked
  await page.keyboard.press('Escape');

  // A fresh visit to the same version shows the pin again.
  const again = await openProject(page);
  await expect(again).toBeVisible();
  // Pins stand on the model, so they appear once it has loaded.
  await expect(page.getByRole('button', { name: 'Note 1: Add a 1 mm chamfer around this top edge' })).toBeVisible({ timeout: 30000 });
  // Open it, edit it.
  await page.getByRole('button', { name: /^Note 1:/ }).click();
  await page.getByRole('group', { name: 'Note 1' }).getByRole('button', { name: 'Edit' }).click();
  const edit = page.getByRole('form', { name: 'Edit note' });
  await edit.getByLabel('Note text').fill('Add a 1 mm chamfer around the top edge');
  await edit.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('button', { name: 'Note 1: Add a 1 mm chamfer around the top edge' })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('magic-note-pin.png') });

  // Every request carries the version's pins, and the agent receives them.
  await page.getByLabel('Change request').fill('riser_height 14');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Propose change' }).click();
  const proposal = await (await posted).json();
  expect(proposal.selection.pins).toHaveLength(1);
  expect(proposal.selection.pins[0]).toMatchObject({ instance: 'riser', note: 'Add a 1 mm chamfer around the top edge' });
  expect(proposal.selection.pins[0].description).toMatch(/^a note pinned on body "riser" at \(.+\) mm: "Add a 1 mm chamfer around the top edge"$/);
  const echoed = await (await request.get(`/api/proposals/${proposal.id}`)).json();
  expect(echoed.selection).toEqual(proposal.selection);
  await expect(page.locator('.gate-progress')).toContainText('Pinned: a note pinned on body "riser"');
  await expect(page.getByRole('button', { name: 'Reject change' })).toBeEnabled({ timeout: 120000 });
  await page.getByRole('button', { name: 'Reject change' }).click();
  await expect(page.getByRole('region', { name: 'Proposed edit' })).toHaveCount(0);

  // Delete clears it from the version.
  await page.getByRole('button', { name: /^Note 1:/ }).click();
  await page.getByRole('group', { name: 'Note 1' }).getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByRole('button', { name: /^Note 1:/ })).toHaveCount(0);
  // Deleting is undoable for a few seconds, and focus lands on Undo rather than on the page.
  const undo = page.locator('.pin-undo').getByRole('button', { name: 'Undo' });
  await expect(undo).toBeFocused();
  await undo.click();
  const back = page.getByRole('button', { name: 'Note 1: Add a 1 mm chamfer around the top edge' });
  await expect(back).toBeFocused();
  // Escape closes an open note and hands focus back to its marker.
  await back.click();
  await expect(page.getByRole('group', { name: 'Note 1' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('group', { name: 'Note 1' })).toHaveCount(0);
  await page.waitForTimeout(300);  // focus moves back once the card has unmounted (two frames later)
  await expect(back).toBeFocused();
  await back.click();
  await page.getByRole('group', { name: 'Note 1' }).getByRole('button', { name: 'Delete' }).click();
  await expect(page.getByRole('button', { name: /^Note 1:/ })).toHaveCount(0);
  expect((await (await request.get(`/api/projects/pins?${new URLSearchParams({ project: folder, version })}`)).json()).pins).toEqual([]);
});

test('the lasso selects every enclosed face and corner point, on both bodies', async ({ page }) => {
  const canvas = await openProject(page);
  const at = await topView(page, canvas);
  await page.getByRole('button', { name: 'Circle an area' }).click();
  // A loop drawn around the whole model, off its surface.
  const box = (await canvas.boundingBox())!;
  const ring = [[0.08, 0.1], [0.92, 0.1], [0.92, 0.92], [0.08, 0.92], [0.08, 0.12]].map(([fx, fy]) => at(fx, fy));
  await page.mouse.move(box.x + ring[0].x, box.y + ring[0].y);
  await page.mouse.down();
  for (const point of ring.slice(1)) await page.mouse.move(box.x + point.x, box.y + point.y, { steps: 6 });
  await page.mouse.up();
  const chips = page.getByRole('list', { name: 'Selected on the model' });
  await expect(chips).toContainText(/Circled area on (base|riser) · 2 faces, 8 corners/);
  await page.screenshot({ path: test.info().outputPath('magic-lasso.png') });
  await page.getByLabel('Change request').fill('riser_height 14');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Propose change' }).click();
  const proposal = await (await posted).json();
  const area = proposal.selection.picks[0];
  expect(area.kind).toBe('area');
  expect(area.enclosed.faces.map((f: { instance: string; kind: string }) => `${f.instance}:${f.kind}`).sort()).toEqual(['base:plane', 'riser:plane']);
  expect(area.enclosed.points).toHaveLength(8);
  expect(area.enclosed.points.map((p: { point: number[] }) => p.point[2]).sort((a: number, b: number) => a - b)).toEqual([8, 8, 8, 8, 21.5, 21.5, 21.5, 21.5]);
  expect(area.description).toMatch(/it encloses 2 faces \(unnamed\) and 8 corner points$/);
  await expect(page.getByRole('button', { name: 'Reject change' })).toBeEnabled({ timeout: 120000 });
  await page.getByRole('button', { name: 'Reject change' }).click();
});
