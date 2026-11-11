---
paths:
  - "src/modules/**"
  - "include/modules/**"
  - "include/module.h"
  - "src/main.cpp"
---

# Firmware module pattern

Every subsystem is a **namespace of free functions** plus a thin CRTP adapter that
the compiler uses to enforce the lifecycle contract. The contract lives in
`include/module.h`, and the full guide is `docs/modules.md`. Use the `add-module`
skill to scaffold a new one.

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

- Register the module in the right `ModuleEntry` array in `src/main.cpp`. **Array
  order encodes init/service dependencies.** The generic helpers (`initGroup`,
  `serviceWithLog`, `reportStatus`) drive it, so don't add per-module boilerplate.
- `init()` returns an `InitStatus` (`MODULE_INIT_SUCCESS`,
  `MODULE_INIT_HARDWARE_ERROR`, …). `service()` returns a `ServiceStatus`
  (`MODULE_SERVICE_OK`, `MODULE_SERVICE_SKIPPED`, `MODULE_SERVICE_ERROR`).
- **Return the honest status.** Callers log health transitions from it, so never
  report OK to hide a fault.
- Optional `enable` / `disable` / `isEnabled` follow the same free-function pattern.
- Declare each SPI IC in the owning module's `.cpp` as a `SpiDevice` or
  `SpiChipSelect` (`include/spi_device.h`; "SPI ICs" in `docs/modules.md`). Use
  `SpiTransaction` for transfers rather than toggling the chip select by hand.
