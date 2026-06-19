import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'frontend/src'),
    },
  },
  base: '/static/dist/',
  build: {
    outDir: 'static/dist',
    manifest: true,
    rollupOptions: {
      input: {
        'main-patient': path.resolve(__dirname, 'frontend/src/main-patient.tsx'),
        'main-doctor': path.resolve(__dirname, 'frontend/src/main-doctor.tsx'),
        'main-secretary': path.resolve(__dirname, 'frontend/src/main-secretary.tsx'),
        'main-admin': path.resolve(__dirname, 'frontend/src/main-admin.tsx'),
      },
    },
  },
});
