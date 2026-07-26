---
name: add-module
description: Scaffold a new firmware subsystem module following the ModuleBase<T> CRTP lifecycle pattern and register it in main.cpp. Use when adding a new sensor, actuator, or subsystem to the ESP32 firmware.
---

# Add a subsystem module

Every subsystem is a C++ **namespace of free functions** plus a thin
`struct Module : ModuleBase<Module>` (CRTP) that the compiler uses to enforce the
lifecycle. The full authoring guide is [`docs/modules.md`](../../../docs/modules.md);
the contract is in [`include/module.h`](../../../include/module.h). Read both,
then follow these steps and mirror an existing module (e.g.
`include/modules/imu.h` + `src/modules/imu.cpp`).

## Steps

1. **Header** — `include/modules/<name>.h`:
   - Doxygen `@file`/`@brief` block (see `STYLEGUIDE.md`).
   - `namespace <name> { ... }` declaring `module::InitStatus init();` and
     `module::ServiceStatus service();` plus any getters.
   - The CRTP adapter:
     ```cpp
     struct Module : ModuleBase<Module> {
         static module::InitStatus    init()    { return <name>::init(); }
         static module::ServiceStatus service() { return <name>::service(); }
     };
     ASSERT_MODULE_INTERFACE(Module);
     ```
   - Guard the `Module` struct with `#ifdef ARDUINO` if `service()` needs
     `millis()` or other Arduino-only APIs (keeps the `native` test build green).

2. **Source** — `src/modules/<name>.cpp`:
   - `init()` performs setup (blocking is OK here only) and returns an
     `InitStatus` (`MODULE_INIT_SUCCESS` / `MODULE_INIT_HARDWARE_ERROR` / …).
   - `service()` does periodic, **non-blocking** work each tick, time-gated on
     `tick::nowMs()`, returning `MODULE_SERVICE_OK` / `MODULE_SERVICE_SKIPPED` /
     `MODULE_SERVICE_ERROR`.

3. **Register in `src/main.cpp`** — add a `MODULE_ENTRY(<name>, <fatal>)` to the
   correct array; **order encodes dependencies**:
   - `persistentModules[]` — init once at boot, never re-init.
   - `controlModules[]` — re-init on every FSM reinit.
   - `tickServiceModules[]` — serviced every loop tick with health logging.
   - `allModulesForBanner[]` — for the boot status banner.
   Include the new header near the other module includes at the top.

4. **Config** — add pins to `include/config/pin_config.h` and any tunables to
   `include/config/config.h` if needed.

5. **Build** to confirm the interface assertion passes:
   ```bash
   SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run
   ```
   A missing `init()`/`service()` is a compile error, not a silent runtime bug.

## Conventions

- No blocking in `service()` / `loop()` — only in `init()`/`setup()`.
- Descriptive names; no single-letter variables.
- Document every exported function with Doxygen `@param`/`@return`.
- If the module exposes telemetry, use the `add-telemetry-field` skill.
