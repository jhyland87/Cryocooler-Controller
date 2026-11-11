---
paths:
  - "src/state_machine*.cpp"
  - "src/state_machine*.h"
  - "src/modules/cold_head.cpp"
  - "src/modules/compressor.cpp"
  - "src/modules/amplifier.cpp"
  - "src/modules/cooling.cpp"
  - "include/config/**"
  - "docs/state_machine.md"
---

# Safety-critical code

This firmware drives a compressor and a high-voltage amplifier on a cryogenic cooler.
Thermal, current, and voltage limits, FSM fault transitions, and hardware interlocks
(e.g. `PG_15V_N` blocking `AMP_REM` until both ±15 V rails are good) protect the
hardware.

- **Never loosen, bypass, or remove a limit or interlock silently.** Call out every
  change to one explicitly: old value, new value, why, and what it puts at risk. Get
  the user's OK first, even when it seems like part of an approved task.
- **Fail safe.** On a missing, stale, or out-of-range sensor reading, go to the fault
  or safe state. Never carry on with the last good value as if it were current.
- Keep limits as named constants in `include/config/`, with units in the name. Don't
  inline magic numbers.
- Any FSM change must keep `docs/state_machine.md` accurate.
- Mock or test hooks (`src/sensor_mock.cpp`, `src/mock_commands.cpp`) must not be able
  to override a safety check in a normal build.
