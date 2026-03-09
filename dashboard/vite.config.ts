import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [preact()],

  resolve: {
    alias: {
      // Map React imports to Preact compatibility layer so MUI components work.
      'react':              path.resolve(__dirname, 'node_modules/preact/compat'),
      'react-dom':          path.resolve(__dirname, 'node_modules/preact/compat'),
      'react/jsx-runtime':  path.resolve(__dirname, 'node_modules/preact/jsx-runtime'),
    },
  },

  build: {
    // Write built files into data/ so embed_web.py can embed them into
    // web_content.h during the PlatformIO firmware build.
    outDir: '../data',

    // Keep OTA files that already live in data/ (ota.html, ota.css, ota.js).
    emptyOutDir: false,

    // Use predictable, hash-free filenames so embed_web.py can reference them
    // by name without knowing build-time content hashes.
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: 'app.js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) return 'style.css';
          return '[name][extname]';
        },
      },
    },

    // Raise the chunk-size warning threshold — MUI + recharts are legitimately
    // large; the firmware has a 26 MB LittleFS partition so size isn't critical.
    chunkSizeWarningLimit: 2048,
  },
});
