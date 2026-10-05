import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    target: 'es2022',
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // Inline the shared UI package so vi.mock('@clerk/clerk-react') also
    // applies inside it (otherwise its prebuilt dist is externalized and keeps
    // the real ClerkProvider, which tries network access in tests).
    server: { deps: { inline: ['@agenteresolve/ui'] } },
  },
});
