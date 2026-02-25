# ESP32-S3 Cryocooler Controller

Firmware for an ESP32-S3 DevKit that automates the cooldown sequence of a cryogenic cooler. The controller manages a compressor-driven cold stage through ten operational states — from a cold start at room temperature (~295 K) down to an operating setpoint of 78 K, with a graceful shutdown sequence — while enforcing thermal safety limits, detecting back-EMF current spikes, streaming live telemetry to Serial Studio, and serving real-time data as JSON over WiFi.

---

## Hardware

| Component | Part | Interface | Purpose |
|-----------|------|-----------|---------|
| Microcontroller | ESP32-S3 DevKitC-1 | — | Host MCU |
| Cold-stage sensor | MAX31865 + PT100 RTD | SPI (CS: GPIO 1) | Cold-stage temperature |
| Ambient sensor | DS18B20 / DS18S20 | 1-Wire (GPIO 4) | Room temperature |
| Waveform generator | AD9833 DDS | SPI (CS: GPIO 7) | 60 Hz sine wave for compressor |
| DAC | MCP4921 12-bit | SPI (CS: GPIO 6) | Compressor power control |
| Current sensor | ACS712-05B | ADC (GPIO 14) | Back-EMF spike detection |
| IMU | QMI8658 | I²C (SDA: GPIO 8, SCL: GPIO 9) | Vibration / overstroke detection |
| 12 V rail monitor | Resistor divider | ADC (GPIO 10) | Supply voltage monitoring |
| DAC voltage readback | — | ADC (GPIO 9) | DAC output verification |
| Status LED | WS2812 RGB | GPIO 38 | Fault / Ready indication |
| Bypass relay | — | GPIO 11 | Normal / Bypass switching |
| Alarm relay | — | GPIO 12 | External fault signalling |

**SPI bus** (shared by MAX31865, AD9833, MCP4921): MOSI → GPIO 42, MISO → GPIO 41, CLK → GPIO 40.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              main.cpp                                   │
│  setup()                          loop()                                │
│  ├─ SPI.begin()                   ├─ [every iteration]                 │
│  ├─ waveform::init()              │   ├─ device::service()             │
│  ├─ temperature::init()           │   ├─ waveform::service()           │
│  ├─ dac::init()                   │   ├─ dacVoltageAdc.service()       │
│  ├─ rms::init()                   │   ├─ serial_commands::service()    │
│  ├─ relay::init()                 │   └─ indicator::update()           │
│  ├─ indicator::init()             │                                     │
│  ├─ http_api::init()              └─ [every 200 ms]                    │
│  ├─ state_machine::init()             ├─ 1. Read sensors               │
│  └─ serial_commands::init()           ├─ 2. Advance state machine      │
│                                       ├─ 3. Drive actuators            │
│                                       ├─ 4. HTTP API service           │
│                                       └─ 5. Emit telemetry             │
└─────────────────────────────────────────────────────────────────────────┘

Modules (each a C++ namespace):

  temperature   ──► state_machine ──► relay
  rms           ──►               ──► dac
  accelerometer ──►               ──► indicator
                                      │
                              telemetry / FrameBuilder ──► Serial Studio
                                                       ──► http_api (JSON)
```

---

## Module Reference

### `state_machine`

The core of the controller. Ingests sensor readings every 200 ms and outputs a complete set of actuator targets. Contains no hardware calls — pure logic, fully unit-testable on the host PC.

**States:**

| # | Name | Description | FAULT LED | READY LED | DAC | Relay |
|---|------|-------------|-----------|-----------|-----|-------|
| -1 | Off | System powered down | — | — | 0 | Bypass |
| 0 | Initialize | Power-up self-check (1.5 s amber flash) | Amber | Amber | 0 | Bypass |
| 1 | Idle | Warm standby | Solid Red | Off | 0 | Bypass |
| 2 | CoarseCooldown | Cooling above 85 K; DAC ramps up | Flash Fast Red | Off | Ramps | Bypass |
| 3 | FineCooldown | Cooling below 85 K | Flash Fast Red | Flash Slow Green | Ramps | Bypass |
| 4 | Overshoot | Below setpoint, integrator settling | Flash Fast Red | Flash Fast Green | Holds | Bypass |
| 5 | Settle | Near setpoint; Normal relay engages | Flash Fast Red | Flash Fast Green | Holds | Normal |
| 6 | Baseline | Collecting pre-run baseline (5 min) | Off | Solid Green | Holds | Normal |
| 7 | Operating | Normal cryogenic operation | Off | Solid Green | Holds | Normal |
| 8 | Shutdown | Graceful shutdown; DAC ramps down (~5 s) | Off | Off | Ramps→0 | Bypass |
| 127 | Fault | Any fault condition (terminal state) | Solid Red | Off | 0 | Bypass + Alarm |

**Transition triggers:**

```
Off         ──[start()]──► CoarseCooldown (or FineCooldown / Overshoot / Settle,
                            depending on current temperature)
Initialize  ──[auto]──► Idle
Idle        ──[start()]──► CoarseCooldown
Coarse      ──[temp < 85 K]──► FineCooldown
Fine        ──[temp ≤ setpoint + tolerance]──► Overshoot
Fine        ──[temp in setpoint band]──► Settle
Overshoot   ──[temp in setpoint band]──► Settle
Settle      ──[stable for 60 s]──► Baseline
Baseline    ──[5 min elapsed]──► Operating
Any         ──[RMS overvoltage | temp stall | too many backoffs]──► Fault
Coarse/Fine ──[stop()]──► Shutdown
Overshoot   ──[stop()]──► Shutdown
Settle      ──[stop()]──► Shutdown
Baseline    ──[stop()]──► Shutdown
Operating   ──[stop()]──► Shutdown
Shutdown    ──[~5 s elapsed]──► Idle
Any         ──[off()]──► Off
```

**Back-EMF backoff:** When the ACS712 detects a current spike exceeding the EMA baseline by `OVERSTROKE_CURRENT_THRESHOLD_A` (2 A), the DAC target is decremented by `BACKOFF_DAC_STEP` (200 counts). After `BACKOFF_MAX_COUNT` (10) cumulative events the machine enters Fault.

**Key configuration** (all in `config.h`):

| Constant | Default | Description |
|----------|---------|-------------|
| `SETPOINT_K` | 78.0 K | Target cold-stage temperature |
| `COARSE_FINE_THRESHOLD_K` | 85.0 K | Coarse/Fine transition boundary |
| `SETPOINT_TOLERANCE_K` | 2.0 K | Band around setpoint for settle/overshoot logic |
| `SETTLE_DURATION_MS` | 60 000 ms | Time stable before advancing to Baseline |
| `BASELINE_DURATION_MS` | 300 000 ms | Baseline collection window |
| `SHUTDOWN_DURATION_MS` | 5 000 ms | Duration of graceful shutdown sequence |
| `STALL_DETECT_WINDOW_MS` | 600 000 ms | Stall detection observation window (10 min) |
| `STALL_MIN_DROP_K` | 2.0 K | Minimum drop required within the window |
| `MAX_COOLDOWN_RATE_K_PER_MIN` | 1.0 K/min | Maximum allowed cooling rate |
| `DAC_MAX_STEP_PER_INTERVAL` | 5 counts | Normal ramp rate limiter (smooth cooldown) |
| `DAC_SHUTDOWN_STEP_PER_INTERVAL` | 200 counts | Fast ramp rate for shutdown sequence |

---

### `temperature`

Drives the MAX31865 breakout board over SPI to read the PT100 RTD and converts the raw resistance to Kelvin/Celsius. Also reads a DS18B20/DS18S20 on the 1-Wire bus for ambient (room) temperature.

Internally maintains a ring buffer of `TEMP_HISTORY_SIZE` (20) timestamped samples for:
- **Cooling-rate calculation** — linear fit over oldest and newest samples (K/min)
- **Stall detection** — compares head and tail of the window; triggers fault if the drop is less than `STALL_MIN_DROP_K` within `STALL_DETECT_WINDOW_MS`
- **Cooldown progress** — maps current temperature to 0–100 % between ambient start (295 K) and setpoint (78 K)

| Function | Returns |
|----------|---------|
| `getLastTempK()` | Cold-stage temperature in Kelvin |
| `getLastTempC()` | Cold-stage temperature in Celsius |
| `getLastAmbientTempC()` | Room temperature in Celsius (DS18B20) |
| `getLastTempCBelowAmbient()` | `ambient − cold_stage` in Celsius |
| `getCoolingRateKPerMin()` | K/min, positive = cooling |
| `isStalled()` | True if stall threshold is exceeded |
| `getTemperatureToPercent()` | Cooldown progress 0–100 % |

---

### `accelerometer`

Drives the QMI8658 6-DOF IMU over I²C (SDA: GPIO 8, SCL: GPIO 9). On `init()` the sensor is configured at 1000 Hz ODR for both accelerometer (±8 g) and gyroscope (±512 dps), then a one-time blocking calibration collects 1000 samples to compute per-axis offsets (gravity is removed from the Z accel offset). No `delay()` calls are used — the calibration loop spins on `readSensorData()` which returns false when no new sample is ready.

Each `service()` call applies calibration offsets, runs a first-order low-pass filter (`α = 0.1`), computes roll/pitch (from filtered accel) and yaw (open-loop gyro integration), and checks for motion. All computed values are stored as module state and accessible via getters.

**Motion / overstroke detection:** A reading is classified as motion when the acceleration magnitude deviates from 9.81 m/s² by more than `ACCEL_THRESHOLD_MPS2` (2.0) or the gyroscope magnitude exceeds `GYRO_THRESHOLD_DPS` (10.0). The flag clears automatically after `MOTION_TIMEOUT_MS` (2000 ms) of stillness.

| Function | Returns |
|----------|---------|
| `isInitialized()` | True if the sensor was found and configured |
| `isMotionDetected()` | True while motion is active |
| `hasOverstroke()` | Alias for `isMotionDetected()` — matches `rms::hasOverstroke()` contract |
| `getRoll()` | Roll angle in degrees |
| `getPitch()` | Pitch angle in degrees |
| `getYaw()` | Yaw angle in degrees (open-loop gyro integration; drifts over time) |
| `getAccelMag()` | Calibrated acceleration magnitude in m/s² (unfiltered) |
| `getGyroMag()` | Calibrated gyroscope magnitude in deg/s (unfiltered) |
| `getTemperature()` | IMU die temperature in °C |

---

### `rms`

Houses two independent measurements on the AC output line:

**1. RMS-to-DC converter** (`read()` / `getVoltage()`) — currently stubbed at 0 V. Reserved for a future hardware driver. Triggers a Fault if voltage exceeds `RMS_MAX_VOLTAGE_VDC` (120 V).

**2. ACS712-05B current sensor** (`readCurrent()` / `getCurrentA()`) — uses the custom `ContinuousZMCT103C` library in continuous non-blocking RMS mode. `updateContinuousRMS()` is called every 200 ms tick and updates an exponential moving average of mean and mean-square. Mean-centering (`useMeanCenter = true`, the default) eliminates the need for explicit zero-current calibration.

**Overstroke (back-EMF) detection:** A separate slow-tracking EMA (`OVERSTROKE_EMA_ALPHA = 0.08`) forms the baseline. A current reading that exceeds `baseline + OVERSTROKE_CURRENT_THRESHOLD_A` fires `hasOverstroke()`, subject to `OVERSTROKE_DEBOUNCE_MS`. The EMA is primed for `OVERSTROKE_PRIME_READINGS` (20) ticks on startup to prevent false triggers.

---

### `dac`

Drives the MCP4921 12-bit DAC over SPI to set the compressor power level (0 – 4095 counts). Provides three write modes:

- `update(val)` — immediate write; skips SPI if value unchanged
- `rampToward(target)` — increments/decrements by at most `DAC_MAX_STEP_PER_INTERVAL` (5 counts) per call, enforcing a smooth power ramp (~164 s for full-scale at 200 ms ticks)
- `rampTowardShutdown(target)` — fast ramp using `DAC_SHUTDOWN_STEP_PER_INTERVAL` (200 counts) per call for graceful shutdown (~4 s full-scale descent). Prevents motor stress without abrupt voltage spikes

---

### `waveform`

Initialises the AD9833 DDS to output a continuous 60 Hz sine wave (`AD9833_FREQ_HZ`). This signal drives the compressor input. `service()` is called every loop iteration to keep the driver state machine ticking.

---

### `relay`

Controls two relays via discrete GPIO outputs:

- **Bypass relay** (GPIO 11) — LOW = Bypass mode (safe default); HIGH = Normal mode (engaged during Settle, Baseline, Operating)
- **Alarm relay** (GPIO 12) — HIGH = fault signalling to external systems; active only in Fault state

Both pins are driven LOW during `init()`, ensuring a safe-default state at boot.

---

### `indicator`

Drives the on-board WS2812 RGB LED (GPIO 38) and optional discrete FAULT/READY digital outputs according to the state machine's requested `Mode` enum. All flash timing is non-blocking — `update(nowMs)` is called every loop iteration regardless of the 200 ms gate.

| Mode | Colour | Rate |
|------|--------|------|
| `SolidRed` | Red | — |
| `SolidGreen` | Green | — |
| `SolidAmber` | Amber | — |
| `FlashFastRed` | Red | 2 Hz |
| `FlashSlowGreen` | Green | 1 Hz |
| `FlashFastGreen` | Green | 2 Hz |

---

### `device`

Reads the 12 V supply rail via an ADC-connected resistor divider (GPIO 10) with EMA smoothing. Exposes `getVoltage()` (scaled V) and `getVoltageRaw()` (raw ADC count). `service()` is called every loop iteration.

---

### `frame_builder`

A reusable, format-agnostic telemetry frame. Fields are appended via a fluent API:

```cpp
FrameBuilder frame;
frame.field("temp_c",  "%.2f", temperature::getLastTempC())
     .field("state",   "%d",   static_cast<int>(currentState))
     .field("label",   "%s",   "Running");
```

The C++ type of the value argument is detected at compile time (`if constexpr`) and stored alongside the formatted string so the frame can be rendered in multiple formats without re-reading hardware:

| Method | Output |
|--------|--------|
| `sendSerial(Print&)` | `/*v1\|v2\|...\|v35*/\r\n` (Serial Studio wire format) |
| `fillJson(JsonDocument&)` | `{"name": typed_value, ...}` — numbers as JSON numbers, strings as JSON strings |

---

### `telemetry`

Calls `FrameBuilder` each 200 ms tick to snapshot all 35 module values, sends the frame to Serial, and stores it as `lastFrame_`. Other modules retrieve the stored frame without re-reading hardware:

```cpp
telemetry::getLastFrame()          // const FrameBuilder& — full frame access
telemetry::fillJson(doc)           // convenience wrapper → JsonDocument
```

**Full field list** (Serial Studio column order):

| # | Key | Type | Description |
|---|-----|------|-------------|
| 1 | `state_no` | int | State index (−1 to 127, with Fault = 127) |
| 2 | `state_name` | string | State label (e.g. `"CoarseCooldown"`) |
| 3 | `status_text` | string | Human-readable status |
| 4 | `temp_k` | float | Cold-stage temperature (K) |
| 5 | `temp_c` | float | Cold-stage temperature (°C) |
| 6 | `ambient_temp_c` | float | Room temperature (°C) |
| 7 | `cooling_rate` | float | Cooling rate (K/min) |
| 8 | `dac_target` | uint | DAC target from state machine (0–4095) |
| 9 | `dac_actual` | uint | DAC value written to hardware (0–4095) |
| 10 | `rms_v` | float | RMS output voltage (V) |
| 11 | `relay_normal` | uint | 0 = Bypass, 1 = Normal |
| 12 | `alarm_relay` | uint | 0 = off, 1 = active |
| 13 | `red_led` | int | FAULT LED lit this tick |
| 14 | `green_led` | int | READY LED lit this tick |
| 15 | `on_duration_ms` | ulong | Total run time (ms) |
| 16 | `on_duration` | string | Total run time (HH:MM:SS) |
| 17 | `cooldown_pct` | float | Cooldown progress 0–100 % |
| 18 | `time_in_state` | string | Time in current state (HH:MM:SS) |
| 19 | `current_a` | float | ACS712 AC RMS current (A) |
| 20 | `backoff_count` | uint | Cumulative back-EMF backoffs this run |
| 21 | `delta_below_ambient_c` | float | ambient − cold_stage (°C) |
| 22 | `voltage_v` | float | 12 V supply voltage (V) |
| 23 | `voltage_raw` | float | Raw ADC voltage reading |
| 24 | `waveform_status` | uint | AD9833 status code |
| 25 | `frequency_hz` | float | AD9833 output frequency (Hz) |
| 26 | `accel.roll_deg` | float | IMU roll angle (°) |
| 27 | `accel.pitch_deg` | float | IMU pitch angle (°) |
| 28 | `accel.yaw_deg` | float | IMU yaw angle — open-loop gyro integration (°) |
| 29 | `accel.accel_mag` | float | Acceleration magnitude (m/s²) |
| 30 | `accel.gyro_mag` | float | Gyroscope magnitude (deg/s) |
| 31 | `accel.temp_c` | float | IMU die temperature (°C) |
| 32 | `accel.motion` | uint | 1 = motion / overstroke detected, 0 = still |
| 33 | `accel.x` | float | Filtered X-axis acceleration (m/s²) |
| 34 | `accel.y` | float | Filtered Y-axis acceleration (m/s²) |
| 35 | `accel.z` | float | Filtered Z-axis acceleration (m/s²) |

To add a field: append one `.field(name, fmt, value)` call to `emit()` in `telemetry.cpp` and add a row to the table above.

**Serial Studio setup:** connect at 115200 baud, enable Frame Detection with start sequence `/*` and end sequence `*/`, then load `Cryocooler Dashboard.ssproj`.

---

### `http_api`

Connects to WiFi at startup and serves telemetry as JSON on port 80.

```
GET /  →  200 application/json
```

```json
{
  "state_no": 2,
  "state_name": "CoarseCooldown",
  "temp_k": 210.34,
  "temp_c": -62.81,
  "current_a": 1.24,
  ...
}
```

The response is built from `telemetry::fillJson()` (the last emitted frame — no additional hardware reads). The JSON is serialised directly to the TCP client stream via `measureJsonPretty` + `serializeJsonPretty`, so no large intermediate buffer is allocated.

WiFi credentials live in `src/arduino_secrets.h` (not committed — see setup below).

---

### `serial_commands`

Non-blocking line-by-line USB serial command handler. `service()` accumulates characters from `Serial` and dispatches completed lines to `processLine()`. The same `processLine()` function is used by unit tests with a stub `Print`.

| Command | Action |
|---------|--------|
| `start` | Begin cooldown (from Off or Idle); resumes at the correct state if already cold |
| `stop` | Abort cooldown, return to Idle |
| `off` | Return to Off state |
| `status` | Print current state, running flag, and on-duration |
| `summary` | Full snapshot of all sensor and actuator values |
| `board` | Print compile-time platform/build info |
| `help` | List all commands with descriptions |
| `telemetry on/off` | Enable or disable Serial Studio frame output |

---

### `conversions`

Header-only pure-math utilities with no hardware dependencies — safe to include in native unit tests.

| Function | Description |
|----------|-------------|
| `rtdRawToResistance(raw, rRef)` | MAX31865 raw register → resistance (Ω) |
| `celsiusToKelvin(c)` | °C → K |
| `celsiusToFahrenheit(c)` | °C → °F |
| `fahrenheitToCelsius(f)` | °F → °C |
| `tempKToDacValue(tempK, ambientK, setpointK, maxDac)` | Linear temperature → 12-bit DAC mapping |
| `msToHHMMSS(ms, buf)` | Milliseconds → `HH:MM:SS` string |

---

## Setup Sequence

```
setup()
 │
 ├─ Serial.begin(115200)  ── wait for USB-CDC enumeration
 ├─ analogReadResolution(12)
 ├─ SPI.begin(CLK=40, MISO=41, MOSI=42)
 │
 ├─ SmoothADC init ── prime DAC voltage readback filter (8 samples)
 │
 ├─ waveform::init()     ── configure AD9833, start 60 Hz sine output
 ├─ temperature::init()  ── configure MAX31865, verify RTD connection
 ├─ dac::init()          ── configure MCP4921 CS pin, set DAC to 0
 ├─ rms::init()          ── set ADC attenuation, begin ContinuousZMCT103C
 ├─ accelerometer::init() ── configure QMI8658, calibrate offsets (~1 s)
 ├─ relay::init()        ── both relays to LOW (Bypass + alarm off)
 ├─ indicator::init()    ── configure GPIO pins, WS2812 driver
 ├─ http_api::init()     ── connect WiFi, start mDNS ("esp32.local"), start HTTP server
 │
 ├─ state_machine::init(millis())  ── enter Off state
 └─ serial_commands::init()        ── clear line buffer
```

---

## Loop Sequence

The loop runs in two tiers: **every iteration** (unconstrained, ~microsecond cadence) and **every 200 ms** (gated by `LOOP_INTERVAL_MS`).

```
loop()
 │
 ├─ [every iteration]
 │   ├─ device::service()           ── service ADC EMA for 12 V rail
 │   ├─ waveform::service()         ── service AD9833 driver state machine
 │   ├─ dacVoltageAdc.service()     ── service smoothed DAC voltage ADC
 │   ├─ accelerometer::service()    ── read IMU, update orientation + motion state
 │   ├─ serial_commands::service()  ── accumulate serial bytes, dispatch lines
 │   └─ indicator::update(nowMs)    ── advance flash timers, write LEDs
 │
 └─ [every 200 ms]
     │
     ├─ 1. Read sensors
     │   ├─ temperature::read(nowMs)   ── RTD + DS18B20, update ring buffer
     │   ├─ rms::read()               ── RMS voltage (stub)
     │   ├─ rms::readCurrent()        ── tick ContinuousZMCT103C EMA, check overstroke
     │   └─ temperature::checkFaults() ── read and clear MAX31865 fault register
     │
     ├─ 2. Advance state machine
     │   └─ state_machine::update(tempK, coolingRate, rmsV, stalled, nowMs,
     │                            rms::hasOverstroke() || accelerometer::hasOverstroke())
     │       └─ returns Output { state, dacTarget, bypassRelay, alarmRelay,
     │                           faultIndMode, readyIndMode, statusText, backoffCount }
     │
     ├─ 3. Drive actuators
     │   ├─ relay::setBypass(!out.bypassRelay)
     │   ├─ relay::setAlarm(out.alarmRelay)
     │   ├─ indicator::setFaultMode(out.faultIndMode)
     │   ├─ indicator::setReadyMode(out.readyIndMode)
     │   └─ dac::rampToward(out.dacTarget)  ── max ±5 counts per tick
     │
     ├─ 4. HTTP API
     │   └─ http_api::service()  ── handle any pending HTTP client
     │
     └─ 5. Telemetry
         └─ telemetry::emit(out)
             ├─ builds FrameBuilder with all 25 named fields
             ├─ lastFrame_.sendSerial(Serial)  ── Serial Studio frame
             └─ stores lastFrame_ for http_api / serial summary
```

---

## Build & Configuration

### Dependencies (`platformio.ini`)

| Library | Purpose |
|---------|---------|
| `fastled/FastLED` | WS2812 RGB LED |
| `adafruit/Adafruit MAX31865 library` | PT100 RTD sensor |
| `majicdesigns/MD_AD9833` | DDS waveform generator |
| `milesburton/DallasTemperature` | DS18B20 ambient sensor |
| `bblanchon/ArduinoJson` | JSON serialisation (HTTP API + FrameBuilder) |
| `QMI8658` | 6-DOF IMU driver |

The `ContinuousZMCT103C` library lives in `lib/ContinuousZMCT103C/` and is picked up automatically by PlatformIO.

### WiFi credentials

Create `src/arduino_secrets.h` (excluded from version control):

```cpp
#define WIFI_SSID "your-network-name"
#define WIFI_PASS "your-password"
```

### Key tuning parameters (`config.h`)

All application-level constants live in `config.h`. Hardware pin assignments live in `pin_config.h`. Neither file has hardware includes, so both are safe to include in native unit tests.

---

## Testing

Unit tests run on the host PC via PlatformIO's native environment:

```bash
pio test -e native
```

Tests use a minimal Arduino stub (`src/stub.cpp`) that provides `millis()`, a `Print` class with `contains()`, and other shims. The state machine, serial command handler, and telemetry modules are compiled and exercised without any hardware.

Test files live in `test/test_native/`. The shared entry point is `test_state_machine.cpp`, which calls `run_serial_command_tests()` from `test_serial_commands.cpp`.

Embedded integration tests (requiring hardware) live in `test/test_embedded/` and run via:

```bash
pio test -e esp32s3
```
