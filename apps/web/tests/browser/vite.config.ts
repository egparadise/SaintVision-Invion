import { defineConfig, mergeConfig } from 'vite';
import base from '../../vite.config';
if (!process.env.INV_BROWSER_TEST_API_URL) throw new Error('Isolated test API is required');
export default mergeConfig(base, defineConfig({ server: { host: '127.0.0.1', strictPort: true,
  proxy: { '/v1': { target: process.env.INV_BROWSER_TEST_API_URL, changeOrigin: true } } } }));
