# Style Guide

Coding conventions for this repository. The C++ firmware and the TypeScript
dashboard each have their own idioms; match the surrounding code, and prefer an
existing pattern over inventing a new one.

---

## C++ firmware

### Module pattern (the core convention)

Every subsystem is a **namespace of free functions** plus a thin CRTP adapter
that the compiler uses to enforce the lifecycle contract. See
[`include/module.h`](include/module.h) and [`docs/modules.md`](docs/modules.md).

```cpp
namespace mymodule {

module::InitStatus    init();      // called once from setup(); must not block
module::ServiceStatus service();   // called every loop() tick; must not block

struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return mymodule::init(); }
    static module::ServiceStatus service() { return mymodule::service(); }
};
ASSERT_MODULE_INTERFACE(Module);

} // namespace mymodule
```

- Register the module in the appropriate `ModuleEntry` array in
  [`src/main.cpp`](src/main.cpp) — array order encodes init/service dependencies.
- Guard `Module` structs that call `millis()` (or other Arduino APIs) with
  `#ifdef ARDUINO` so the `native` host-test build still compiles.
- `init()` returns an `InitStatus` (`MODULE_INIT_SUCCESS`,
  `MODULE_INIT_HARDWARE_ERROR`, …). `service()` returns a `ServiceStatus`
  (`MODULE_SERVICE_OK`, `MODULE_SERVICE_SKIPPED`, `MODULE_SERVICE_ERROR`).
  Return the honest status — callers log health transitions from it.

### The no-blocking rule

**Blocking code is only allowed in `setup()` / module `init()`.** Nothing in
`loop()` or any `service()` may block (no `delay()`, no busy-waits, no blocking
I/O). Time-gate periodic work against `tick::nowMs()` and return
`MODULE_SERVICE_SKIPPED` when there is nothing to do this tick.

### Timing

Call `tick::update()` at the top of `loop()`, then read `tick::nowMs()` /
`tick::deltaMs()` everywhere else — do not sprinkle `millis()` calls that drift
within a tick.

### Naming

- Descriptive names; **no single-letter or ambiguous variable names.**
- `UpperCamelCase` for types/structs/enums; `lowerCamelCase` for functions and
  variables; `CONSTANT_CASE` for compile-time constants and macros.
- Namespaces are lower_snake or lowercase matching the subsystem (`cold_head`,
  `imu`). Proto message `ColdHead` maps to telemetry prefix `cold_head`.

### Control flow

Prefer early returns / guard clauses over deep nesting. Keep the happy path at
the base indentation.

### Comments — Doxygen

The firmware is Doxygen-documented. Match the existing house style:

- **File header** on every hand-written `.h`/`.cpp`:
  ```cpp
  /**
   * @file mymodule.h
   * @brief One-line summary of what this unit owns.
   *
   * Longer prose if useful.
   */
  ```
- **Every public/exported function** gets a `/** */` block with a description,
  `@param` for each parameter, and `@return` where it returns a value. Terse
  one-line `/** ... */` is fine for obvious members. `///` single-line docs are
  also accepted (both are used in the codebase).
- Use `@code ... @endcode` for examples and the
  `// ─── Section ───` banner comments to group related declarations.
- Keep implementation comments short (`//`), explaining *why*, not narrating.
- **Never edit generated files** (`web_content.h`, `*.pb.*`, `*/generated/*`).

Regenerate docs with `doxygen Doxyfile` (see [`AGENTS.md`](AGENTS.md)).

---

## TypeScript dashboard (`dashboard/`)

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
