import { test, expect, type Page } from '@playwright/test';
import { copyFileSync, readFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseManifest, type AssemblyManifest } from '../src/assembly/manifest';
import { INITIAL_VIEW, assemblyRows, displayOf, viewReducer } from '../src/assembly/view';

const repoPath = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));
const fixture: AssemblyManifest = parseManifest(JSON.parse(readFileSync(repoPath('tests/fixtures/assembly_manifest/holder_clip.json'), 'utf8')));

test('the tree lists every instance under its parent, with its kind in parts-list words', () => {
  expect(assemblyRows(fixture)).toEqual([
    { id: 'clip', name: 'Wall clip', kind: 'printed', kindLabel: 'Printed part', depth: 0 },
    { id: 'screw_1', name: 'M3 screw 1', kind: 'hardware', kindLabel: 'Hardware', depth: 1 },
    { id: 'screw_2', name: 'M3 screw 2', kind: 'hardware', kindLabel: 'Hardware', depth: 1 },
  ]);
  // A purchased component is named the way the parts list names it; an orphan still shows, at the root.
  const extra = { ...fixture.instances[0], id: 'fan', name: 'Fan', kind: 'component' as const, parent: 'missing' };
  expect(assemblyRows({ ...fixture, instances: [...fixture.instances, extra] }).at(-1)).toEqual({ id: 'fan', name: 'Fan', kind: 'component', kindLabel: 'Purchased component', depth: 0 });
});

test('hide, ghost and isolate act per instance and isolate never forgets what was hidden', () => {
  let view = viewReducer(INITIAL_VIEW, { type: 'toggleHidden', id: 'screw_1' });
  expect(['clip', 'screw_1', 'screw_2'].map(id => displayOf(view, id))).toEqual(['shown', 'hidden', 'shown']);
  view = viewReducer(view, { type: 'toggleGhost', id: 'clip' });
  expect(displayOf(view, 'clip')).toBe('ghost');
  view = viewReducer(view, { type: 'toggleIsolate', id: 'screw_2' });
  expect(['clip', 'screw_1', 'screw_2'].map(id => displayOf(view, id))).toEqual(['hidden', 'hidden', 'shown']);
  // Isolating a hidden instance shows it; leaving isolation restores the earlier choices.
  view = viewReducer(view, { type: 'toggleIsolate', id: 'screw_1' });
  expect(['clip', 'screw_1', 'screw_2'].map(id => displayOf(view, id))).toEqual(['hidden', 'shown', 'hidden']);
  view = viewReducer(view, { type: 'toggleIsolate', id: 'screw_1' });
  expect(['clip', 'screw_1', 'screw_2'].map(id => displayOf(view, id))).toEqual(['ghost', 'hidden', 'shown']);
  view = viewReducer(view, { type: 'showAll' });
  expect(['clip', 'screw_1', 'screw_2'].map(id => displayOf(view, id))).toEqual(['shown', 'shown', 'shown']);
  expect(viewReducer(view, { type: 'explode', amount: 1.7 }).explode).toBe(1);
  expect(viewReducer(view, { type: 'select', id: 'clip' }).selected).toBe('clip');
});

// The assembly project sits inside the shared test project folder; left there, it would read as an
// unsaved change to that project's versions and block studio.spec's rollback.
const assemblyFolder = () => `${process.env.MAGIC_TEST_PROJECT!}/holder-assembly-${test.info().workerIndex}-${test.info().repeatEachIndex}-${test.info().retry}`;
test.afterEach(() => rmSync(assemblyFolder(), { recursive: true, force: true }));

type Probe = Record<string, { visible: boolean; opacity: number; highlighted: boolean; position: [number, number, number] }>;
const probe = async (page: Page): Promise<Probe> => JSON.parse(await page.getByTestId('assembly-scene').getAttribute('data-instances') || '{}');

test('Studio shows the assembly: tree, highlight, hide/isolate/ghost and a derived exploded view', async ({ page, request }) => {
  test.setTimeout(300000);  // one full gate run of the clip and its assembly
  const folder = assemblyFolder();
  expect((await request.post('/api/projects', { data: { folder, from_design: repoPath('designs/holder_clip.py') } })).ok()).toBeTruthy();
  copyFileSync(repoPath('assembly/holder_clip.py'), `${folder}/assembly.py`);
  expect((await request.post('/api/projects/versions', { data: { project: folder, message: 'Add the assembly' } })).ok()).toBeTruthy();
  const checked = await request.post('/api/runs', { data: { project: folder, wait: true, samples: 9 }, timeout: 240000 });
  expect(checked.ok(), await checked.text()).toBeTruthy();
  const manifest = parseManifest(JSON.parse(readFileSync(`${folder}/outputs/_assembly/assembly.json`, 'utf8')));

  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', { name: 'Open project' }).click();

  // An assembly opens in the assembly view; the parts view stays one click away.
  const views = page.getByRole('group', { name: 'Model view' });
  await expect(views.getByRole('button', { name: 'Assembly' })).toHaveAttribute('aria-pressed', 'true', { timeout: 30000 });
  const tree = page.getByRole('treegrid', { name: 'Assembly' });
  await expect(tree.getByRole('row')).toHaveCount(manifest.instances.length);
  for (const instance of manifest.instances) await expect(tree.getByRole('row', { name: new RegExp(instance.name) })).toBeVisible();
  await expect(tree.getByRole('row', { name: /M3 screw 1/ })).toHaveAttribute('aria-level', '2');
  await expect(tree.getByRole('row', { name: /Wall clip/ })).toContainText('Printed part');
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  await expect.poll(async () => Object.keys(await probe(page)).sort()).toEqual(manifest.instances.map(i => i.id).sort());

  // Selecting in the tree highlights that instance, and only it, in 3D.
  await tree.getByRole('row', { name: /M3 screw 1/ }).click();
  await expect(tree.getByRole('row', { name: /M3 screw 1/ })).toHaveAttribute('aria-selected', 'true');
  await expect.poll(async () => Object.entries(await probe(page)).filter(([, s]) => s.highlighted).map(([id]) => id)).toEqual(['screw_1']);
  await tree.getByRole('row', { name: /M3 screw 1/ }).getByRole('button', { name: /^M3 screw 1/ }).press('ArrowDown');
  await expect(tree.getByRole('row', { name: /M3 screw 2/ }).getByRole('button', { name: /^M3 screw 2/ })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect.poll(async () => Object.values(await probe(page)).some(s => s.highlighted)).toBe(false);
  await tree.getByRole('row', { name: /M3 screw 1/ }).click();

  // Hide, ghost and isolate, each on one instance.
  await page.getByRole('button', { name: 'Hide M3 screw 2' }).click();
  await expect.poll(async () => (await probe(page)).screw_2.visible).toBe(false);
  await expect(page.getByRole('button', { name: 'Hide M3 screw 2' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Ghost Wall clip' }).click();
  await expect.poll(async () => (await probe(page)).clip.opacity).toBeLessThan(0.5);
  await expect.poll(async () => (await probe(page)).clip.visible).toBe(true);
  await page.getByRole('button', { name: 'Isolate M3 screw 1' }).click();
  await expect.poll(async () => Object.entries(await probe(page)).filter(([, s]) => s.visible).map(([id]) => id)).toEqual(['screw_1']);
  await page.getByRole('button', { name: 'Isolate M3 screw 1' }).click();
  await expect.poll(async () => (await probe(page)).clip.visible).toBe(true);
  await expect.poll(async () => (await probe(page)).screw_2.visible).toBe(false);
  await page.getByRole('button', { name: 'Show all' }).click();
  await expect.poll(async () => Object.values(await probe(page)).every(s => s.visible && s.opacity === 1)).toBe(true);

  // The exploded view moves every instance by the manifest's derived offset, scaled by the slider.
  const slider = page.getByRole('slider', { name: 'Explode' });
  await slider.fill('100');
  await expect(slider).toHaveAttribute('aria-valuetext', '100%');
  await expect.poll(async () => {
    const now = await probe(page);
    return manifest.instances.every(instance => {
      const offset = manifest.explode.find(r => r.instance === instance.id)!.offset;
      return instance.transform.position.every((v, k) => Math.abs(now[instance.id].position[k] - (v + offset[k])) < 1e-3);
    });
  }).toBe(true);
  const moving = manifest.explode.filter(r => r.distance > 0).map(r => r.instance);
  expect(moving.length).toBeGreaterThan(0);
  await slider.fill('50');
  await expect.poll(async () => (await probe(page))[moving[0]].position[0]).toBeCloseTo(manifest.instances.find(i => i.id === moving[0])!.transform.position[0] + manifest.explode.find(r => r.instance === moving[0])!.offset[0] / 2, 3);

  // A click on a part in the viewport selects it in the tree.
  await slider.fill('0');
  await page.getByRole('button', { name: 'Isolate Wall clip' }).click();
  // Head-on, the middle of the view is the clip's solid front wall rather than the hollow of its barrel.
  await page.getByRole('group', { name: 'Camera controls' }).getByRole('button', { name: 'Front', exact: true }).click();
  const canvas = page.getByLabel('3D model').locator('canvas');
  await page.waitForTimeout(1200);
  const box = (await canvas.boundingBox())!;
  await canvas.click({ position: { x: box.width * 0.42, y: box.height / 2 } });
  await expect(tree.getByRole('row', { name: /Wall clip/ })).toHaveAttribute('aria-selected', 'true');

  // The parts view still shows the design bodies, without the assembly's own meshes.
  await views.getByRole('button', { name: 'Parts' }).click();
  await expect(page.getByRole('treegrid', { name: 'Assembly' })).toHaveCount(0);
  await expect(page.getByRole('group', { name: 'Bodies' }).getByRole('button')).toHaveText(['holder_clip']);
});

test('a project without an assembly shows no assembly view', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await expect(page.getByRole('heading', { name: 'Version 3' })).toBeVisible();
  // The version's artifact list has loaded once the stage shows its model or says there is none.
  await expect(page.getByLabel('3D model').or(page.getByText(/No saved model/))).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole('group', { name: 'Model view' })).toHaveCount(0);
  await expect(page.getByRole('treegrid', { name: 'Assembly' })).toHaveCount(0);
});
