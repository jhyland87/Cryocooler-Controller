# TypeScript dashboard style (`dashboard/`)

Preact + MUI + Vite. Existing conventions to match:

- **TSDoc** file headers (`/** @file ... @brief ... */`) and one-line `/** */`
  docs on exported symbols and notable members.
- `// ─── Section ───` banner comments to group config / helpers / hooks.
- Components are function components; hooks live in `src/hooks/`, shared types in
  `src/types/`, pure helpers in `src/utils/`.
- `proto/telemetry.proto` drives the generated decoder — remember protobufjs
  converts snake_case proto fields to camelCase on the JS side.

For broader TypeScript style (naming, `type` vs `interface`, no `any`, etc.),
this project follows the standard Google TypeScript conventions where the
dashboard grows.
