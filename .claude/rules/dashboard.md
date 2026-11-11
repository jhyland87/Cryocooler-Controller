---
paths:
  - "dashboard/**"
---

# Dashboard (Preact + MUI + Vite + TypeScript)

- **TSDoc** file headers (`/** @file … @brief … */`) and one-line `/** */` docs on
  exported symbols and notable members.
- `// ─── Section ───` banner comments group config, helpers, and hooks.
- Function components only. Hooks live in `src/hooks/`, shared types in `src/types/`,
  pure helpers in `src/utils/`.
- Telemetry decoding is generated from `proto/telemetry.proto` (see `telemetry.md`).
  protobufjs turns snake_case proto fields into camelCase.
- Wider TypeScript style (naming, `type` vs `interface`, no `any`) follows the
  Google TypeScript conventions.
- Run the dev server through the preview tools (`dashboard-dev` in
  `.claude/launch.json`, port 5173), not a raw shell. Verify UI changes in the browser.
- Type-check with `npx tsc --noEmit` and build with `npm run build` before calling
  work done. The firmware build embeds `data/`, so a broken dashboard build breaks
  `pio run`.
- No dead code: list unused npm dependencies, components, hooks, and exports, and
  delete them once the user confirms (`general.md`).
