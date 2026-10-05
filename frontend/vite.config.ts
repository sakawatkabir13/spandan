import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(['/api', '/uploads', '/health'].map(prefix => [prefix, {
      target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true,
    }])),
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  test: {
    exclude: ['e2e/**', '**/node_modules/**'],
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
  },
});
