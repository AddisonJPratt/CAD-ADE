import { test, expect } from '@playwright/test';

// #52: "Add knurling to this face" on a picked face becomes a previewed proposal that adds the
// texture's pitch and depth as new parameters. The engine test (tests/test_texture_request.py)
// accepts the same proposal and runs every gate and the sweep on it.
test('asking for knurling on a picked face previews a texture proposal with its new parameters', async ({ page, request }) => {
  test.setTimeout(300000);  // one gate run to export the face map, then two preview builds
  const folder = process.env.MAGIC_TEST_PROJECT! + '/knurl-on-a-pick';
  const source = decodeURIComponent(new URL('../../tests/fixtures/named_features.py', import.meta.url).pathname);
  expect((await request.post('/api/projects', {data:{folder, from_design:source}})).ok()).toBeTruthy();
  const checked = await request.post('/api/runs', {data:{project: folder, wait: true, samples: 9}, timeout: 180000});
  expect(checked.ok(), await checked.text()).toBeTruthy();
  const faceMap = page.waitForResponse(r => r.url().includes('plate.faces.json') && r.ok());
  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', {name:'Open project'}).click();
  await faceMap;
  const canvas = page.getByLabel('3D model').locator('canvas');
  await expect(canvas).toBeVisible();
  // Straight down onto the middle of the plate: the floor of the lid pocket. Wait for the camera to settle first.
  await page.getByRole('group', {name:'Camera controls'}).getByRole('button', {name:'Top', exact:true}).click();
  await page.waitForTimeout(700);
  let last = await canvas.screenshot();
  await expect.poll(async () => { await page.waitForTimeout(400); const next = await canvas.screenshot(); const same = next.equals(last); last = next; return same; }, {timeout: 15000}).toBe(true);
  const box = (await canvas.boundingBox())!;
  await canvas.click({position: {x: box.width / 2, y: box.height / 2}});
  await expect(page.getByRole('list', {name:'Selected on the model'})).toContainText('Lid pocket');
  await page.getByLabel('Change request').fill('Add knurling to this face');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', {name:'Propose change'}).click();
  expect((await posted).status()).toBe(202);
  await expect(page.locator('.gate-progress')).toContainText('Add straight knurl to the +Z face of \'lid pocket\'');
  await expect(page.locator('.gate-progress')).toContainText('add knurl_pitch = 2');
  await expect(page.getByRole('button', {name:'Accept change'})).toBeEnabled({timeout:180000});
  const diff = page.locator('.review-diff');
  await expect(diff).toContainText('knurl_pitch: new 2');
  await expect(diff).toContainText('knurl_depth: new 0.6');
  await page.screenshot({path: test.info().outputPath('magic-knurl-proposal.png')});
  await page.getByRole('button', {name:'Reject change'}).click();
  await expect(page.getByRole('region', {name:'Proposed edit'})).toHaveCount(0);
});
