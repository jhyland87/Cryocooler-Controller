import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import path from 'path';
import fs from 'fs';

/** HOSTNAME from the firmware config, so the dashboard and the board always agree. */
function firmwareHostname(): string {
  const configPath = path.resolve(__dirname, '../include/config/config.h');
  const match = fs.readFileSync(configPath, 'utf8').match(/^#define\s+HOSTNAME\s+"([^"]+)"/m);
  if (!match) {
    throw new Error(`HOSTNAME not found in ${configPath}`);
  }
  return match[1];
}

/** RUN_RECORDER_HOURS from the firmware config: how much history the board keeps. */
function firmwareHistoryHours(): number {
  const configPath = path.resolve(__dirname, '../include/config/config_advanced.h');
  const match = fs.readFileSync(configPath, 'utf8').match(/^#define\s+RUN_RECORDER_HOURS\s.*\((\d+)\)\s*$/m);
  if (!match) {
    throw new Error(`RUN_RECORDER_HOURS not found in ${configPath}`);
  }
  return Number(match[1]);
}

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [preact()],

  define: {
    __ESP32_HOSTNAME__: JSON.stringify(firmwareHostname()),
    __DEV_SERVER__: JSON.stringify(command === 'serve'),
    __RUN_RECORDER_HOURS__: JSON.stringify(firmwareHistoryHours()),
  },

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
}));
