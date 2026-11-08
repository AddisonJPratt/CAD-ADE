import { test, expect } from '@playwright/test';

test('opens a project and inspects an older version', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await expect(page.getByRole('heading', { name: 'Version 3' })).toBeVisible();
  await expect(page.getByText('Not ready to print', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Versions', exact: true }).click();
  const currentModel = page.waitForResponse(r => r.url().includes('version-artifacts') && r.url().includes('path=') && r.ok());
  await page.getByRole('button', { name: /Version 2/ }).click();
  const currentBytes = await (await currentModel).body();
  await expect(page.getByRole('heading', { name: 'Version 2' })).toBeVisible();
  await expect(page.getByText('Ready to print', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Checks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Computed checks' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Needs a physical test' })).toBeVisible();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Versions', exact: true }).click();
  await page.getByRole('button', { name: /Version 1/ }).click();
  await page.getByRole('button', { name: 'Close details' }).click();
  await expect(page.getByRole('button', { name: 'Rebuild model' })).toBeVisible();
  const oldModel = page.waitForResponse(r => r.url().includes('version-artifacts') && r.url().includes('path=') && r.ok());
  await page.getByRole('button', { name: 'Rebuild model' }).click();
  const response = await oldModel;
  const oldBytes = await response.body();
  expect(oldBytes.length).toBeGreaterThan(100);
  expect(oldBytes.equals(currentBytes)).toBe(false);
  await page.getByRole('button', { name: 'Versions', exact: true }).click();
  await expect(page.getByRole('button', { name: /Version 3/ })).toBeVisible();
  await page.getByRole('button', { name: 'Close details' }).click();
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible();
  await expect(page.getByText('Ready to print', { exact: true })).toBeVisible();
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
  await page.screenshot({path: test.info().outputPath('magic-studio-desktop.png')});
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({path: test.info().outputPath('magic-studio-mobile.png'), fullPage:true});
});

test('fake agent previews, rejects and accepts a change', async ({ page, request }) => {
  const project = process.env.MAGIC_TEST_PROJECT!;
  const restored = await request.post('/api/projects/rollback', { data: { project, version: '2', wait: true, samples: 5 }, timeout: 180000 });
  expect(restored.ok(), await restored.text()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Project folder').fill(project);
  await page.getByRole('button', { name: 'Open project' }).click();
  const wire = page.getByRole('button', { name: 'Wireframe' });
  await wire.click();
  await expect(wire).toHaveAttribute('aria-pressed', 'true');
  await wire.click();
  await page.getByRole('button', { name: 'Use light theme' }).click();
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await expect(page.getByRole('button', { name: 'Use light theme' })).toBeVisible();
  await page.screenshot({path: test.info().outputPath('magic-application-dark.png')});
  await page.getByText('Export STL', {exact:true}).click();
  await expect(page.locator('.export-menu a')).toHaveCount(2);
  await page.getByText('Export STL', {exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.getByText('Export STL', {exact:true}).click();
  const downloaded = page.waitForEvent('download');
  await page.locator('.export-menu a').first().click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.stl$/);
  await page.getByText('Export STL', {exact:true}).click();
  await page.setViewportSize({width:1280,height:720});
  await page.getByLabel('Change request').fill('size 26');
  await page.getByRole('button', { name: 'Propose change' }).click();
  await expect(page.getByText('size: 24 → 26').first()).toBeVisible({ timeout: 120000 });
  await expect(page.getByLabel('after preview').locator('canvas')).toBeVisible();
  await expect(page.getByText('Unchecked previews · same scale')).toBeVisible();
  await page.waitForTimeout(3000);
  await page.screenshot({path: test.info().outputPath('magic-comparison-initial.png')});
  await page.getByRole('group', { name: 'Preview camera controls' }).getByRole('button', { name: 'Iso' }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({path: test.info().outputPath('magic-comparison-desktop.png')});
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel('after preview').locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Before', exact: true }).click();
  await expect(page.getByLabel('before preview').locator('canvas')).toBeVisible();
  await page.getByRole('button', { name: 'After', exact: true }).click();
  await page.waitForTimeout(3000);
  await page.screenshot({path: test.info().outputPath('magic-comparison-mobile.png')});
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole('button', { name: 'Reject change' }).click();
  await expect(page.getByText('Proposed change ready to review')).toHaveCount(0);
  // The composer clears after sending, so ask again.
  await page.getByLabel('Change request').fill('size 26');
  await page.getByRole('button', { name: 'Propose change' }).click();
  await expect(page.getByText('size: 24 → 26').first()).toBeVisible({ timeout: 120000 });
  await page.getByRole('button', { name: 'Accept change' }).click();
  await expect(page.getByText('Previous: passed · Now: passed')).toBeVisible({ timeout: 180000 });
  await expect(page.locator('.gate-progress .progress-row', { hasText: '3 Printability' })).toHaveClass(/pass/);
  await expect(page.locator('.gate-progress .progress-row', { hasText: '3 Printability' }).locator('.progress-status')).toHaveText('PASS');
  await expect(page.getByRole('heading', { name: 'Version 5' })).toBeVisible();
});

test('reviews a curved cable clip proposal', async ({ page, request }) => {
  const folder = process.env.MAGIC_TEST_PROJECT! + '/cable-clip';
  const source = new URL('../../designs/cable_clip.py', import.meta.url).pathname;
  const created = await request.post('/api/projects', {data: {folder, from_design: decodeURIComponent(source)}});
  expect(created.ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', {name: 'Open project'}).click();
  await page.getByRole('button', {name: 'Settings', exact: true}).click();
  await expect(page.getByRole('spinbutton', {name:'cable_dia', exact:true})).toHaveValue('6');
  await page.getByRole('button', {name: 'Close details'}).click();
  const rebuilt = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/projects/version-artifacts'), {timeout:120000});
  await page.getByRole('button', {name:'Rebuild model', exact:true}).click();
  expect((await rebuilt).ok()).toBeTruthy();
  await expect(page.getByLabel('3D model').locator('canvas')).toBeVisible({timeout:30000});
  await page.waitForTimeout(1500);
  const modelCanvas = page.getByLabel('3D model').locator('canvas');
  const alloy = await modelCanvas.screenshot();
  await page.getByRole('button', {name:'Viewport display settings',exact:true}).click();
  const display = page.getByRole('region',{name:'Viewport display',exact:true});
  await expect(display).toBeVisible();
  await display.getByRole('button',{name:'Porcelain',exact:true}).click();
  await expect(display.getByRole('button',{name:'Porcelain',exact:true})).toHaveAttribute('aria-pressed','true');
  await display.getByLabel('Studio lighting').focus();
  await page.keyboard.press('Home');
  await page.keyboard.press('ArrowRight');
  await expect(display.locator('output')).toHaveText('45%');
  await display.getByLabel('Workplane grid').uncheck();
  await expect(display.getByLabel('Workplane grid')).not.toBeChecked();
  await page.screenshot({path: test.info().outputPath('magic-viewport-display-desktop.png')});
  await page.keyboard.press('Escape');
  await expect(display).not.toBeVisible();
  await expect.poll(async () => (await modelCanvas.screenshot()).equals(alloy)).toBe(false);
  await page.getByRole('button', {name:'Viewport display settings',exact:true}).click();
  await display.getByRole('button',{name:'Reset',exact:true}).click();
  await expect(display.locator('output')).toHaveText('100%');
  await expect(display.getByLabel('Workplane grid')).toBeChecked();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Pan navigation',exact:true}).click();
  await expect(page.getByRole('button',{name:'Pan navigation',exact:true})).toHaveAttribute('aria-pressed','true');
  const box = await modelCanvas.boundingBox();
  const beforePan = await modelCanvas.screenshot();
  await page.mouse.move(box!.x+box!.width*.5,box!.y+box!.height*.45);
  await page.mouse.down();
  await page.mouse.move(box!.x+box!.width*.55,box!.y+box!.height*.5,{steps:8});
  await page.mouse.up();
  await expect.poll(async () => (await modelCanvas.screenshot()).equals(beforePan)).toBe(false);
  await page.getByRole('button',{name:'Fit model',exact:true}).click();
  await page.getByRole('button',{name:'Orbit navigation',exact:true}).click();
  await page.mouse.move(800,100);
  await page.screenshot({path: test.info().outputPath('magic-viewport-tools-desktop.png')});
  await page.getByRole('button',{name:'Use light theme',exact:true}).click();
  await page.screenshot({path: test.info().outputPath('magic-viewport-tools-light.png')});
  await page.getByRole('button',{name:'Use dark theme',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Viewport display settings',exact:true}).click();
  await expect(display).toBeVisible();
  await page.mouse.move(380,800);
  await page.screenshot({path: test.info().outputPath('magic-viewport-display-mobile.png')});
  await page.keyboard.press('Escape');
  await page.setViewportSize({width:1280,height:720});
  await page.screenshot({path: test.info().outputPath('magic-parameter-cable-inspector.png')});
  await page.getByLabel('Change request').fill('cable_dia 8');
  await page.getByRole('button', {name: 'Propose change'}).click();
  const keep = page.getByRole('button', {name: 'Accept change'});
  await expect(keep).toBeEnabled({timeout:120000});
  await expect(page.getByText('Preview bodies', {exact:false})).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({path: test.info().outputPath('magic-hallmark-cable-desktop.png')});
  const measurements = page.locator('.model-measurements:visible');
  const envelope = measurements.locator('summary');
  await envelope.click();
  await expect(measurements.getByText('Body 1', {exact:true})).toBeVisible();
  await envelope.click();
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(1500);
  await page.screenshot({path: test.info().outputPath('magic-hallmark-cable-mobile.png')});
  await page.getByRole('button', {name:'Reject change'}).click();
  await expect(page.getByRole('region', {name:'Proposed edit'})).toHaveCount(0);
});

test('bounded parameter controls preview and accept a saved edit', async ({ page, request }) => {
  const folder = process.env.MAGIC_TEST_PROJECT! + '/parameter-panel';
  // Units and intent come only from the PARAMS-line comments: this fixture has no brief.
  const source = decodeURIComponent(new URL('../../tests/fixtures/commented_params.py', import.meta.url).pathname);
  expect((await request.post('/api/projects', {data:{folder, from_design:source}})).ok()).toBeTruthy();
  const proposalPosts: string[] = [];
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/api/proposals')) proposalPosts.push(r.url()); });
  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', {name:'Open project'}).click();
  await page.getByRole('button', {name:'Settings', exact:true}).click();
  const panel = page.getByRole('region', {name:'Design parameters'});
  const size = panel.getByRole('spinbutton', {name:'size', exact:true});
  const gap = panel.getByRole('spinbutton', {name:'gap', exact:true});
  await expect(panel.getByRole('spinbutton')).toHaveCount(2);
  await expect(size).toHaveValue('20');
  await expect(size).toHaveAttribute('min', '10');
  await expect(size).toHaveAttribute('max', '30');
  await expect(size).toHaveAccessibleDescription('Block edge length 10 to 30 mm');
  await expect(panel.getByText('Block edge length', {exact:true})).toBeVisible();
  await expect(gap).toHaveValue('1');
  await expect(gap).toHaveAccessibleDescription('Clearance between the blocks 0.5 to 2 mm');
  await expect(panel.getByText('Clearance between the blocks', {exact:true})).toBeVisible();
  await page.screenshot({path: test.info().outputPath('magic-parameter-inspector-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  await expect(size).toBeVisible();
  await expect(page.locator('.app-header')).toHaveCount(1);
  await page.waitForTimeout(1000);
  await page.screenshot({path: test.info().outputPath('magic-parameter-inspector-mobile.png')});
  await page.setViewportSize({width:1280,height:720});
  const review = panel.getByRole('button', {name:'Review size', exact:true});
  await size.fill('');
  await expect(review).toBeDisabled();
  await size.press('Enter');
  for (const outside of ['31', '9.5']) {
    await size.fill(outside);
    await expect(review).toBeDisabled();
    await expect(size).toHaveAttribute('aria-invalid', 'true');
    await size.press('Enter');
  }
  await expect(size).toHaveAccessibleDescription(/Enter a value from 10 to 30 mm/);
  await panel.getByRole('button', {name:'Revert to 20 mm'}).click();
  await expect(size).toHaveValue('20');
  await expect(review).toBeDisabled();
  await size.fill('31');
  await page.screenshot({path: test.info().outputPath('magic-parameter-out-of-range.png')});
  await expect(page.getByRole('region', {name:'Proposed edit'})).toHaveCount(0);
  expect(proposalPosts).toEqual([]);
  await size.fill('24');
  await expect(size).not.toHaveAttribute('aria-invalid', 'true');
  await review.click();
  await expect(page.getByText('size: 20 → 24').first()).toBeVisible({timeout:120000});
  expect(proposalPosts).toHaveLength(1);
  await page.getByRole('button', {name:'Accept change'}).click();
  await expect(page.getByRole('heading', {name:'Version 2'})).toBeVisible({timeout:180000});
  await expect(size).toHaveValue('24');
  await expect(size).toHaveAttribute('step', '1');
  await expect(gap).toHaveAttribute('step', '0.1');
  await expect(page.getByText('Ready to print', {exact:true})).toBeVisible();
  await size.fill('24.5');
  await review.click();
  await expect(page.getByText('size: 24 → 24.5').first()).toBeVisible({timeout:120000});
  await page.getByRole('button', {name:'Reject change'}).click();
  // A discarded draft does not linger as if it were the saved value.
  await expect(size).toHaveValue('24');
});

test('Watermelon-adapted command search runs real Studio actions', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', {name:'Open project'}).click();
  await page.getByRole('button', {name:'Versions', exact:true}).click();
  await page.getByRole('button', {name:/Version 2/}).click();
  await page.getByRole('button', {name:'Close details'}).click();
  const canvas = page.getByLabel('3D model').locator('canvas');
  await expect(canvas).toBeVisible();
  await page.waitForTimeout(1500);
  const shortcut = process.platform === 'darwin' ? 'Meta+k' : 'Control+k';
  await page.keyboard.press(shortcut);
  const menu = page.getByRole('dialog', {name:'Studio commands'});
  await expect(menu).toBeVisible();
  await page.screenshot({path: test.info().outputPath('magic-watermelon-commands-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(1000);
  await page.screenshot({path: test.info().outputPath('magic-watermelon-commands-mobile.png')});
  await page.setViewportSize({width:1280,height:720});
  await page.waitForTimeout(1000);
  await page.keyboard.press('Escape');
  const before = await canvas.screenshot();
  await page.keyboard.press(shortcut);
  await menu.getByRole('combobox', {name:'Search commands'}).fill('front');
  await menu.getByRole('combobox', {name:'Search commands'}).press('Enter');
  await expect(menu).not.toBeVisible();
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  await page.keyboard.press(shortcut);
  await menu.getByRole('combobox', {name:'Search commands'}).fill('no such tool');
  await expect(menu.getByText('No matching commands')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).not.toBeVisible();
  await page.keyboard.press(shortcut);
  await menu.getByRole('combobox', {name:'Search commands'}).fill('light theme');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', {name:'Use dark theme'})).toBeVisible();
});

test('the header shows the Magic box brand and the favicon is served', async ({ page, request }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Magic CAD');
  // The logo is a plain image named "Magic CAD": nothing to click, and not a Tab stop.
  const brand = page.getByRole('img', {name:'Magic CAD', exact:true});
  await expect(page.getByRole('link', {name:/Magic CAD/})).toHaveCount(0);
  const mark = brand.locator('svg.brand-mark'), wordmark = brand.locator('svg.brand-wordmark');
  await expect(mark).toBeVisible();
  await expect(wordmark).toBeVisible();
  await expect(mark).toHaveAttribute('data-surface', 'dark');
  await page.getByRole('button', {name:'Use light theme'}).click();
  await expect(mark).toHaveAttribute('data-surface', 'light');
  const favicon = await page.locator('link[rel="icon"][type="image/svg+xml"]').getAttribute('href');
  expect(favicon).toBe('/favicon.svg');
  for (const icon of [favicon!, '/favicon-32.png', '/apple-touch-icon.png']) expect((await request.get(icon)).ok()).toBe(true);
  await page.setViewportSize({width:390, height:844});
  await expect(wordmark).toBeHidden();
  await expect(mark).toBeVisible();
});

test('modes preserve the project and selected version, and Mission Control shows saved sources', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: 'Versions', exact: true }).click();
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

// Last: choosing a material writes printer.json, an unsaved project change that would block rollbacks and proposals in earlier tests.
test('the Settings drawer shows the project printer and changes the material for future checks', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project folder').fill(process.env.MAGIC_TEST_PROJECT!);
  await page.getByRole('button', { name: 'Open project' }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByText('Elegoo Centauri Carbon 2')).toBeVisible();
  await expect(page.getByLabel('Material')).toHaveValue('PLA');
  await page.getByLabel('Material').selectOption('PETG');
  await expect(page.getByText('Material set to PETG for future checks.')).toBeVisible();
  await page.getByLabel('Material').selectOption('PLA');
  await expect(page.getByText('Material set to PLA for future checks.')).toBeVisible();
});

test('a picked face is named from the harness face map, survives a mode switch and reaches the agent', async ({ page, request }) => {
  test.setTimeout(300000);  // one full gate run with its sweep, then a proposal preview
  const folder = process.env.MAGIC_TEST_PROJECT! + '/named-features';
  const source = decodeURIComponent(new URL('../../tests/fixtures/named_features.py', import.meta.url).pathname);
  expect((await request.post('/api/projects', {data:{folder, from_design:source}})).ok()).toBeTruthy();
  // Checking the version exports the model and its face map together; the open then loads both.
  const checked = await request.post('/api/runs', {data:{project: folder, wait: true, samples: 9}, timeout: 180000});
  expect(checked.ok(), await checked.text()).toBeTruthy();
  const faceMap = page.waitForResponse(r => r.url().includes('plate.faces.json') && r.ok());
  await page.goto('/');
  await page.getByLabel('Project folder').fill(folder);
  await page.getByRole('button', {name:'Open project'}).click();
  expect((await (await faceMap).json()).features).toEqual(['lid pocket', 'mount hole']);
  const canvas = page.getByLabel('3D model').locator('canvas');
  await expect(canvas).toBeVisible();
  const cameras = page.getByRole('group', {name:'Camera controls'});
  const at = async (fx: number, fy: number) => { const box = (await canvas.boundingBox())!; return {x: box.width * fx, y: box.height * fy}; };
  const centre = () => at(0.5, 0.5);
  // The camera presets animate: wait until two consecutive frames agree before clicking.
  const settled = async () => { await page.waitForTimeout(700); let last = await canvas.screenshot(); await expect.poll(async () => { await page.waitForTimeout(400); const next = await canvas.screenshot(); const same = next.equals(last); last = next; return same; }, {timeout: 15000}).toBe(true); };
  // Straight down onto the middle of the plate: the floor of the lid pocket, a labelled feature.
  await cameras.getByRole('button', {name:'Top', exact:true}).click();
  await settled();
  await canvas.click({position: await centre()});
  const chips = page.getByRole('list', {name:'Selected on the model'});
  await expect(chips).toContainText('Lid pocket · plate');
  // The selection belongs to the project, not to the Studio mode.
  await page.getByRole('button', {name:'Mission Control'}).click();
  await expect(page.getByRole('heading', {name:'Mission Control'})).toBeVisible();
  await page.getByRole('button', {name:'Make', exact:true}).click();
  await expect(page.getByRole('heading', {name:'Make'})).toBeVisible();
  await page.getByRole('button', {name:'Studio', exact:true}).click();
  await expect(chips).toContainText('Lid pocket · plate');
  // The plate's own front face has no name: it is described by where it faces.
  await cameras.getByRole('button', {name:'Front', exact:true}).click();
  await settled();
  // Up and to the left of the first pick: its action bar hangs below and to the right of the anchor.
  await canvas.click({position: await at(0.3, 0.45), modifiers:['Shift']});
  await expect(chips.getByRole('listitem')).toHaveCount(2);
  await expect(chips).toContainText('Face on plate ·');
  await page.screenshot({path: test.info().outputPath('magic-selection-named-feature.png')});
  // Sending attaches the structured selection; the engine echoes what the agent received.
  await page.getByLabel('Change request').fill('size 32');
  const posted = page.waitForResponse(r => r.url().endsWith('/api/proposals') && r.request().method() === 'POST');
  await page.getByRole('button', {name:'Propose change'}).click();
  const proposal = await (await posted).json();
  expect(proposal.selection.design).toBe('named_features.py');
  expect(proposal.selection.picks.map((p: {instance: string; kind: string; feature: string | null}) => [p.instance, p.kind, p.feature])).toEqual([['plate', 'face', 'lid pocket'], ['plate', 'face', null]]);
  expect(proposal.selection.picks[0].description).toContain('the "lid pocket" feature of body "plate"');
  expect(proposal.selection.picks[1].description).toMatch(/^a flat face on body "plate" facing /);
  expect(proposal.selection.measurement.kind).toBe('centre to centre');
  const echoed = await (await request.get(`/api/proposals/${proposal.id}`)).json();
  expect(echoed.selection).toEqual(proposal.selection);
  await expect(page.locator('.gate-progress')).toContainText('Selected: a flat face on the "lid pocket" feature of body "plate"');
  await expect(chips).toHaveCount(0);
  await expect(page.getByRole('button', {name:'Accept change'})).toBeEnabled({timeout:120000});
  await page.getByRole('button', {name:'Reject change'}).click();
  await expect(page.getByRole('region', {name:'Proposed edit'})).toHaveCount(0);
});

test('creates a project without typing a path, lists it, and browses folders', async ({ page }) => {
  test.skip(!process.env.MAGIC_PROJECTS_HOME, 'needs a scratch MAGIC_PROJECTS_HOME (tests/run.sh sets one)');
  const name = `Picker ${Date.now()}`;
  await page.goto('/');
  await page.getByRole('button', { name: 'New project', exact: true }).first().click();
  await expect(page.getByRole('radio', { name: /Box with lid/ })).toBeChecked();
  await expect(page.getByText('Small two-part storage box: an open tray and a separate lid', { exact: false })).toBeInViewport();
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByText('Give the project a name.')).toBeVisible();
  await expect(page.getByLabel('Name')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByLabel('Project folder')).toHaveCount(0); // the typed-path fallback steps aside while naming
  await page.getByLabel('Name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible({ timeout: 60000 });
  await expect(page.getByLabel('Project folder')).toHaveValue(new RegExp(name + '$'));

  await page.goto('/');
  await page.getByRole('button', { name: new RegExp(name) }).click();
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible({ timeout: 60000 });

  await page.goto('/');
  await page.getByRole('button', { name: 'Browse', exact: true }).click();
  // Browse starts in the projects home, where the new project is marked as a project.
  await expect(page.locator('.picker-browse .picker-row.is-project', { hasText: name })).toBeVisible();
  const here = await page.locator('.crumb .path').textContent();
  await page.getByLabel('Up one folder').click();
  await expect(page.locator('.crumb .path')).not.toHaveText(here!);
  await page.getByRole('button', { name: 'Projects home' }).click();
  await expect(page.locator('.crumb .path')).toHaveText(here!);
  await page.locator('.picker-browse .picker-row.is-project', { hasText: name }).click();
  await expect(page.getByRole('heading', { name: 'Version 1' })).toBeVisible({ timeout: 60000 });
});

test('Choose a folder in Finder opens a project, explains a non-project folder, and ignores Cancel', async ({ page }) => {
  // The engine shows the real macOS panel; here its answer is stubbed so no window opens.
  const project = process.env.MAGIC_TEST_PROJECT!;
  const answers = [{ path: null, project: false }, { path: project + '/designs', project: false }, { path: project, project: true }];
  await page.route('**/api/workspace/choose-folder', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answers.shift()) }));
  await page.goto('/');
  const finder = page.getByRole('button', { name: 'Choose a folder in Finder…' });
  await finder.click();                       // Cancel: nothing changes
  await expect(finder).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Open a project' })).toBeVisible();
  await finder.click();                       // a folder that is not a project
  await expect(page.getByRole('status').filter({ hasText: 'That folder is not a project' })).toBeVisible();
  await expect(page.locator('.crumb .path')).toContainText('designs');
  await finder.click();                       // a project opens
  await expect(page.getByRole('heading', { name: /Version \d/ })).toBeVisible({ timeout: 60000 });
});
