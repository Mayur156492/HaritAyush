import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Minimal scaffold configuration. Backend proxying, asset budget rules and
// production build targets will be added once the API contract is approved.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  preview: {
    port: 4173,
  },
});
