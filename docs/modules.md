# Module System

This document covers the module lifecycle pattern, how to create a new module, and how modules are initialised and serviced in `main.cpp`.

---

## Overview

Every subsystem in the firmware is implemented as a C++ **namespace** with free functions. A thin `Module` struct inside each namespace inherits from `ModuleBase<T>` (CRTP) to provide a standardised lifecycle interface that the compiler enforces at build time.

Modules are registered in **declarative arrays** of `ModuleEntry` descriptors. Generic helpers (`initGroup`, `serviceWithLog`, `reportStatus`) drive init and service loops from these arrays — no per-module boilerplate in `main.cpp`.

**Key files:**

| File | Role |
|------|------|
| `include/module.h` | CRTP base, enums, traits, registry helpers |
| `src/main.cpp` | Module arrays, init groups, service loop |

---

## Lifecycle

Every module goes through two phases:

### 1. Initialisation (`init`)

Called once during `setup()`. Returns an `InitStatus`:

| Status | Meaning |
|--------|---------|
| `MODULE_INIT_NOT_STARTED` | `init()` has not been called yet |
| `MODULE_INIT_IN_PROGRESS` | Still running (calibration, WiFi, etc.) |
| `MODULE_INIT_SUCCESS` | Completed successfully |
| `MODULE_INIT_HARDWARE_ERROR` | Hardware device failed to respond (I2C/SPI NACK) |
| `MODULE_INIT_DEPENDENCY_ERROR` | A required dependency is unavailable |
| `MODULE_INIT_CONFIG_ERROR` | Invalid or missing configuration |
| `MODULE_INIT_TIMEOUT` | Exceeded allowed time budget |
| `MODULE_INIT_UNKNOWN_ERROR` | Catch-all |

### 2. Service (`service`)

Called every `loop()` tick. Returns a `ServiceStatus`:

| Status | Meaning |
|--------|---------|
| `MODULE_SERVICE_NOT_STARTED` | `service()` has not been called yet |
| `MODULE_SERVICE_OK` | Ran and produced valid output this tick |
| `MODULE_SERVICE_SKIPPED` | Skipped this tick (time-gated, disabled, no new data) |
| `MODULE_SERVICE_ERROR` | A recoverable error occurred; output may be stale |

---

## Creating a New Module

### Step 1: Define the namespace and functions

```cpp
// include/mymodule.h
#pragma once
#include "module.h"

namespace mymodule {

module::InitStatus    init();
module::ServiceStatus service();
float getValue();

// ── Module adapter ──────────────────────────────────────────────
struct Module : ModuleBase<Module> {
    static module::InitStatus    init()    { return _initStatus = mymodule::init(); }
    static module::ServiceStatus service() { return _serviceStatus = mymodule::service(); }
};

ASSERT_MODULE_INTERFACE(Module);

} // namespace mymodule
```

### Step 2: Implement the functions

```cpp
// src/mymodule.cpp
#include "mymodule.h"
#include "hardware.h"
#include "logger.h"

static LogStream _Log = Log.createChildLogger("mymodule");

namespace mymodule {

module::InitStatus init() {
    // Hardware setup, calibration, etc.
    TwoWire& i2c = hardware::i2c();
    i2c.beginTransmission(0x42);
    if (i2c.endTransmission() != 0) {
        return module::MODULE_INIT_HARDWARE_ERROR;
    }
    _Log.println("Sensor detected");
    return module::MODULE_INIT_SUCCESS;
}

module::ServiceStatus service() {
    // Non-blocking periodic work
    // ...
    return module::MODULE_SERVICE_OK;
}

float getValue() { return 42.0f; }

} // namespace mymodule
```

### Step 3: Register in `main.cpp`

Add the module to the appropriate array:

```cpp
#include "mymodule.h"

// Add to the appropriate group:
static const module::ModuleEntry persistentModules[] = {
    // ... existing entries ...
    MODULE_ENTRY(mymodule, false),   // false = non-fatal init failure
};
```

That's it. The module will be automatically initialised, serviced, and included in the boot status banner.

### Key rules

1. **`init()` must cache its result** by assigning to `_initStatus`:
   ```cpp
   static module::InitStatus init() { return _initStatus = mymodule::init(); }
   ```

2. **`service()` must cache its result** by assigning to `_serviceStatus`:
   ```cpp
   static module::ServiceStatus service() { return _serviceStatus = mymodule::service(); }
   ```

3. **`service()` must not block.** Use time-gating, state machines, or async patterns for long operations.

4. **Use `ASSERT_MODULE_INTERFACE(Module);`** after the struct definition. This produces a clear compile error if `init()` or `service()` is missing or has the wrong return type.

---

## Module Registry

### `ModuleEntry` struct

A type-erased descriptor with function pointers — no vtable, no heap allocation:

```cpp
struct ModuleEntry {
    const char*    name;
    InitStatus     (*initFn)();
    InitStatus     (*getInitStatus)();
    ServiceStatus  (*serviceFn)();
    ServiceStatus  (*getServiceStatus)();
    bool           fatal;   // true = halt startup if init fails
};
```

### `MODULE_ENTRY` macro

Creates a `ModuleEntry` from any namespace containing a conforming `Module` struct:

```cpp
MODULE_ENTRY(cooling, false)
// expands to:
// { "cooling", cooling::Module::init, cooling::Module::getInitStatus,
//   cooling::Module::service, cooling::Module::getServiceStatus, false }
```

### Helper functions

All three are templates that accept any printf-style log function:

| Function | Purpose |
|----------|---------|
| `module::initGroup(entries, count, emitFn, logFn, yieldFn)` | Initialise every module in an array. Logs before/after each init. Calls optional `emitFn` (e.g. `telemetry::emitSafe`) after each step for dashboard progress. Calls optional `yieldFn` to feed the FreeRTOS watchdog. Returns `false` if any fatal entry fails. |
| `module::serviceWithLog(entry, prevStatus, logFn)` | Service a module and log only on health-status transitions (healthy ↔ unhealthy). Prevents per-tick spam. |
| `module::reportStatus(entries, count, logFn)` | Print the boot banner — lists all modules that failed to init. Returns the failure count. |

---

## Module Groups in `main.cpp`

Modules are organised into four arrays. **Order within each array encodes dependency constraints.**

### Persistent modules

Initialised once at boot. Never re-initialised on `reinit`. These provide the communication path (console, dashboard, telemetry) that the operator uses to issue commands.

```
logger → imu → commands → ota → dashboard → [espnow] → telemetry → sysinfo
```

- OTA before dashboard (routes must be registered before the HTTP server starts)
- dashboard before espnow (WiFi must be up)

### Control modules

Re-initialised on every FSM `reinit()` (entering the Initialize state). This allows hardware peripherals to be reconfigured after a logical system reset without a full MCU reboot.

```
[compressor] → cooling → amplifier → cold_head
```

- compressor first (de-energise relay as early as possible)

### Tick-service modules

Serviced every `loop()` iteration with health-transition logging:

```
sysinfo → imu → amplifier → cooling
```

### Boot banner

A combined array of all modules (including special-cased ones) used for the one-time status report on the first `loop()` iteration.

---

## Special-Cased Modules

These modules don't fit the uniform init/service signature and remain hand-coded in `main.cpp`:

| Module | Reason |
|--------|--------|
| `hardware` | Fatal init — halts startup if it fails. Initialised before all other modules. |
| `indicator` | Must init before WiFi to avoid `neopixelWrite()` deadlock on ESP32-S3. Has its own timer-driven `update(nowMs)` in the loop. |
| `state_machine` | Non-standard `update(tempC, coolingRate, rmsV, stalled, nowMs, overstroke, sysVoltage)` signature. Returns actuator targets. |
| `telemetry` | `emit(out)` takes `state_machine::Output` as input. `emitSafe()` is used during init for dashboard progress. |
| `cold_head` | In the time-gated section of the loop, before `state_machine::update()`. Includes fault checking internally. |
| `sensor_mock` | No `Module` struct. Called once per gated tick to advance mock ramps before module reads. |
| `commands` | Serviced unconditionally every tick (before the time gate) so the console is always reachable. |

---

## Init Flow (setup)

```
setup()
  │
  ├─ hardware::Module::init()        [FATAL — halts on failure]
  ├─ indicator::Module::init()       [before WiFi]
  │
  ├─ initPersistentModules()         [logger, imu, commands, ota, dashboard, ...]
  │   └─ module::initGroup(persistentModules, ..., telemetry::emitSafe, yield)
  │
  ├─ state_machine::Module::init()   [pure logic, always succeeds]
  │
  └─ state_machine::reinit()
      └─ initControlModules()        [cooling, amplifier, cold_head, ...]
          └─ module::initGroup(controlModules, ..., telemetry::emitSafe, yield)
```

## Service Flow (loop)

```
loop()
  │
  ├─ commands::Module::service()     [unconditional — console always reachable]
  │
  ├─ tickServiceModules[]            [sysinfo, imu, amplifier, cooling]
  │   └─ module::serviceWithLog()    [logs only health transitions]
  │
  ├─ hardware::serviceI2c(nowMs)     [I2C error monitor + bus recovery]
  ├─ indicator::update()             [at INDICATOR_UPDATE_INTERVAL_MS cadence]
  │
  └─ [LOOP_INTERVAL_MS gate]
      ├─ sensor_mock::service()      [advance mock ramps]
      ├─ cold_head::service()        [read RTD + fault check]
      ├─ state_machine::update(...)  [returns actuator targets]
      ├─ indicator::set{Fault,Ready}Mode()
      ├─ compressor::Module::service()
      ├─ telemetry::emit(out)
      └─ dashboard::Module::service()
```

---

## Optional Interface

`ModuleBase<T>` provides default implementations for optional methods. Override only what you need:

| Method | Default | Override when... |
|--------|---------|------------------|
| `service()` | Returns `SERVICE_SKIPPED` | Module has periodic work |
| `enable()` | No-op | Module output can be suspended |
| `disable()` | No-op | Module output can be suspended |
| `isEnabled()` | Returns `true` | Module tracks enabled state |

### Status queries (provided by ModuleBase, no override needed)

| Method | Returns |
|--------|---------|
| `getInitStatus()` | Cached `InitStatus` from last `init()` call |
| `isInitialized()` | `true` if init status is `SUCCESS` |
| `getServiceStatus()` | Cached `ServiceStatus` from last `service()` call |
| `overrideInitStatus(s)` | Override cached status (for deferred/hot-plug init) |

---

## Deferred (Hot-Plug) Initialisation

Some hardware (e.g. the EMC2302 fan controller) may not be powered at boot. The pattern for handling this:

1. `init()` returns `MODULE_INIT_HARDWARE_ERROR` when the device is absent.
2. `service()` checks `Module::getInitStatus() != SUCCESS` and periodically retries.
3. On success, call `Module::overrideInitStatus(MODULE_INIT_SUCCESS)` to promote the module.
4. On I2C failure, call `hardware::reportI2cError()` and `hardware::recoverI2c()` to free the shared bus.

See `src/cooling.cpp` for a complete example.

---

## Compile-Time Enforcement

### Trait detection

`module_traits::is_module<T>` returns `true` at compile time if `T` has both `init()` and `service()` with the correct return types. Used internally by `ASSERT_MODULE_INTERFACE`.

### `ASSERT_MODULE_INTERFACE(Module)`

Place this immediately after your `Module` struct definition. It produces a descriptive static_assert failure if the interface is not satisfied:

```
error: static assertion failed: Module does not satisfy the Module interface:
       must provide static module::InitStatus init()
       and static module::ServiceStatus service()
```

---

## Conventions

- **Namespace = module name.** The namespace name is used in log output, serial commands, and the boot banner.
- **One `.cpp` + one `.h` per module.** The header declares the public API; the implementation file is self-contained.
- **Static state.** Module state is file-scope `static` variables in the `.cpp` file. No globals, no singletons.
- **Child loggers.** Each module creates `static LogStream _Log = Log.createChildLogger("name");` for prefixed log output.
- **Bus access via `hardware::`** — never use the global `Wire` or `SPI` directly.
- **Mock support.** When `sensor_mock::isActive()`, skip hardware reads and pull values from `sensor_mock::get()` instead.
- **Non-blocking.** `service()` must return promptly. Use state machines or time-gating for multi-step operations.
