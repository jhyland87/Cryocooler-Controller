# OEM controller state machine: consolidated

This is every documented description of the STI controller's system state machine, cross-mapped. Each
statement cites its source: file:line for the transcribed firmware (`../US6446444/code/`), and PDF page
for the patents and manuals. Anything not stated in a source is marked **[inference]**.

Diagrams:
- [diagrams/firmware_state_machine.drawio](diagrams/firmware_state_machine.drawio): the firmware (most detailed)
- [../manuals/diagrams/superlink_state_machine.drawio](../manuals/diagrams/superlink_state_machine.drawio): SuperLink Rx Table 7
- [../manuals/diagrams/superfilter_state_machine.drawio](../manuals/diagrams/superfilter_state_machine.drawio): SuperFilter Table 9
- [../US6446444/diagrams/fig5b_temperature_control_loop.drawio](../US6446444/diagrams/fig5b_temperature_control_loop.drawio): the patent's operating/cooldown decision

## 1. Sources and how they relate

| Source | Generation | State model |
|---|---|---|
| US6098409 / US6256999 (filed 1998) | Analog two-loop controller + microcontroller (FIG 3, schematics FIG 5-6) | No explicit states in the text. A µC monitors and sets references ('409 col. 4-5). |
| SuperFilter guide 830-0010A (9/2000) | Same family as '409 (console reports `Cooler Driver Type {PWM/CRD}`, p61) | 9 states: 0 Initialize … 7 Operating, 8 Fault (Table 9, p33) |
| US6446444 (filed 5/2001) + firmware appendix (linked 11 May 2001) | TMS320F243 DSP | Text: operating vs cooldown (FIG 5B). Code: 6 states INIT/IDLE/COOLDOWN/CONTROL/POWERDOWN/FINAL (`TASKS.C:172-177`) |
| SuperLink Rx manual 830-0013E (3/2004) | DSP generation | 6 states: 0 Initial … 4 Shutdown, 5 Forced Bypass (Table 7, p39) |

**[inference]** The firmware's state names do not match either manual table. Its 6-state structure is
closest to SuperLink Table 7, which suggests the published 2001 code is an early version of the DSP-generation
state machine. Later firmware added the "Bypass (Fault)", "Forced Bypass" and fault-log features the
SuperLink manual documents.

## 2. Firmware state machine (US6446444 appendix, `TASKS.C`)

**Scheduling.** `StateMachine()` (`TASKS.C:559`) is a kernel task with `delay = 0`, which means "run 60 times/sec"
(`TASKS.C:1062`). The kernel tick is 2.083 ms (`CLOCKS_PER_SEC 480`, `GLOBALS.H:21`). The state machine is nested:
each state has numbered phases, and the phase resets to 0 whenever the state changes (`TASKS.C:587-589`).
Outputs are not written directly. States set bits in `SmStatusBitFlag`, and `OperationMonitor()` copies them to
port A (LEDs) and port D (LNA, FAULT and BYPASS relays) every 500 ms (`TASKS.C:1228-1288`). LED toggling also
happens there, so LEDs blink at 1 Hz.

**Hardware bits** (`TASKS.C:45-56`): FAULT LED on PA3, READY LED on PA4, ALIVE LED on PA5, LNA_SD on PD5, FAULT relay
on PD6, BYPASS relay on PD7.

**Relay polarity.** `RELAY_ON(x)` *clears* the bit and `RELAY_OFF(x)` *sets* it. The opposite definitions are
commented out (`TASKS.C:128-131`). The physical sense therefore depends on the driver hardware (see the FIG 5G
relay driver in the KiCad transcription).

**Automatic and manual modes.** Every forward transition requires `!(SmStatusBitFlag & SMBF_MODE)`, i.e.
automatic mode. Serial command S6 selects the mode, S8 forces `SmCurrentState.Phase`, S7 sets the current
set point `ImSp`, and S9/S10/S11 set the LNA, FAULT and BYPASS bits (`SetCommand`, `TASKS.C:1418`).

### Checks made on every pass, before the switch (`TASKS.C:564-575`)
- `Trej < TrejHiTemp` → `SM_ERROR_TREJ_RANGE`, go to **SM_POWERDOWN**. The comment says the "inequality is reversed
  because thermocouple has neg tempco": the motor heat-reject sensor reads *lower* counts when hotter.
- `Vin < VinLoVolts || Vin > VinHiVolts` → `SM_ERROR_VIN_RANGE`, go to **SM_POWERDOWN**.

### States

| # | State | Outputs on entry (phase 0) | Behaviour | Exits |
|---|---|---|---|---|
| 0 | `SM_INIT` (`:599`) | FAULT LED on, READY LED on, FAULT relay ON, BYPASS relay ON, LNA off | Waits 15 s ("to facilitate stopping the state machine before it gets a chance to get started") | 15 s elapsed and automatic → IDLE |
| 1 | `SM_IDLE` (`:651`) | FAULT on, READY off, relays ON, LNA off. `ImSp = 0`, `MotorOn(TRUE)` | Every second, `ImSp += POWER_INCR` until `ImSp ≥ ImLoLimit` ("~40W") | `TcswHiTemp < Tcsw < TcswLoTemp` (wide-range sensor sane) and automatic → COOLDOWN, clearing the TCSW error. The header says a bad sensor leads to POWERDOWN, but the code only waits. |
| 2 | `SM_COOLDOWN` (`:714`) | FAULT and READY LEDs toggling, relays ON, LNA off. PID state reset | ph1: compute the cooldown line m, b from `Tamb` (`:740-753`). ph2: ramp `ImSp += 0x456` per pass ("~3App/min") while warmer than set point and `ImSp ≤ CoolDownSp()`. ph3: `ImSp = CoolDownSp()` while warmer than set point and `CoolDownSp < PidSp`. ph4: `ImSp = PidSp()` | ph4 and automatic → CONTROL. `Tcsw` out of range → `SM_ERROR_TCSW_RANGE`, IDLE (`:829-833`) |
| 3 | `SM_CONTROL` (`:842`) | FAULT off, READY on, FAULT relay OFF, BYPASS relay OFF, **LNA on**. `ImSp = PidSp()` | PID every pass. After 5 min, enable the Tcsn median filter (`SMBF_TCSN_FILTER`). ph3: if `|TcSp − Tcsn| > 200` counts → `SM_ERROR_TCSP_RANGE` and `RELAY_OFF(BYPASS)`, else clear it and `RELAY_ON(BYPASS)` (`:885-896`, see note 1) | `Tcsw` out of range → TCSW error, IDLE. `Ilna` outside `[IlnaLoCurrent, IlnaHiCurrent]` → set `SM_ERROR_ILNA_RANGE` only, no state change (`:916-923`) |
| 4 | `SM_POWERDOWN` (`:933`) | FAULT on, READY off, relays ON, LNA off | `ImSp -= POWER_INCR` every 1/16 s; at zero, `MotorOn(FALSE)` | → FINAL in any mode |
| 5 | `SM_FINAL` (`:993`) | FAULT on, READY off, relays ON, LNA off | "an off state, either by choice (i.e. entering manual mode) or because of a system error" | TREJ error and `Trej > TrejLoTemp` (cooled) → INIT. VIN error and `VinLo < Vin < VinHi` → INIT |
| — | `default` (`:1048`) | | "there is a problem so shut the whole system down" | → POWERDOWN |

**Error flags** (`SmErrorBitFlag`, `TASKS.C:156-162`). In the code comments, TREJ, VIN, TCSW and TCSN are "major" and
TAMB and ILNA are "minor". TCSP means "Tcsn no tracking TcSp". `SM_ERROR_TCSN_RANGE` is defined but never set, and the
Tamb check exists only in a commented-out template at the end of `TASKS.C` (`:2090-2100`). That template would have
made minor faults toggle the FAULT LED and major faults hold it on. `OperationMonitor` calls `logEvent()` when the
flags change, but `logEvent`'s published body is empty.

**Limits** come from EEPROM at reset (`LoadRtConstants`, `TASKS.C:1951-1969`; addresses `GLOBALS.H:91-110`): PID gains,
Tsp, and lo/hi limits for Trej, Tamb, Ilna, Vin, Tcsw, Tcsn and Im. The `ImHiLimit` load is commented out.
**No numeric limit values are published.**

**Sensor sense.** The cold-stage sensor counts *rise* as temperature falls (`TCSW_300K 230`, `TCSW_70K 965`,
`GLOBALS.H:80-81`). So `Tcsn < TcSp` means "still warmer than the set point", and the in-range test is written
`Tcsw > TcswHiTemp && Tcsw < TcswLoTemp`.

**Note 1, CONTROL-phase bypass relay [inference].** On CONTROL entry the code calls `RELAY_OFF(BYPASS)`, the
Normal/SuperLink position, because every bypass state calls `RELAY_ON(BYPASS)`. In phase 3, a *small* tracking error
calls `RELAY_ON(BYPASS)` and a *large* one calls `RELAY_OFF(BYPASS)`. Read literally, that is backwards: the unit
would sit in bypass while regulating well. Either the published snapshot has an inverted condition, or the phase 3
naming means something else. Check it against the relay driver hardware before copying the logic.

## 3. Manual state tables

Verbatim tables: [../manuals/superfilter_states.md](../manuals/superfilter_states.md) (SuperFilter Table 9) and
[../manuals/superlink_states.md](../manuals/superlink_states.md) (SuperLink Table 7).

## 4. Cross-map

| Firmware (2001) | SuperFilter Table 9 (2000) | SuperLink Table 7 (2004) | Bypass relay | Notes |
|---|---|---|---|---|
| 0 INIT (15 s) | 0 Initialize (both LEDs amber briefly) | 0 Initial | Bypass | SL: "powers up the cooler motor to minimum power setting". The firmware does that in IDLE. |
| 1 IDLE (ramp to ~40 W, check WR sensor) | 1 Idle ("Dewar is not cooling") | (part of 0 Initial) **[inference]** | Bypass | |
| 2 COOLDOWN (profile-limited max drive) | 2 Coarse Cool-down (>85 K), 3 Fine Cool-down (<85 K) | 1 Cooldown ("maximum motor drive power, based on the cooldown profile") | Bypass | SF splits at 85 K, where it switches from the WR to the NR sensor (p63). The firmware uses Tcsw for the profile and Tcsn for the end condition. |
| 2 COOLDOWN ph3-4 → 3 CONTROL first 5 min | 4 Over shoot (integrator settling), 5 Settle (relay → Normal) | 1 Cooldown dwell: NR in tolerance for 300 s, LNA on | SF: Bypass in 4, Normal in 5. SL: Bypass. FW: Normal on CONTROL entry | The firmware's 5-minute delay before enabling the Tcsn filter (`TASKS.C:858`) matches SL's 300 s dwell in length. In SL the LNA comes on in Cooldown; in FW it comes on at CONTROL entry. |
| 3 CONTROL | 6 Baseline, 7 Operating (baseline-deviation checks) | 2 Regulate (= SuperLink mode) | Normal | The firmware has no baseline concept. |
| (none) | (none) | 3 Bypass (Fault): input voltage out of bounds, keeps regulating | Bypass | The firmware treats a Vin fault as fatal (POWERDOWN). |
| 4 POWERDOWN → 5 FINAL | 8 Fault (alarm relay on) | 4 Shutdown (Fault): drive to zero; restart after warming and clearing | Bypass | SL restarts once NR has warmed out of range. FW restarts when Trej or Vin recover. |
| S6/S8 manual mode | `SET FORCED BYPASS ON/OFF` | 5 Forced Bypass (button or portal) | Bypass | FW S11 can set the BYPASS bit directly. |

## 5. Faults and their effects, by source

| Fault | Firmware | SuperFilter | SuperLink |
|---|---|---|---|
| Motor heat-reject over-temperature (Trej) | POWERDOWN → FINAL, auto-restart when cooled (`:565`, `:1018`) | (not listed separately) | fault record "Trej"; System tab "Cooler Rejection temperature out of bounds" (p67, p70) |
| Input voltage | POWERDOWN → FINAL, restart when back in range (`:571`, `:1027`) | → Bypass + alarm (p14-15) | → state 3 Bypass (Fault), keeps regulating (Table 7, p13) |
| Driver/motor current | (no check in this code) | → Bypass + alarm (p15) | → state 4 Shutdown + alarm (p13) |
| Wide-range cold sensor (Tcsw) out of range | → IDLE (`:829`, `:910`) | | fault record "Tcsw" |
| Cold stage not tracking set point | TCSP flag + bypass relay call (`:887`) | | |
| LNA current | flag only (`:916`) | ±20 % from initial → State 8, alarm, Bypass (p65) | → Bypass (p13), record "Ilna" |
| Overstroke | **no code**; drive ceiling only, see [OVERSTROKE.md](OVERSTROKE.md) | Overstroke Detector → drive back-off (p16, p65) | "Power Drive Limit Foldback" (p67) |

## 6. Timings

| Item | Value | Source |
|---|---|---|
| State machine rate | 60 passes/s | `TASKS.C:1062` |
| LED/relay update | every 500 ms; LED blink 1 Hz | `TASKS.C:1287` |
| INIT delay | 15 s | `TASKS.C:612` |
| Idle ramp | +`POWER_INCR` per second (`0x00008000` 48 V / `0x00010000` 12 V) | `TASKS.C:674-679`, `GLOBALS.H:74,77` |
| Cooldown ramp | +`0x456` per pass, "~3App/min" | `TASKS.C:792` |
| Tcsn filter enable / SL regulate dwell | 5 min / 300 s | `TASKS.C:858`; SL p39 |
| Power-down ramp | −`POWER_INCR` every 1/16 s | `TASKS.C:955-959` |
| SF LED flash | fast 2/s, slow 1/s | SF p33 |
| Cooldown duration | 3-5 h; call support if not regulating in 5 h | SF p32; SL p38 |
| Recool after power drop | ~3 h | SL p57 |

## 7. Open questions (not answered by any source)

1. What ends SuperFilter Settle → Baseline → Operating, and what counts as a "deviation from the baseline"? (SF p33)
2. How does the unit leave SuperFilter state 8: latched, or automatic?
3. What are the numeric limits (Vin, Trej, Tamb, Ilna, Tcsw, Tcsn, the tolerance for the 300 s dwell)? They are EEPROM-only (`GLOBALS.H:91-110`).
4. The CONTROL-phase bypass relay polarity (note 1).
5. What "Warmed sufficiently to be out of its valid range" means for SuperLink Shutdown → Initial. The SuperFilter NR valid range is 65-83 K (SF p64).
