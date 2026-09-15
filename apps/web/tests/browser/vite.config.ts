import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
export default defineConfig({
  plugins: [react()],
  resolve: {alias: {'@': path.resolve(__dirname, '../../src')}},
  server: {host: '127.0.0.1', strictPort: true, proxy: {'/v1': {target: process.env.INV_BROWSER_TEST_API_URL, changeOrigin: true}}},
});
