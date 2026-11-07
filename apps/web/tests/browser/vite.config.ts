import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

// This fixture is launched directly by Node/Vite, so npm's predev hook is not run.
// Prepare the SAME canonical ESM before any browser entry graph is linked.
execFileSync(process.execPath, [path.resolve(__dirname, '../../scripts/node-certificate-validator.mjs'), '--write'],
  { cwd: path.resolve(__dirname, '../..'), stdio: 'inherit' });

export default defineConfig({
  plugins: [react()],
  resolve: {alias: {'@': path.resolve(__dirname, '../../src')}},
  server: {host: '127.0.0.1', strictPort: true, proxy: {'/v1': {target: process.env.INV_BROWSER_TEST_API_URL, changeOrigin: true}}},
});
