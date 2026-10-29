import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// point the dev proxy somewhere else with API_TARGET=http://host:port npm run dev
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://localhost:8000',
    },
  },
});
