import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => ({
  base: './',
  define: {
    __TEST_HOOK__: JSON.stringify(process.env.VITE_TEST_HOOK === '1' || mode === 'development'),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
}));
