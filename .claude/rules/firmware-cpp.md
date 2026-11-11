---
paths:
  - "src/**"
  - "include/**"
  - "test/**"
  - "lib/**"
  - "platformio.ini"
---

# Firmware C++ conventions

C++17 on Arduino/ESP-IDF (`espressif32@5.3.0`). Match the surrounding code, and prefer
an existing pattern over inventing a new one. Module structure is in
`firmware-modules.md`.

## The no-blocking rule

**Blocking code is only allowed in `setup()` / module `init()`.** Nothing in `loop()`
or any `service()` may block: no `delay()`, busy-waits, or blocking I/O. Time-gate
periodic work against `tick::nowMs()` and return `MODULE_SERVICE_SKIPPED` when there
is nothing to do this tick.

## Timing

`tick::update()` runs at the top of `loop()`. Everywhere else, read `tick::nowMs()` /
`tick::deltaMs()` instead of calling `millis()`, which drifts within a tick.

## Naming

- Descriptive names. **No single-letter or ambiguous variable names.**
- `UpperCamelCase` for types/structs/enums, `lowerCamelCase` for functions and
  variables, `CONSTANT_CASE` for compile-time constants and macros.
- Namespaces are lowercase / lower_snake matching the subsystem (`cold_head`, `imu`).
- **Unit suffixes** on physical quantities: `tempC`, `periodMs`, `currentA`,
  `SETPOINT_C`, `AMPLIFIER_MAX_VOLTAGE_VAC`. Firmware temperatures are **Celsius**,
  not Kelvin.
- Don't name anything after an Arduino.h function-like macro (`bit`, `constrain`,
  `lowByte`, `highByte`, `bitRead`, …). The macro silently rewrites the call. Check
  `framework-arduinoespressif32/cores/esp32/Arduino.h` when in doubt.

## Control flow

Prefer early returns / guard clauses over deep nesting, and keep the happy path at
the base indentation.

## Host-test compatibility

Guard code that calls `millis()` or other Arduino APIs with `#ifdef ARDUINO` so the
`native` test build still compiles.

## Drivers and registers

Register addresses, bit fields, and timing constants come from the datasheet, with
the section/table cited in a comment (e.g. `// DS20001919F Table 1-2`). See
`general.md`: verify, never assume.

## Doxygen comments

- A file header on every hand-written `.h` / `.cpp`:
  ```cpp
  /**
   * @file mymodule.h
   * @brief One-line summary of what this unit owns.
   */
  ```
- Every public/exported function gets a `/** */` block with a description, `@param`
  for each parameter, and `@return` where it returns a value. A terse one-line
  `/** */` or `///` is fine for obvious members.
- `@code … @endcode` for examples. `// ─── Section ───` banners group declarations.
- Implementation comments are short `//` lines that explain *why*, not narration.
- Regenerate the docs with `doxygen Doxyfile` (the `generate-docs` skill).

## Before calling work done

- Build: `SKIP_DASHBOARD_BUILD=1 SKIP_PROTO_BUILD=1 pio run`, or the full `pio run`
  if the dashboard or proto changed.
- Host tests: `pio test -e native`. Add native tests for new pure logic
  (conversions, filters, state decisions).
- Report what was and wasn't tested on real hardware.
