import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { execFileSync } from 'node:child_process';

// Shipped launchers invoke vite.js directly, bypassing npm lifecycle hooks.
// Always refresh the same canonical ESM before serving/building any main graph;
// a generator failure throws here, before Vite can report readiness.
execFileSync(process.execPath, [path.resolve(__dirname, 'scripts/node-certificate-validator.mjs'), '--write'],
  { cwd: __dirname, stdio: 'inherit' });

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/v1': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/healthz': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/v1': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
      '/healthz': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'esnext',
    outDir: 'dist',
    sourcemap: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          query: ['@tanstack/react-query', 'zustand'],
          icons: ['lucide-react'],
        },
      },
    },
  },
});
