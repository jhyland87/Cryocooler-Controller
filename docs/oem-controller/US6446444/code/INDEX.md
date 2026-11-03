# US6446444 firmware appendix ("NCP.OUT")

The firmware for STI's DSP cryocooler controller, transcribed verbatim from the patent appendix (PDF pp13-104).
The target is a **TMS320F243** DSP with a 20 MHz clock, built with TI Code Composer 4.10.36 (patent col. 8). The link
date is Fri May 11 2001 (`NCP.MAP`), and the version string is `4.1.08,05.18.01` (`MAIN.C`). This is the
`TOWER_MOUNT_CODE` (48 V cooler) build; the 12 V values are kept in `#else` branches.

- How it was transcribed, the checks, and per-page notes: [TRANSCRIPTION_NOTES.md](TRANSCRIPTION_NOTES.md)
- Which patent page each file came from: [PAGE_MAP.md](PAGE_MAP.md)
- Re-run the consistency checks with `python3 -I ../../tools/check_code.py`

## Files

| File | What it is |
|---|---|
| [VECTORS.ASM](VECTORS.ASM) | Interrupt vector table. RESET → `_c_int0`, INT2 → `GISR2`, INT3 → `GISR3`, INT5 → `GISR5`. Unused vectors go to `PHANTOM`, which counts them. |
| [BOOT.ASM](BOOT.ASM) | Reset and C start-up (`_c_int0`, `_hw_init`, `_var_init`). Sets up the stack, wait states, watchdog, event manager (PWM) and SCI/SPI. |
| [ISRS.ASM](ISRS.ASM) | Interrupt handlers. **GISR2:** timer-1 period (the PWM system); steps through the 256-entry **sine table** `_sTable` and writes `sValue × sGain + sOffset` to the PWM compare registers. **GISR3:** timer 2; spin decrement, watchdog, motor-current ADC sample into `ImotBuf`. **GISR5:** SCI receive/transmit and SPI. The sine table fills the end of the file. |
| [AFUNCS.ASM](AFUNCS.ASM) | `_BlockMove`: moves strings stored in program memory to data memory. |
| [GLOBALS.H](GLOBALS.H) | Global constants. `CLOCKS_PER_SEC 480` (2.083 ms tick); motor current limits `MIN_IMOT`/`MAX_IMOT` (90L ≈ 12 A p-p at 48 V; 190L ≈ 26 A p-p at 12 V); `POWER_INCR`; `TCSW_300K`/`TCSW_70K` sensor calibration; **EEPROM parameter map** `NVADDR_*` (0x0780-0x07AB); buffer sizes and revision history. |
| [C_REGS.H](C_REGS.H) | TMS320F243 peripheral register structs (SCI, SPI, ADC, digital I/O). |
| [KERNEL.H](KERNEL.H) / [KERNEL.C](KERNEL.C) | Cooperative task kernel. `TaskDispatcher()` busy-waits on `SpinVar` (8 timer ticks = one 60 Hz cycle). It then runs each task in `nTCB[]` whose delay has expired and whose pended events are posted. Task order: MeasMotorCurrent, MeasTemps, ADCMeas, **StateMachine**, SciInputReady, SciOutputReady, OperationMonitor, SysDataOut. |
| [TASKS.H](TASKS.H) | Task prototypes. |
| [TASKS.C](TASKS.C) | **All of the control logic** (2100 lines). It contains:<br>• `MeasMotorCurrent` (RMS = standard deviation of 8 samples, then `ImServo`)<br>• `MeasTemps` (Tcsw/Tcsn, alternating)<br>• `ADCMeas` (Trej, Tamb, Vlna, Ilna, Vin)<br>• `StateMachine`<br>• `SciInputReady`/`SciOutputReady` and the S/I command handlers `SetCommand`/`InquireCommand`<br>• `OperationMonitor` (LEDs, relays, run-time counter)<br>• `SysDataOut` (debug string)<br>• `MotorOn`, `CoolDownSp`, `PidSp`, `ImServo`, `iSqrt`, `LoadRtConstants` (EEPROM → limits), `MedianFilter` |
| [PARSER.C](PARSER.C) | `parse()`: splits a received command such as `S4=512` or `I7` into index, operator and argument. |
| [MISC.C](MISC.C) | `AsciiToLong`, `LongToAscii`, `clock()`. |
| [EEPROM.C](EEPROM.C) | SPI EEPROM driver (`SpiShift`, `EEPROM_Read`, `EEPROM_Write`). |
| [MAIN.C](MAIN.C) | `main()`, global initialisation, version and ACK/NAK strings, `SignOn`. |
| [NCP.CMD](NCP.CMD) | Linker command file: F243 memory map. |
| [NCP.MAP](NCP.MAP) | Linker map: every section and symbol address. |
| [NCP.MAK](NCP.MAK) / [MAKEFILE](MAKEFILE) | Code Composer project data and build rules. |

## Control structure, briefly

1. **Drive (FIG 5A).** GISR2 runs at 65.1 µs, which is 256 points per 60 Hz cycle. It outputs `sine × sGain` as PWM to
   the H-bridge. `MeasMotorCurrent` computes `ImOut` (RMS of 8 samples per cycle). `ImServo` closes the current
   loop `u[k] = 0.1988 e[k] − 0.007503 e[k−1] + u[k−1]` toward `ImSp` and writes `sGain`.
2. **Temperature (FIG 5B).** The current set point `ImSp` comes from the state machine. During cooldown it is the
   ramp / `CoolDownSp()` profile. In control it is `PidSp()`, a PID on `TcSp − Tcsn` with windup limit `TcLimI`,
   clamped to `[0, MAX_IMOT]`.
3. **Supervision.** `StateMachine` runs at 60 Hz; see [../../analysis/STATE_MACHINE.md](../../analysis/STATE_MACHINE.md).
   Drive limiting (this code's answer to overstroke) is covered in [../../analysis/OVERSTROKE.md](../../analysis/OVERSTROKE.md).
4. **Serial console.** Commands are `S0`-`S13` (set or inquire with `?`: gains, set point, modes, relays, EEPROM) and
   `I0`-`I10` (Trej, Tamb, Vlna, Ilna, ImOut, Tcsw, Tcsn, version, error flags, run time). `SetCommand` is at
   `TASKS.C:1418`; `InquireCommand` is at `TASKS.C:1641`.
