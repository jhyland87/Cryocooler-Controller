# Overstroke detection and drive back-off: everything the sources say

A linear Stirling cooler's allowed drive depends on cold-finger temperature. At room temperature only a small
drive is safe, and more becomes available as the finger cools. Driving too hard makes the piston/displacer
**overstroke**, meaning they hit their end stops. Every STI source handles this differently. This file collects all
of them, each statement with a citation.

Diagram: [diagrams/overstroke_signal_path.drawio](diagrams/overstroke_signal_path.drawio)

## 1. Why the limit is needed (shared by every source)

- "when initially cooling down from room temperature, the maximum power that can be delivered to the cooler will
  be a relatively low value, then gradually increase as the cold-finger temperature decreases. If one tries to
  drive the cooler at full power, the cooler will over-stroke." (SuperFilter guide, PDF p65)
- "when a Stirling cycle cryocooler initially is turned 'on' only a limited amount of power may be provided ...
  as the temperature of the cold finger ... begins to drop, additional power may be provided" (US6098409 col. 5)

## 2. Analog generation: US6098409 / US6256999 and the SuperFilter

### 2.1 Patent text (FIG 3)
- **Knock sensor 64 → knock processor 66 → limiter 68.** "The knock sensor 64 may comprise, for example, a PZT crystal
  based sensor (or microphone), a back EMF sensor circuit or current analyzer circuit that may be used to detect
  overstrokes of the cryocooler 40." The knock sensor, "when used in conjunction with the limiter circuit 68,
  functions to ensure that the cryocooler 40 is not overdriven, for example, at start-up." ('409 col. 5; the '999
  Certificate of Correction makes "sensor 66" read "sensor 64" here.)
- **Thermistor 60 → processor 62 → limiter 68** limits power "when, for example, the cryocooler 40 becomes too hot."
- **Signal chain.** The inner PD loop output 38 feeds limiter 68. Limiter output 72 drives multiplier 70, which
  "amplitude modulates a 60 Hz signal that is used to drive the cryocooler 40". So overstroke protection works by
  **clamping the amplitude of the 60 Hz drive**.
- '409 claim 3: "a limiter circuit which receives as inputs an output of a first loop controller, an output of a
  cryocooler knock sensor circuit and an output of a cryocooler thermistor sensor circuit, and which in response
  ... generates a signal that is provided to a multiplier circuit". '999 claims 6-8 claim the knock sensor and its
  three sensor types separately.

### 2.2 SuperFilter guide 830-0010A (the product built on this design)
- **Figure 3 (p16)** draws an **"Overstroke Detector"** as part of the Stirling cooler, with its own arrow into
  "Control Electronics and Processor". That input is separate from the "Driver Current (Voltage) Sensor" and from the
  "Multiplexed Sensor Signals". See [../manuals/diagrams/superfilter_fig3_functional_block.drawio](../manuals/diagrams/superfilter_fig3_functional_block.drawio).
- **LOOP console screen (p64-65).** "**Back-off Count**: ... an STI diagnostic which indicates the amount the maximum
  cooler drive is 'Backed off' due to the cooler over-stroke detector ... The controller monitors the cooler for
  potential over-stroke conditions and 'backs off' the drive. This value displayed is a relative amount the
  controller has 'backed off' the maximum cooler drive: A value of 0 indicates no back-off has occurred. Higher
  numbers indicate correspondingly less maximum drive is available to the cooler." Example value: `0`.
- "**DAC Back Off**: ... a factory set value." Example value: `300`. Its meaning is not explained anywhere.
- The CLS screen (p60) shows `User ID: STI TEST W/ILNA/PIEZO`. **[inference]** This suggests the test unit had a
  piezo (PZT) knock sensor, matching '409's first sensor option.
- The NSP screen (p66) sets the drive frequency through an "Osc. Divisor" of a 2 MHz clock (nominal 60 Hz).

### 2.3 Schematic: the back-off counter (US6098409 FIG 5C, 5E, 5G)
Source: FIG 5C-1/5C-2 (PDF p7-8), FIG 5E (p12), FIG 5G-3 (p17). See the KiCad pages `US6098409_fig5c`, `_fig5e` and
`_fig5g` in [../kicad/](../kicad/README.md). Part values and pins are as printed, and anomalies are in
[../kicad/TRANSCRIPTION_NOTES.md](../kicad/TRANSCRIPTION_NOTES.md). Numbers marked **[estimate]** are calculated from
printed values (74HC123 pulse width taken as 0.45·R·C) and are not stated anywhere.

None of the patent text describes this circuit. It is the only place where the sensor, threshold, step size and
decay that §5 asks about appear. All of it is in hardware: the microcontroller only reads the result.

1. **Sensor input and amplifier (5C-1).** `HOG_T` / `HOG_TR` come from off the board.
   - `HOG_T` → R285 2.21K → C150 .01uF → **U53A** (LT1124, inverting). Gain is set by R266, printed "221K(RM) / 49.0K"
     (RM/TM = rack/tower build, see the FIG 5A option table). C155 .01uF is in its feedback.
   - `HOG_TR` returns to ground via R286 2.21K. U53A + is biased through R267 221K.
   - U53A → C155 (AC coupling) → R232 20K → **U53B** (LT1124, non-inverting). Its feedback holds a **thermistor
     network** for the TM build (RT1 "Y4401", R281 3.08(TM), R282 12.4(TM), R283 unvalued, C167). R284 is "0(RM)", so
     the RM build is a unity follower. Output test point TPX1.
   - **[assumption]** `HOG_T` is the overstroke (knock) sensor channel, i.e. '409's knock sensor 64 / processor 66.
     The circuit is an AC-coupled, temperature-compensated amplifier, which fits a piezo or accelerometer. Nothing
     printed names it.
2. **Trip comparator (5C-1).** U53B → R253 10K → R254 10K → **U48 LT1011A** + input (pin 2, TP4, C141 to ground).
   - The − input (pin 3, TP5) is a threshold: R255 90.7K from +5VA against R256 2.09K, in parallel with the 10K pot
     R285 to ground. **[estimate]** That makes it adjustable from about 0 to 94 mV.
   - Output pin 7 is open collector, pulled up to +5VA by R233 1K.
   - **As drawn**, the U48 output also connects back to the R253/R254 junction, which is strong positive feedback.
     Taken literally, this makes U48 latch. It may be meant as hysteresis, or it may be a drafting error. It is
     transcribed as drawn.
3. **Count step: short one-shot (5C-2).** U48 output → the B input of **U28A** (HC123, pin 2), triggered on a rising
   edge.
   - Timing is R144 10K / C53 2.2uF, so **[estimate] ≈ 10 ms**. It is retriggerable.
   - While it runs, Q̄ (pin 4) turns **Q5** (INLD110) off. R167 64.8K from +5V then pushes current through the
     gate-channel junction of **Q4** (2N4220 JFET, drain and source tied, used as a low-leakage diode) into
     **C71 10uF**.
   - **[estimate]** About 0.4 µC per trip, i.e. a step of roughly 40 mV on C71 near 2 V. A burst of trips holds the
     one-shot on and charges C71 continuously.
4. **Hold and decay: long one-shot (5C-2).** The same trip also triggers **U28B** (pin 10).
   - Timing is R145 640K / C72 100uF, so **[estimate] ≈ 30 s**.
   - Each trip restarts it. While it runs, Q̄ (pin 12) holds **Q1** off.
   - After ~30 s with no trips, Q1 turns on and bleeds C71 through **R130 1M** (**[estimate] τ ≈ 10 s**). So the count
     holds while overstrokes keep occurring and decays once they stop.
5. **Reset (5C-2).** While `SHUTO_T` is low:
   - Both one-shots are cleared (CLR pins 3 and 11), so Q5 and Q1 are on.
   - **Q2** is off, so the R190 10K / R142 10K divider (2.5 V) feeds C71 through **Q3** (2N4220 used as a diode).
   - **[estimate]** C71 therefore settles near 1.9 V, the zero-count baseline.

   `SHUTO_T`'s source is not on the transcribed pages. 5B latches `RAW_SHUTO_T-` (U29 MC2001 output O3), and 5E ORs it
   with `SYS.RESET` into J8 pin 3.
6. **Output to the microcontroller (5C-2 → 5G-3).** C71 → R143 1K → **U27A** (LMC6-482 follower, +5VA/−5V) →
   **`BACK_OFF_COUNT`** → **U22 PE3/AN3, pin 39**, an ADC input of the microcontroller (68HC11K-family guess).
   - This is the voltage the SuperFilter LOOP screen shows as "Back-off Count" (§2.2). **[inference]** The displayed
     number is the ADC reading relative to its reset value.
   - "DAC Back Off" (300) is still unexplained. No DAC is drawn on this path.
7. **Back-off of the drive ceiling (5C-2).**
   - `BACK_OFF_COUNT` → R141 51.1K → **U27B** − input (pin 2), together with an offset from −10V through R165 50K + pot
     R197 200K. The + input goes to ground via R166 4.01K.
   - **No feedback part is drawn on U27B**, so as drawn it is an open-loop comparator. **[estimate]** It switches
     when `BACK_OFF_COUNT` passes about 2-10 V, set by R197. **[inference]** A missing feedback resistor, making it an
     inverting amplifier, would give a proportional back-off and fit the manual's "relative amount" wording better.
   - U27B output → **R163 (value printed "XXX")** → the **ceiling node** at U26 + input (pin 3). R140 200K from the
     `CMT_T` precision rectifier (U11 → U26A with CR10/CR11) also feeds that node.
   - **U26 (LT1124) with CR14 1N4149** from its − input to its output is an ideal-diode clamp. The set-point sum from
     **U34** (LT1012, via R139 10K) cannot rise above the ceiling node. So the drive command is
     `min(set-point sum, ceiling)`, and a higher back-off count lowers the ceiling.
8. **Drive command out (5C-2 → 5E → 5G).**
   - The clamped node → R162 10K → **U33** (LMC6-482, gain 1 + R185/R194 = 1.05) → **`NOT_TOTAL`** (TP1).
   - **[inference]** `NOT_TOTAL` is the net printed `HOT TOTAL` on 5E and `HOT-TOTAL` on 5G (joined in the KiCad
     project; see the transcription notes).
   - On 5E it feeds the reference (URF, pin 10) of the microcontroller-programmed serial pot UX1. UX1's line out
     → R136 → **U10** (LT1124, two stages) → R132 → an off-board line. **[inference]** This is the amplitude reference
     for the 60 Hz drive, i.e. multiplier 70's amplitude input in FIG 3.
   - On 5G it is also read by **U22 PE4/AN4, pin 38**.

Put together, this is FIG 3's knock sensor 64 → processor 66 → limiter 68 → multiplier 70, built in hardware:
- **Detection:** U53 + U48.
- **Integrating count with ~30 s hold and decay:** U28 + C71.
- **Limiter:** U27B + U26 clamp.
- **Amplitude scaling:** UX1 + U10.

The microcontroller sees the count (PE3) and the clamped drive (PE4), but the back-off itself does not depend on
firmware.

## 3. DSP generation: US6446444 and its published firmware

### 3.1 Patent text
- "the cryocooler 8 drive is preferably controlled for the purpose of producing maximum drive allowable without
  causing damage to the cryocooler 8 through overstroking, by using criteria either stored in a look-up table within
  DSP memory and/or by calculations made within the DSP." (col. 8)
- The cooldown profile may combine heat-exchanger temperature, ambient temperature, cryocooler temperature "and
  motor back-EMF from measured cryocooler drive voltage and drive current (or other parameter) to provide a fast
  cooldown without overdriving the cryocooler 8." (col. 6; claim 2)
- The H-bridge **overcurrent lock-out 136** is a "hardware failsafe that prevents shorted current conditions from
  harming the H-Bridge" and interrupts the DSP (col. 7). It protects against short circuits, not overstroke.

### 3.2 What the published code actually does (`../US6446444/code/`)
**The firmware contains no overstroke or knock detection.** No identifier or comment mentions stroke, knock, piezo
or back-off, and it never computes back-EMF. Instead it **schedules a ceiling on the drive current** from
temperatures and clamps everything to a hard maximum:

1. **Hard limits.** `MAX_IMOT 90L` "~12App (48V)" and `190L` "~26App (12V)", plus `MIN_IMOT 0L` (`GLOBALS.H:69-77`).
   Every current set point is clamped to `MAX_IMOT << 16`.
2. **Cooldown ceiling `CoolDownSp()`** (`TASKS.C:1749-1773`): `ImSp_max = m·Tcsw + b`. This is a straight line in the
   wide-range cold-stage sensor reading, from `ImLoLimit` at 300 K (`TCSW_300K = 230` counts) up to an
   ambient-dependent value at 70 K (`TCSW_70K = 965`; 965 − 230 = 735).
   - m and b are computed once on entering COOLDOWN (`TASKS.C:740-753`), "based on 90W max drive":
     `Im = 0.20979·Tamb − 52.86047`, `m = (Im − ImLoLimit)/735`, `b = ImLoLimit − m·230`.
   - A commented-out 75 W variant (`Im = 0.105·Tamb + 3.566`) and a 12 V variant (`Im = 0.307692·Tamb + 1.461539`,
     `m = (Im − 44)/735`) are kept as well.
   - **Motor-temperature derating:** if `Trej < TrejLoTemp` (motor hot; inverted sensor), the ceiling drops by
     `(TrejLoTemp − Trej)` (`TASKS.C:1755-1762`). This is the code counterpart of the '409 thermistor limiter.
   - The result is clamped to `[ImLoLimit, MAX_IMOT]`.
3. **Ramps, so the drive never steps.**
   - IDLE ramps to `ImLoLimit` (~40 W) by `POWER_INCR` once per second (`TASKS.C:670-681`).
   - COOLDOWN ramps by `0x456` per 60 Hz pass, "~3App/min", while below the ceiling (`TASKS.C:787-795`).
   - It then tracks the ceiling until the PID asks for less (`TASKS.C:798-807`).
   - POWERDOWN ramps down by `POWER_INCR` every 1/16 s (`TASKS.C:951-966`).
4. **PID output clamp.** `PidSp()` clamps `TcUk0` to `[0, MAX_IMOT << 16]` (`TASKS.C:1811-1816`).
5. **Inner current servo.** `ImServo()` drives the measured RMS current `ImOut` to `ImSp`; its output is the sine
   amplitude `sGain` (`TASKS.C:1830-1846`). Out-of-range outputs hold the previous value.
6. `ImHiLimit` ("upper drive limit in all states") is declared, but its EEPROM load is commented out
   (`TASKS.C:1969`). It is unused in this snapshot.

**[inference]** Read against the patent, the "look-up table / calculation" of col. 8 is this temperature-scheduled
ceiling: the cooldown profile *is* the overstroke protection. There is no feedback from an actual overstroke event
in this code.

### 3.3 SuperLink Rx manual 830-0013E (later DSP product)
- Figure 4 has **no overstroke block**, only "Motor current & voltage sensors" (p14).
- The System tab shows **"Power Drive Limit Foldback"**: "Power maximum drive level is folding back on a limit." /
  "Power maximum drive level is off the cooldown table." (p67). **[inference]** This is the DSP-era equivalent of
  "Back-off Count", with the ceiling coming from a cooldown *table*.
- Measured quantities that could detect overstroke: Cooler Power, Cooler Voltage/Current (real, RMS), **Cooler Current
  Phase** ("current phase referenced to voltage, in degrees"), **Cooler Impedance** (ohms), PWM drive %, PWM
  frequency (p68-69). The fault record **PM** covers "a power loop out of regulation fault or cooler motor impedance
  out of bounds fault" (p71). **[inference]** Impedance and phase move sharply when a linear motor's piston hits
  its stops, so these are the likely later overstroke indicators, but the manual does not say so.
- "Auto Frequency Adjust: SL Rx automatically adjusts the operating cooler drive frequency to minimize vibration." (p67)

## 4. Background (other coolers, not STI)
*Cryocoolers 13* mentions "stroke limitations" on a pulse-tube compressor (input power reduced so pistons don't hit;
PDF p183), "piston overstroke" as a sensor-based safety (p208), and an optical stroke-limit sensor that caused false
shut-offs (p211).

## 5. What is not documented anywhere
1. The SuperFilter overstroke detector's actual transducer and the units of "Back-off Count". The threshold, step
   size, hold and decay can only be estimated from the FIG 5C values (§2.3). R163 and R283 are unvalued, and the U48
   feedback and U27B stage look incomplete as drawn.
2. The meaning of "DAC Back Off" (300).
3. The algorithm behind SuperLink's "Power Drive Limit Foldback", and its impedance and phase limits.
4. Numeric values of `ImLoLimit`, `TrejLoTemp` and the other EEPROM parameters.
