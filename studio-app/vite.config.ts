import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// MAGIC_ENGINE_PORT lets parallel checkouts run their own engine (see playwright.config.ts).
const engine = process.env.MAGIC_ENGINE_PORT || '8766';
export default defineConfig({ plugins: [react()], server: { proxy: { '/api': { target: `http://127.0.0.1:${engine}`, changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } } } });
