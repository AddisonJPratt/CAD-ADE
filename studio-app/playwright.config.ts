import { defineConfig } from '@playwright/test';
// MAGIC_ENGINE_PORT / MAGIC_STUDIO_PORT let parallel checkouts run their suites side by side.
const engine = process.env.MAGIC_ENGINE_PORT || '8766';
const studio = process.env.MAGIC_STUDIO_PORT || '5173';
export default defineConfig({ testDir: './tests', timeout: 180000, use: { baseURL: `http://127.0.0.1:${studio}`, channel: 'chrome', launchOptions: { args: ['--use-angle=swiftshader'] } }, webServer: [{ command: `../.venv/bin/python ../magic.py serve --agent scripted --port ${engine}`, url: `http://127.0.0.1:${engine}/health`, reuseExistingServer: false, timeout: 30000 }, { command: `npm run dev -- --port ${studio} --strictPort`, url: `http://127.0.0.1:${studio}`, reuseExistingServer: false, timeout: 30000 }] });
