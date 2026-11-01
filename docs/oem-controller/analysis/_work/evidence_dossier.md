# Evidence dossier: STI cryocooler controller, overstroke handling and system state machine

Scope: control logic, states, faults, thresholds, timings, LEDs, relays, and console/diagnostic fields only.
Physical layout, connectors, mounting, RF installation and cabling are left out.

## Source keys and citation format

| Key | Document | Notes |
|---|---|---|
| **SF** | SuperFilter Operation/Install Guide, STI 830-0010A (9/21/00), `docs/oem-controller/manuals/SuperFilter_Operation_Install_Guide.pdf` | Scanned. `p.N` is the PDF page; the printed page is about N-5 (N-6 from about p.60 on). Tables were transcribed from the page images. |
| **SL** | SuperLink Rx Operation & Installation Manual, STI 830-0013E (3/5/04), `docs/oem-controller/manuals/SuperLink_Rx_Operation_and_Installation_Manual.pdf` | `p.N` is the PDF page; printed page = N-5. |
| **SF-F** | SuperFilter Operation & Installation Manual, STI **830-0012F** (DSP generation), `~/Documents/chem/cryocooler/docs/SuperFilter - Operation and Installation Manual.pdf` | Not in the brief. Checked for corroboration only; its state table is identical to SL Table 7. |
| **SL1900** | SuperLink Rx 1900 Operation & Installation Manual, STI **830-0016C**, `~/Documents/chem/cryocooler/docs/SuperLink - Rx 1900 Operation and Installation Manual.pdf` | Not in the brief. Checked for corroboration and differences. |
| **'409** | US 6,098,409, PDF pages 27-31 (OCR text) | Cited as col./line. Line numbers are approximate, from the OCR margin markers. |
| **'999** | US 6,256,999 B1 (continuation of '409) | The description text is identical to '409. The claims and the Certificate of Correction differ (see A). |
| **'444** | US 6,446,444 B1, `docs/oem-controller/US6446444/US6446444.pdf` (105 pages) | Description on PDF pp.9-12 (cols 1-8). Claims on PDF p.105 (cols 193-194). |
| **'444-App** | The **source-code Appendix** of '444, PDF pp.13-104 (patent cols 9-192). STI DSP firmware "NCP.OUT", TMS320F243, (c) 2000. | **Not covered by the brief, and the most important new find.** PDF pp.20-104 have no text layer. I OCR'd them with tesseract (`scratchpad/p444/pg-NNN.txt`) and checked the key pages against the images. On a code page, the left column number = 2*PDFpage - 17. |
| **C13** | *Cryocoolers 13* (proceedings), `~/Documents/chem/cryocooler/docs/Cryocoolers - 13.pdf` | `p.N` is the PDF page; the printed page is given in brackets. |

---

## A. Overstroke detection and drive back-off

### A1. SuperFilter manual (830-0010A, analog/"CRD" generation)

- **The block diagram has a dedicated "Overstroke Detector".** Figure 3 draws an "Overstroke Detector" box under the Stirling Cycle Cryogenic Cooler, with its own arrow into "Control Electronics and Processor". This input is separate from "Driver Current (Voltage) Sensor" and from the "Multiplexed Sensor Signals" path through the Thermal Sensor Interface. The same figure shows the drive as "Cooling Motor Driver → 60 Hz, 66 VAC → Stirling Cycle Cryogenic Cooler" and the control as "Proportional Control Temperature/Cooler Driver". Figure labels: "Overstroke Detector"; "Driver Current (Voltage) Sensor"; "Proportional Control Temperature/Cooler Driver". **[SF p.16, Fig. 3]** (transcribed from the image)
- **The LOOP console field "Back-off Count" exposes overstroke back-off.** It is described as a relative amount by which the maximum drive is reduced because of the over-stroke detector: "'Back-off Count' is an STI diagnostic which indicates the amount the maximum cooler drive is 'Backed off' due to the cooler over-stroke detector." **[SF p.65]**
- **Why back-off is needed: the allowed drive grows as the cold finger cools.** "when initially cooling down from room temperature, the maximum power that can be delivered to the cooler will be a relatively low value, then gradually increase as the cold-finger temperature decreases. If one tries to drive the cooler at full power, the cooler will over-stroke." **[SF p.65]**
- **Control action: monitor for over-stroke, then back off the drive ceiling.** "The controller monitors the cooler for potential over-stroke conditions and 'backs off' the drive. This value displayed is a relative amount the controller has 'backed off' the maximum cooler drive: A value of 0 indicates no back-off has occurred. Higher numbers indicate correspondingly less maximum drive is available to the cooler." **[SF p.65]**
- **"DAC Back Off" is a separate factory constant.** "The line labeled 'DAC Back Off' is a factory set value." The example LOOP screen shows `Back Off Count: 0` and `DAC Back Off: 300`. **[SF p.65; screen on p.64]** What DAC Back Off means is not explained (see E).
- **The drive magnitude reported is RMS voltage or current, depending on the model.** "'Cooler V (RMS)' indicates the RMS value of the drive voltage to the cooler. On some SuperFilter systems this line is labeled 'Cooler I (RMS)' which indicates the RMS value of the drive current to the cooler." Example value: `Cooler V (RMS): 68V`. **[SF p.65, p.64]**
- **The drive-chain status line names two drive technologies.** "'Cooler Driver Type:' indicates which of the two types of technology are in use: pulse width modulation (PWM) or cost reduction (CRD) voltage control. Its valid states can be one of {PWM/CRD}." **[SF p.61]**
- **Indirect hint that a piezo sensor is fitted.** The CLS identification screen shows `User ID: STI TEST W/ILNA/PIEZO` (System S00665, Cooler HC00651). This suggests the test unit carried a piezo sensor, which matches the PZT "knock sensor" in '409. **[SF p.60]** This is an inference from a user-ID string, not a statement.
- **Drive-current anomaly leads to Bypass and alarm.** This is separate from back-off. "The Control Electronics and Processor senses variations in driver current. If the motor driver current levels move to an unacceptable level the Control Electronics and Processor will cause the SuperFilter to switch into the Bypass Mode and, at the same time, activate the Alarm Relay" **[SF p.15]**

### A2. SuperLink Rx manual (830-0013E, DSP generation)

- **There is no "Overstroke Detector" block in the DSP-generation diagram.** Figure 4 shows "Motor current & voltage sensors" from the Cooling Motor Driver into the DSP, with "Motor Drive 60 Hz, Variable Voltage" and "Proportional control drive". There is no overstroke or knock block. **[SL p.14, Fig. 4]** (checked against the image)
- **Cooldown runs at a maximum drive taken from a per-cooler profile.** Cooldown state: "runs the cooler motor at the maximum motor drive power, based on the cooldown profile of the cooler." **[SL p.39, Table 7, state 1]**
- **Status field "Power Drive Limit Foldback" (System tab).** Its two indications are "Power maximum drive level is folding back on a limit." and "Power maximum drive level is off the cooldown table." This is the DSP-era equivalent of a drive-ceiling back-off indicator. **[SL p.67]**
- **Status field "Power Duty Limit Exceeded".** Indications: "Power duty cycle has exceeded the maximum limit." / "...has not exceeded the maximum limit." **[SL p.67]** There is a matching fault record "Duty-Duty Cycle exceeds operating range fault?", with "This does not affect the active fault indication." **[SL p.71]**
- **"Power/Current Loop Regulating" and "Power Loop Active".** The drive has two inner loops: "Power loop is the active loop." / "Current loop is the active loop." Regulation status: "Power or current loop regulates within tolerance." **[SL p.66]**
- **Measured drive quantities that could be used to detect overstroke** (Measure tab): Cooler Power (W), Cooler Power Error (W), Cooler Voltage Real (VRMS), Cooler Current Real (ARMS), "Cooler Current Phase ... current phase referenced to voltage, in degrees", "Cooler Impedance ... measured in ohms", Cooler Current RMS, PWM Drive (%), PWM Feedforward (%), PWM Frequency (Hz). **[SL p.68-69]**
- **Fault record "PM" covers power-loop and motor-impedance faults.** "Two types of faults that trigger this record: a power loop out of regulation fault or cooler motor impedance out of bounds fault." **[SL p.71]** The "PM Last" tab is described the same way. **[SL p.73]**
- **Drive frequency is adjusted automatically to reduce vibration.** "Auto Frequency Adjust: SL Rx automatically adjusts the operating cooler drive frequency to minimize vibration." **[SL p.67]**
- **A driver-current anomaly leads to the Shutdown state.** In SuperFilter 830-0010A it led to Bypass. "If the motor driver current levels move to an unacceptable level the DSP will cause the SL Rx to switch into the Shutdown mode and, at the same time, activate the alarm relay" **[SL p.13]** SL1900 says "driver power" and "Shutdown (Bypass) mode" instead. **[SL1900 p.13]**

### A3. US 6,098,409 / US 6,256,999 (analog two-loop controller)

- **The knock sensor detects overstrokes and can be PZT, back-EMF or current-analyzer based.** "The knock sensor 64 may comprise, for example, a PZT crystal based sensor (or microphone), a back EMF sensor circuit or current analyzer circuit that may be used to detect overstrokes of the cryocooler 40." **['409 PDF p.29, col.5 ll.~19-23]**
- **Allowed drive rises as the cold finger cools.** "when a Stirling cycle cryocooler initially is turned 'on' only a limited amount of power may be provided to the cryocooler to drive the cryocooler. However, as the temperature of the cold finger ... begins to drop, additional power may be provided" **['409 p.29, col.5 ll.~24-32]**
- **Knock sensor plus limiter prevents overdrive at start-up.** "the knock sensor 66, when used in conjunction with the limiter circuit 68, functions to ensure that the cryocooler 40 is not overdriven, for example, at start-up." **['409 p.29, col.5 ll.~32-35]** The '999 Certificate of Correction changes "sensor 66" to "sensor 64" at col.5 ll.33 and 37. **['999 PDF p.31]**
- **A motor thermistor also limits drive when the cooler is hot.** "the thermistor sensor 60 is used to monitor the temperature of the cryocooler 40 and to limit the power that is provided to the cryocooler 40 when, for example, the cryocooler 40 becomes too hot." **['409 p.29, col.5 ll.~36-41]**
- **Signal chain: inner-loop PD output → limiter → multiplier → 60 Hz drive.** "The multiplier circuit 70 preferably is responsive to the output signal 72 of the limiter circuit 68 and amplitude modulates a 60 Hz signal that is used to drive the cryocooler 40." The inner loop consists of "a thermistor sensor 60 and related processor 62, a knock sensor 64 and related processor 66, a limiter circuit 68, and a multiplier circuit 70", and the inner-loop controller is preferably "a proportional and derivative (PD) controller." **['409 p.29, col.5 ll.~5-18, 41-45]**
- **Claimed limiter inputs.** "a limiter circuit which receives as inputs an output of a first loop controller, an output of a cryocooler knock sensor circuit and an output of a cryocooler thermistor sensor circuit, and which in response to said inputs generates a signal that is provided to a multiplier circuit for amplitude modulating a sinusoidal signal" **['409 p.31, col.7, claim 3]**
- **'999 claims the knock sensor separately (differs from '409).** Claim 6: "a second signal from a knock sensor used to detect overstrokes of the cryocooler." Claim 8: "the knock sensor is a sensor selected from the group consisting of a PZT crystal based sensor, back EMF sensor circuit, and current analyzer circuit." Claim 7: "the limiter circuit outputs a signal to a multiplier circuit used to drive the cryocooler." **['999 PDF p.30, col.8, claims 6-8]** The rest of the '999 description matches '409 word for word, apart from OCR/hyphenation noise and the added continuation line in col.1.

### A4. US 6,446,444 (DSP controller): description and claims

- **The cooldown profile is designed to avoid overdriving.** It may combine heat-exchanger temperature, ambient temperature, cryocooler temperature "and motor back-EMF from measured cryocooler drive voltage and drive current (or other parameter) to provide a fast cooldown without overdriving the cryocooler 8." **['444 PDF p.11, col.6 ll.~10-25]**
- **Maximum drive without overstroking comes from a look-up table and/or a calculation.** "the cryocooler 8 drive is preferably controlled for the purpose of producing maximum drive allowable without causing damage to the cryocooler 8 through overstroking, by using criteria either stored in a look-up table within DSP memory and/or by calculations made within the DSP." **['444 PDF p.12, col.8 ll.~20-26]**
- **A hardware overcurrent lock-out (not overstroke).** "The overcurrent lock-out 136 is a hardware failsafe that prevents shorted current conditions from harming the H-Bridge. It provides an interrupt to the DSP to examine the failure condition and reset operation, if necessary." **['444 PDF p.12, col.7 ll.~18-22]**
- **Drive chain (FIG. 5(a)).** Current sense transformer → buffer → anti-alias filter → ADC → RMS → "8:1 time decimation" → summed with "cryocooler driving current set point 46" → "proportional integral compensation 48" → "drive factor calculation 50" → multiplied with a "software-constructed sine wave via a look-up table 54" → PWM → H-bridge. **['444 PDF p.11, col.5 ll.~8-33]**
- **Claim 2: profile inputs include back-EMF.** "the cooldown profile is calculated based one or more of the following parameters, heat-exchange temperature, cold finger temperature, ambient temperature, and motor back-EMF." **['444 PDF p.105, col.193 ll.~18-22]**

### A5. US 6,446,444 firmware Appendix: how the published code actually limits drive

**Finding: the published firmware has no explicit overstroke or knock detection.** No identifier or comment contains "stroke", "knock", "piezo" or "back-off". OCR'd pages 13-104 were grepped. Drive is instead limited by a **temperature-scheduled current-setpoint ceiling** (the "cooldown profile"), with motor-temperature derating, a fixed absolute maximum, and slow ramps. The code is the "TOWER_MOUNT_CODE" (48 V cooler) build.

- **Absolute motor-current caps.** "`#define MIN_IMOT 0L // this number corresponds to 0App`". For non-tower (12 V) builds: "`#define MAX_IMOT 190L // this number corresponds to ~26App (12V)`" (220L/~30 App is commented out). For tower (48 V) builds: "`#define MAX_IMOT 90L // this number corresponds to ~12App (48v)  [corrected: dossier OCR said 390L; image shows 90L]`". **['444-App PDF p.37, cols.57-58 ll.~45-55]**
- **Ramp step sizes.** "`#define POWER_INCR 0x00010000L // defined for 12V coolers`" and "`#define POWER_INCR 0x00008000L // defined for 48V coolers`". **['444-App PDF p.37-38, cols.58-59]**
- **Calibration points for the wide-range cold sensor.** "`#define TCSW_300K 230 // Tcsw @ 300K, estimated from xfer func`" and "`#define TCSW_70K 965`". The difference, 735 counts, is the slope denominator below. **['444-App PDF p.38, col.59 ll.~3-8]**
- **The cooldown ceiling is a straight line from (300 K, ImLoLimit) to (70 K, Im).** Im depends on ambient temperature, sized for a 90 W maximum drive: "`// slope and intercept based on 90W max drive // 48V cooler: Im = 0.20979*Tamb - 52.86047`", then "`m = (Im-ImLoLimit)/735`" and "`b = ImLoLimit - m * 230 (230 = 300K)`". Commented-out alternatives: "75W max drive ... Im = 0.105*Tamb + 3.566", and a "12V cooler: Im = 0.307692 * Tamb + 1.461539" with "m = (Im-44)/735". **['444-App PDF p.77-78, cols.137-140]** (checked against the images)
- **CoolDownSp(): setpoint = m·Tcsw + b, derated for a hot motor, clamped to [ImLoLimit, MAX_IMOT].** "`long result = ImSpCoolDown_m * Tcsw + ImSpCoolDown_b;`" then "`// check to see what Trej is and compensate for it (rem Trej xfer is inv) if( Trej < TrejLoTemp ) { delta = TrejLoTemp - Trej; ... result -= delta;`" then "`if( result >= ImLoLimit && result <= t1 ) return result; else if( result > t1 ) return t1; else return ImLoLimit;`" (t1 = MAX_IMOT<<16). **['444-App PDF p.97, cols.177-178 ll.~15-45]** This is the code-level counterpart of the '409 thermistor limiter and of "Power maximum drive level is off the cooldown table".
- **Cooldown ramp rate ≈3 A/min.** "`case 2 : // --- approach the cooldown current ... if( (Tcsn < TcSp) && (ImSp <= lCdSp) ) ImSp += 0x00000456; // ~3App/min else SmCurrentPhase = 3;`" **['444-App PDF p.78, col.140 ll.~35-44]** (checked against the image)
- **The ceiling is tracked until the PID asks for less.** "`case 3 : // --- maintain cooldown drive until 78K ... if( (Tcsn < TcSp) && (lCdSp < lPidSp) ) ImSp = lCdSp; // keep tracking the cool down sp else ... SmCurrentPhase = 4; // so shift control to the PID code`" **['444-App PDF p.78-79, cols.140-141]**
- **The PID output is also capped at MAX_IMOT.** In PidSp(): "`if( TcUk0 < MIN_IMOT ) TcUk0 = 0; if( TcUk0 > t1 ) // ~30App current TcUk0 = t1;`" **['444-App PDF p.98, col.179 ll.~29-34]**
- **Inner current servo (PI-like) with output clamp.** Comment: "`u[k] = 0.1988*e[k] - 0.007503*e[k-1] + u[k-1]`". Code: "`ImEk0 = ImSp - ImOut; ImEk0 /= 256;`". If u<0 or u>0x7FFF, u holds its previous value. The output goes to sGain, the sine amplitude. **['444-App PDF p.98-99, cols.180-181]**
- **"RMS" current estimate.** MeasMotorCurrent averages 8 samples of ImotBuf and computes "the variance ... and the standard deviation `ImOut = iSqrt( gMotVar );`" every tick, then calls ImServo(). **['444-App PDF p.68-69, cols.120-121]**
- **Upper drive limit variable, apparently unused.** "`long ImLoLimit; // lower drive limit in the idle state`" / "`long ImHiLimit; // upper drive limit in all states`". The EEPROM load of ImHiLimit is commented out ("`//ImHiLimit = EEPROM_Read( NVADDR_IM_HI, 4 );`"). **['444-App PDF p.68 col.119 ll.15-16; p.101 col.185 l.~34]**
- **Power-down ramp.** "`SM_POWERDOWN (4) : At whatever drive level we're at, throttle down to zero`". It decrements ImSp by POWER_INCR every CLOCKS_PER_SEC>>4 (1/16 s), then "`MotorOn( FALSE )`". **['444-App PDF p.81-82, cols.145-148]**
- **Idle-power ramp at power-up.** "`case 1: // --- get to idle power ... every second until we reach the idle power ... if( ImSp < ImLoLimit ) ImSp += POWER_INCR;`" SM_IDLE throttles to "~40W". **['444-App PDF p.75-76, cols.133-136]** The emulator default is "`ImLoLimit = 1638400L; // 25.0`". **[p.74, col.131 l.~25]**

### A6. Background literature (not STI controller)

- C13: a pulse-tube pressure-wave generator "will experience stroke limitations and the input power must be reduced to prevent the pistons from hitting each other or the back housing" **[C13 p.183 (printed 178)]**
- C13: a linear-compressor test rig lists "piston overstroke" among its sensor-based safeties. **[C13 p.208 (printed 204)]**
- C13: an "optical stroke limit sensor lost sensitivity and became a source of random false shut-offs" at about 70 °C motor-cavity temperature. **[C13 p.211 (printed 207)]**
- C13: a space cryocooler electronics unit includes "a stroke limitation during operation". **[C13 p.131 (printed 122)]**
- The other patents in `~/Documents/chem/cryocooler/patents` (6141971, 6327862, 2004/0182077, 4602174, 5525845, 5818097, 6311498, 2008/0282707) mention stroke only as mechanical "mid-stroke" phasing. None of them describes stroke limiting or drive back-off. US 7,137,259 is mostly image-only (about 900 words over 27 pages) and was not OCR'd.

---

## B. State machine

### B1. SuperFilter (830-0010A)

**Table 9. Cool-Down State Table** **[SF p.33]**. Table 14 "System State Machine" **[SF p.62]** is identical, so it is not repeated. Transcribed from the images.

| State No. | State Name | Bypass Relay State | FAULT | READY | Description |
|---|---|---|---|---|---|
| 0 | Initialize | Bypass | On ** | Off ** | Initial Power Up State |
| 1 | Idle | Bypass | On RED | Off | Cold stage is warm, Dewar is not cooling |
| 2 | Coarse Cool-down | Bypass | Flash Fast * RED | Off | Cooling, cold stage is above 85 K |
| 3 | Fine Cool-down | Bypass | Flash Fast * RED | Flash Slow * GREEN | Cooling, cold stage is below 85 K |
| 4 | Over shoot | Bypass | Flash Fast * RED | Flash Fast * GREEN | Cold stage is cooler than set point (nominally 78 K) and the control algorithm integrator is settling |
| 5 | Settle | Normal | Flash Fast * RED | Flash Fast * GREEN | Cold stage temperature is settling, circuits are switched to Normal |
| 6 | Baseline | Normal | Off | On GREEN | Cold stage temperature has settled and baseline data is being collected |
| 7 | Operating | Normal | Off | On GREEN | System is operating normally and being checked for deviations from the baseline |
| 8 | Fault | Bypass | On RED | Off | Alarm relay is switched on |

Note: * = Fast Flash is twice per second, Slow Flash is once per second.
** = On power up, both FAULT and READY Indicators will momentarily illuminate AMBER during System State zero (0).

(In the original, State 8 is printed as a separate box below states 0-7.)

Other passages about states and transitions:

- **Power-up default is Bypass; Normal only once at temperature; automatic fallback.** "The SuperFilter is in Bypass Mode upon power up and only switches to Normal Mode when the filter circuits in the CoRE reach the operating temperature. If a problem develops during normal operation, such as the CoRE dropping out of the operating temperature, or, a loss of power, the system will automatically switch into Bypass Mode." **[SF p.14]**
- **Observed power-up LED sequence.** "Initially, both LED's on the front panel of the SuperFilter will flash amber. The READY LED will then go out. Then, the FAULT LED will illuminate red, which is normal. After a couple of minutes, the FAULT LED will begin to Fast Flash* red." Then: "As the cool down progresses, the READY LED will begin to Slow Flash* green." **[SF p.32]** The same text appears in Appendix C. **[SF p.71]**
- **Eight stages; the state machine owns both cooling and the bypass relay.** "The cool down sequence progresses through eight stages, which are indicated by different patterns of flashing red and green LED's. The system state machine controls the cooling for the superconductor circuits and the bypass relay switching." **[SF p.32]**
- **End condition and typical time.** "Initial cooling of the SuperFilter takes 3 to 5 hours. When the SuperFilter cryogenic chamber has reached operating temperature (~78 K), the READY LED will stay on green and the FAULT LED will stay off." **[SF p.32]**
- **Automatic switch to Normal, and a 5 h watchdog for the installer.** "The SuperFilter will automatically switch from Bypass Mode to Normal Mode when it has cooled. If the SuperFilter fails to go into Normal Mode within 5 hours ... call" **[SF p.32; also p.72]**
- **Expected steady state is 7.** "verify the SuperFilter is in System State Machine (SM) State: 7: Operating. This indicates the SuperFilter is operating normally." **[SF p.34; p.47; p.57]**
- **The STATE report shows the current and previous state.** "'System SM State:' indicates the current state of the system state machine; the previous state is indicated in parenthesis." Example: `7: Operating (6: Baseline)`. **[SF p.62; screens p.35, p.48, p.59, p.61]**
- **Forced Bypass is an overlay on any state.** "When the SuperFilter is placed in a Forced Bypass State the READY Indicator will Slow Flash AMBER in all states." **[SF p.62]** "SET FORCED BYPASS ON<Enter>. This places the SuperFilter in Bypass Mode indefinitely, until the command: SET FORCED BYPASS OFF<Enter> is entered" **[SF p.14]**
- **Forced Bypass also asserts the alarm relay.** After SET FORCED BYPASS ON: "The SuperFilter READY Indicator will Slow Flash amber; the Alarm Relay is now placed in an alarm condition." After OFF: "The SuperFilter READY indicator will be steady on green; the Alarm Relay is now placed in normal condition." **[SF p.36; p.49]**
- **The ±20 % external-LNA current fault forces State 8.** "If the current draw changes from the initial set value by ± 20%, then this circuit will declare a fault, switch to System State 8, set the alarm relay, and switch the system into Bypass Mode." **[SF p.65]**
- **The LNA is switched by the state machine.** "'Low Noise Amplifier:' indicates whether power is applied to the amplifier or not. Its valid state can be one of {On/Off} and is normally controlled by the system state machine." **[SF p.61]**
- **RF Bypass line values.** "{Normal/Bypass/Forced} and is normally controller by the system state machine." **[SF p.61]**
- **Cooldown is tracked by sensor range.** Use the WR sensor until about 85 K, then the NR sensors: "When the system temperature reads approximately 85K, as indicated by the WR Cold Finger sensor, then rely on the Cold Finger and Cold Stage sensors." **[SF p.63]** This matches the 85 K boundary between states 2 and 3.
- **Bypass vs Normal LED rule.** "When the SuperFilter is in the Normal Mode of operation, the READY LED should be lit (on, green) and the FAULT LED should be un-lit (off). When the SuperFilter is in the Bypass Mode of operation, the READY LED should be un-lit and the FAULT LED should be lit (red)." **[SF p.54]**
- **Front-panel definitions.** READY: "Illuminates green when the SuperFilter is in Normal Mode and ready for operation. Illuminates Slow Flash amber when the SuperFilter is placed into Forced Bypass Mode." FAULT: "Illuminates red when the SuperFilter is in Bypass Mode." **[SF p.17, Table 2]**

### B2. SuperLink Rx (830-0013E); identical in SF-F 830-0012F

**Table 7. SuperLink Rx Internal States and Status** **[SL p.39]**, checked against the page image.

| Mode | State Name | Bypass Relay State | BYPASS (RED) | STATUS (GREEN) | Description |
|---|---|---|---|---|---|
| Bypass | 0. Initial | Bypass | On | On | Initializes the system and powers up the cooler motor to minimum power setting. Transitions to the Cooldown state. |
| Bypass | 1. Cooldown | Bypass | On | On | Cools down the CoRE. The Cooldown state runs the cooler motor at the maximum motor drive power, based on the cooldown profile of the cooler. The LNAs turn on in the Cooldown state when the cold stage narrow range temperature is within operating bounds. Transitions to Regulate state when the narrow range temperature is within its operating tolerance for 300 seconds (LNA on). |
| SuperLink | 2. Regulate | Normal | Off | On | Regulates the cold stage temperature indefinitely. |
| Bypass | 3. Bypass (Fault) | Bypass | On | Off | Continues to regulate the cooler temperature. This Fault state occurs when the Input Voltage is out of bounds. When the Input Voltage fault has cleared, the system transitions back to the Regulate state (Automatic mode). |
| Bypass | 4. Shutdown (Fault) | Bypass | On | Off | The cooler motor drive reduces to zero and is turned off. Transitions back to Initial state in Automatic mode when cold stage narrow range temperature has warmed sufficiently to be out of its valid range and the faults are cleared. |
| Bypass | 5. Forced Bypass | Bypass | Flash if On | Flash if On | Forces the system into Bypass mode regardless of any other conditions. At least one LED should always flash on if in Forced Bypass mode. |

Footer: "Regulate state = SuperLink mode. In all other states, the SL Rx is in Bypass mode."

- **The SF-F 830-0012F Table 7 is word-for-word the same.** "SuperLink" is replaced by "SuperFilter". The Forced Bypass row is unnumbered and lacks the "At least one LED..." sentence. **[SF-F p.41]**
- **SL1900 Table 10 differences.** It has a single BYPASS (RED) column. State 1 transitions "to Normal (Regulate) state". State 5 reads: "You manually force the system into Bypass mode using the System Status Portal. The LED always flashes on in Forced Bypass mode." **[SL1900 p.39]**
- **Power-up and stripline bypass.** "The SL Rx is set to Bypass mode on power up. In Bypass mode, both Bypass Relays switch together and connect the input to the output through a stripline circuit that bypasses the filter and LNA. The SL Rx system will automatically switch to SuperLink mode (Regulate state) when the CoRE has reached operating temperature." **[SL p.12]**
- **Cooldown LEDs and the end condition.** "Initially, both LEDs on the front panel of the SL Rx remain on and steady during cooldown. When the SL Rx cryogenic chamber has reached operating temperature (~78 K), the STATUS LED will be steady GREEN and the BYPASS LED will be off." **[SL p.38]**
- **5 h limit.** "If the system fails to go into SuperLink mode (Regulate state) within 5 hours, call the CS-Hotline." **[SL p.38; also p.40, p.42, p.54]**
- **Automatic vs Manual mode.** "In Automatic mode, the system will automatically sequence through the states. In Manual mode, the operator manually changes states by selecting the state." **[SL p.69, State tab]**
- **Forced Bypass is a front-panel toggle that also asserts the alarm.** "Push the FORCED BYPASS button ... The STATUS LED will slow flash GREEN. The alarm relay is now placed in an alarm condition." Push it again and "The system will return to SuperLink mode (Regulate state), indicated by a steady GREEN STATUS LED." **[SL p.42]** Forced-bypass LED behaviour: "the LEDs flash GREEN or RED based on the state of the system." **[SL p.58]**
- **The bypass routes can differ by fault type.** Input-voltage fault → "Fault Bypass mode" (state 3). Driver-current fault → "Shutdown mode" (state 4). Out-of-range temperature or LNA current → "Bypass mode". "Each time the SL Rx is switched to Bypass mode, the alarm relay is activated." **[SL p.13]** SL1900 sends temperature and LNA faults to "Fault Bypass mode". **[SL1900 p.13]**
- **Recovery time after a power drop.** "If the LEDs display RED and GREEN, the system may be recovering from power drop out. Wait three hours to allow it to recool." **[SL p.57]**

### B3. Patent-described states

- **'444 FIG. 5(b): operating vs cooldown state decision.** "The temperature control loop ... then determines the state 72 of the cryocooler 8, i.e., whether the cryocooler is in the standard operation mode 74, or alternatively, in the cooldown mode 76." In cooldown, "a cooldown profile 78 is calculated". In the operating state, the error against "temperature set point 88" goes through "proportional integral derivative (PID) compensation 92". **['444 PDF p.11, col.6 ll.~4-12, 27-49]**
- **'444 set point vs ambient temperature.** The set point "can be obtained through a look-up table and/or linear interpolation ... generally is a function of ambient temperature 90 and determined offline by observation of the filter center-frequency vs. ambient temperature 90." **['444 PDF p.11, col.6 ll.~30-38]**
- **'444 claim 11.** "determining whether the signal corresponding to the measured temperature of the at least one temperature sensor indicates an operating state or a cooldown state." **['444 PDF p.105, col.194 ll.30-34]**
- **'444 kernel order.** "...drive loop error calculation, PI compensation, drive factor calculation, the temperature loop filtering, error calculation, PID compensation, and drive level set. Finally, RS-232 communications ... and state machine functions are dispatched before returning to the spin mode." **['444 PDF p.12, cols.7-8]** Timing: 20 MHz/1302 → "65.1 microseconds" PWM/sine interrupt, ÷32 → "2.08 millisecond" current-sampling interrupt with the watchdog. **['444 PDF p.12, col.8]**
- **'409 two-loop structure (no explicit states).** The outer PID on the cold-stage sensor sets the reference for the inner PD on the cold-finger sensor; "a portion of the reference signal 74 is provided as an input to the inner loop controller 32". **['409 PDF p.29-30, cols.5-6]**

**'444 firmware state machine (Appendix, TASKS.C `StateMachine`)**, checked against the images:

States: "`#define SM_INIT 0 ... SM_IDLE 1 ... SM_COOLDOWN 2 ... SM_CONTROL 3 // SM temp control state ... SM_POWERDOWN 4 ... SM_FINAL 5 // SM final (error) state`" **['444-App PDF p.66, col.115 ll.~35-42]**. It is a nested state.phase machine: "`if( SmCurrentState != SmLastState ) SmCurrentPhase = 0;`" **[p.74, col.131]**

| State | Phase actions and exit conditions (paraphrased; key code quoted) | Outputs set on entry | Cite |
|---|---|---|---|
| 0 SM_INIT | "No error checking here, just a 15s delay". Phase 2: "transition to SM_IDLE in automatic mode". | FAULT LED on, READY LED on, FAULT relay ON, BYPASS relay ON, LNA off | p.74-75, cols.131-134 |
| 1 SM_IDLE | "Throttle power to ~40W ... used to check for bad temp sensors and will transition to SM_POWERDOWN if 70K < Tcsw > 300K." MotorOn. Ramp ImSp += POWER_INCR once per second up to ImLoLimit. Then wait until Tcsw is within limits; in auto mode go to SM_COOLDOWN. | FAULT LED on, READY off, FAULT relay ON, BYPASS ON, LNA off | p.75-76, cols.134-136 |
| 2 SM_COOLDOWN | "Calculates the target cooldown setpoint end temperature based on Tamb and Tcsw ... Once Tcsn > TcSp control is passed to the PID". Phases: init PID → compute m,b → ramp ~3 A/min up to CoolDownSp → "maintain cooldown drive until 78K" → hand to PID ("`ImSp = lPidSp`") and go to SM_CONTROL in auto mode. Error check: if Tcsw is out of range, set TCSW error and return to SM_IDLE. | FAULT LED toggle, READY LED toggle, FAULT relay ON, BYPASS ON, LNA off | p.76-79, cols.136-142 |
| 3 SM_CONTROL | "closed-loop PID control". Phase 0: start "`t3 *= 300L; // 5 min delay`". Phase 1: "wait to turn on the Tscn filter". Phase 2: "engage the Tscn filter and run forever". Phase 3: "loop here forever" with "`error checking for ABS(TcSp-Tcsn) > someLimit ... if( tmp > 200 )`" → set SM_ERROR_TCSP_RANGE (and toggle the bypass relay; see E). Error checks: Tcsw out of range → SM_IDLE; Ilna out of [IlnaLoCurrent, IlnaHiCurrent] → set ILNA error flag only (no state change). | FAULT LED off, READY on, FAULT relay OFF, BYPASS OFF, **LNA on** | p.79-81, cols.141-146 |
| 4 SM_POWERDOWN | Ramp ImSp to 0 by POWER_INCR every 1/16 s, MotorOn(FALSE), then go to SM_FINAL "in any mode". | FAULT LED on, READY off, FAULT relay ON, BYPASS ON, LNA off | p.81-82, cols.145-148 |
| 5 SM_FINAL | "an off state, either by choice (i.e. entering manual mode) or because of a system error. System errors are checked here and if they (Trej, Vin) resolve themselves the system starts over." Trej recovered (`Trej > TrejLoTemp`) or Vin back inside (Lo,Hi) → clear the flag and go to SM_INIT. | FAULT LED on, READY off, FAULT relay ON, BYPASS ON, LNA off | p.82-83, cols.147-150 |
| default | "If we get to the default state there is a problem so shut the whole system down" → SM_POWERDOWN. | | p.83, col.149 |

- **Fatal checks on every pass, in any state.** "`if( Trej < TrejHiTemp ) // check the motor temp // inequality is reversed because thermocouple has neg tempco { SmErrorBitFlag |= SM_ERROR_TREJ_RANGE; SmCurrentState = SM_POWERDOWN; }`" and "`if( Vin < VinLoVolts || Vin > VinHiVolts ) ... SmCurrentState = SM_POWERDOWN;`" **['444-App PDF p.74, col.131 ll.~9-22]** In this code, input-voltage faults shut the motor down (→ FINAL → INIT). That differs from SL Table 7, where an input-voltage fault goes to state 3 and keeps regulating.
- **Task rates.** StateMachine runs "60 times/sec" ("`tcb->delay = 0; // no delay, run 60 times/sec`"). OperationMonitor (LEDs/relays) runs every 500 ms. `CLOCKS_PER_SEC 480 // based on a 2.083mS tick`. **['444-App PDF p.83 col.149; p.64 col.111; p.36]**
- **Manual mode.** The state machine only advances when `!(SmStatusBitFlag & SMBF_MODE)`, i.e. automatic. In manual mode, S8 sets the state 0-5 directly and S7 sets ImSp. **['444-App PDF p.92, col.165-166]**
- **Relationship to the manual state tables (inference, not stated in any source).** Firmware INIT/IDLE/COOLDOWN/CONTROL/POWERDOWN/FINAL lines up roughly with SL Initial/Cooldown/Regulate/Shutdown. The firmware has no "Bypass (Fault, keep regulating)" or "Forced Bypass" state, so this 2000 code predates SL Table 7. The SuperFilter 0-8 table (Coarse/Fine/Overshoot/Settle/Baseline) does not match this code.

---

## C. Faults, alarms, thresholds and timings

| Item | Behaviour / value | Cite |
|---|---|---|
| Input power out of range (SF) | "If input power drops or rises to an unacceptable level ... switch into the Bypass Mode and, at the same time, activate the Alarm Relay." FAULT LED red. | SF p.14-15 |
| Input voltage out of bounds (SL) | → "Fault Bypass mode", alarm relay on. State 3 keeps regulating and returns to Regulate when cleared (Automatic). | SL p.13, p.39 |
| Input voltage spec | SF: "+25 to +30 VDC" (27 V nominal); install check "27 ±2 VDC". SL: "22.5 to 30 VDC"; troubleshooting: "should be between 25 to 30 VDC". SL1900: 27 V "27+3 VDC", -48 V "-48+4 VDC". | SF p.10, p.32; SL p.74, p.38, p.56; SL1900 p.39 |
| Driver current anomaly | SF: → Bypass + Alarm. SL: → **Shutdown** + alarm. SL1900: "driver power" → "Shutdown (Bypass)". | SF p.15; SL p.13; SL1900 p.13 |
| CoRE temperature unacceptable | SF: → Bypass. SL: → Bypass. SL1900: → Fault Bypass. "Each time ... switched into the Bypass Mode the Alarm Relay is activated." | SF p.15; SL p.13; SL1900 p.13 |
| LNA voltage/current | SF: "Unacceptable levels of LNA voltage are sensed via the Power Supply and will cause ... Bypass Mode." SL: LNA current → Bypass. | SF p.15; SL p.13 |
| (Int)LNA current ±20 % | "If the current draw changes from the initial set value by ± 20%, then this circuit will declare a fault, set the alarm relay, and switch the system into Bypass Mode." Example 101 mA. | SF p.65, p.64 |
| (Ext)LNA current ±20 % | Same rule, and it explicitly goes to "System State 8". Applies to the Replacement/Extra Gain options with warm LNAs. Example 0 mA. | SF p.65 |
| Firmware fault classes | `SM_ERROR_TREJ_RANGE 0x0001 // major`, `TAMB 0x0002 // minor`, `ILNA 0x0004 // minor`, `VIN 0x0008 // major`, `TCSW 0x0010 // major`, `TCSN 0x0020 // major`, `TCSP 0x0040` ("Tcsn no tracking TcSp"). The commented-out code would toggle the FAULT LED for minor faults and set it steady for major ones. | '444-App p.66 col.115-116; p.104 col.191-192 |
| Firmware limits (NV/EEPROM) | TrejLo/Hi, TambLo/Hi, IlnaLo/Hi, VinLo/Hi, TcswLo/Hi, TcsnLo/Hi, ImLo/Hi, Kp/Ki/Kd/KiLimit, Tsp at EEPROM 0x0780-0x07AB. Values are not published. | '444-App p.38 col.59-60; p.101 |
| Tcsw sanity window | IDLE "will transition to SM_POWERDOWN if 70K < Tcsw > 300K" (comment). The code returns to IDLE from COOLDOWN/CONTROL on a Tcsw range error. | '444-App p.75 col.133-134; p.79, p.81 |
| Temperature tracking error | In CONTROL, \|TcSp−Tcsn\| > 200 counts sets TCSP error and switches the bypass relay. | '444-App p.80 col.143-144 |
| Motor (heat-reject) over-temperature | Code: Trej beyond TrejHiTemp → POWERDOWN → FINAL; restart once `Trej > TrejLoTemp`. SL: fault record "Trej-Cooler Rejection temperature exceeds operating range fault?" and System-tab "Cooler Rejection temperature out of bounds". | '444-App p.74, p.83; SL p.70, p.67 |
| Temperatures | Operating ~78 K (SF/SL); ~79 K (SL1900). 85 K boundary between Coarse and Fine cooldown (SF). Set point "nominally 78 K" (SF state 4). Install check WR Cold Finger "79±4 K" (SL; SL1900 adds "check if the system has been on more than two hours"). NR Cold Finger valid "65k-83k"; above 83 K it "simply indicate[s] 87k". Motor temp normally 5-15 °C above ambient; controller-board ambient about 5 °C above outside. | SF p.15, p.33, p.64; SL p.13, p.42, p.54; SL1900 p.16, p.42 |
| Cooldown times | SF: "3 to 5 hours"; fail if not Normal "within 5 hours". SL: 5 h limit; "Wait three hours to allow it to recool" after a power drop. | SF p.32; SL p.38, p.57 |
| Regulate entry dwell | NR temperature "within its operating tolerance for 300 seconds (LNA on)" → Regulate. Firmware CONTROL also has a "5 min delay" before enabling the Tcsn median filter. | SL p.39; '444-App p.80 |
| Firmware timings | 15 s INIT delay; idle ramp one POWER_INCR per second; cooldown ramp ~3 A/min; powerdown ramp one step per 1/16 s; OperationMonitor every 500 ms; StateMachine 60 Hz. | '444-App p.75-82, p.64 |
| Drive limits | Firmware MAX_IMOT ~12 A (48 V tower) / ~26 A (12 V); cooldown profile sized for "90W max drive". SF/SL max input power "195 Watts Maximum" (SL: "at cooldown only"); steady state 150 W typical (SF), 70/80 W (SL 2-/6-Pak). | '444-App p.37, p.77; SF p.10; SL p.74 |
| LED flash rates | "Fast Flash is twice per second, Slow Flash is once per second." Forced Bypass: SF READY "Slow Flash AMBER in all states"; SL STATUS "slow flash GREEN". | SF p.32-33, p.52, p.62; SL p.42 |
| Power-up LED pattern | SF: both amber (state 0) → READY off, FAULT red → after "a couple of minutes" FAULT fast-flash red → READY slow-flash green. SL: both LEDs steady on during cooldown. SL1900: FAULT red until ~79 K. | SF p.32-33; SL p.38; SL1900 p.16 |
| Alarm relay states | "NO = Open in normal operation ... NC = Closed in normal operation"; fault: "NO = Closed during fault condition ... NC = Open during fault condition". "dry contacts, rated at 2 amps". Test: in alarm, C-NO < 10 Ω and C-NC > 10 kΩ; in normal, the reverse. SL1900 label: "Alarm Relay Fault Condition (Failure or Cooldown)". | SF p.50, p.36; SL p.37, p.43; SL1900 p.38 |
| Alarm relay vs bypass relay coupling | SF rear panel: MAJOR relay "Activation of the Alarm Relay triggers the RF Bypass Relay." MINOR: "Reserved for future expansion" / "not functional". | SF p.20, p.36, p.50 |
| Alarm while unpowered | Table 11: "Alarm condition should be on with power failed." | SF p.52 |
| Firmware relay polarity | `RELAY_ON(x)` *clears* the status bit and `RELAY_OFF(x)` *sets* it. The opposite definitions are commented out. FAULT and BYPASS relays are both "ON" in every non-CONTROL state. | '444-App p.65 col.113-114 |
| Hardware overcurrent | H-bridge "overcurrent lock-out 136 is a hardware failsafe ... provides an interrupt to the DSP". | '444 p.12 col.7 |
| Troubleshooting map (SF Table 11) | Indicators off → input power drop-out, or indicators failed (check STATE = 7). Alarm on + READY off + FAULT steady red → "Low Input Power condition" / "Cooling system fault" / "LNA power fault". READY slow-flash amber → "Forced Bypass On". FAULT fast-flash red → "cooling down normally after power up", wait up to 5 h. One channel dead, no alarm → force bypass to isolate. | SF p.52 |
| Fault log (SL) | Fault Records: PM, Tcsw, Trej, Tcsn, Ilna, Vin, Duty, each with First/Last. Each record stores Operating State, Fault Count, Run Time, System Accumulated Time, Tamb, Trej, Tcsw, Tcsn, Vin, cooler V/I, LNA I. "Only STI can clear the faults". | SL p.63, p.70-73 |

---

## D. Serial console and diagnostic fields/commands

### D1. SuperFilter console (RS-232 DCE, 19,200 8-N-1; prompt `D:HH:MM:SS>` = uptime) [SF p.34, p.57]

| Command | Meaning | Cite |
|---|---|---|
| `CLS` / (CL)S | Clear screen. It also prints identification: "Superfilter - 6000", S/W Version 1.0.6.0-B 07/05/00, User ID, System, Cooler, Dewar, Bypass serials. | SF p.35, p.60 |
| `LOOP` / (L)oop | "Display the temperature loop control parameters" (cooler subsystem state). | SF p.35, p.64 |
| `NSP` / (N)sp | "Dump Non-volatile set point parameters". | SF p.35, p.66 |
| `STATE` / (ST)ate | "Dump filter subsystem state data". | SF p.35, p.61 |
| `TEMP` / (T)emperature | Temperatures (K for cryogenic, °C for motor and ambient). | SF p.35, p.63 |
| `SET FORCED BYPASS ON` / `OFF` | Enter or leave Forced Bypass; asserts or releases the alarm. | SF p.35, p.14, p.36 |
| Syntax | "Signed values, e.g. +3 or -5 denote CHANGES from the current value. Unsigned values ... are treated as ABSOLUTE"; [] optional; {} choice. Commands can be abbreviated. | SF p.60, p.35 |

| Field (screen) | Meaning / values | Cite |
|---|---|---|
| Cooler Controller/Driver (STATE) | "state of the controller & cooler driver chain ... {Normal/Off/Reset}" | SF p.61 |
| Cooler Driver Status (STATE) | "{Normal/Fault}" | SF p.61 |
| Cooler Driver Type (STATE) | "{PWM/CRD}" (pulse width modulation / cost reduction voltage control) | SF p.61 |
| Low-Noise Amplifier (STATE) | "{On/Off} and is normally controlled by the system state machine" | SF p.61 |
| RF Bypass (Relay) (STATE) | "{Normal/Bypass/Forced}"; reads Bypass "if the SuperFilter is either not cooled down sufficiently or has detected an anomaly" | SF p.61, p.35 |
| System Summary Alarm (STATE) | "{Normal/Fault}" | SF p.61 |
| System SM State (STATE) | current state (previous state), states 0-8 | SF p.62 |
| System Error (LOOP) | PID output, −5.1 V to +5.1 V; +ve = "get warmer", −ve = "get colder"; "During cool-down, this voltage will be at the negative rail (around -5V)"; about 0 V at temperature | SF p.65 |
| Cooler V (RMS) / Cooler I (RMS) (LOOP) | RMS drive voltage (or current on some units) | SF p.65 |
| Supply Voltage (LOOP) | input line voltage | SF p.65 |
| **Back-off Count (LOOP)** | relative overstroke back-off of the maximum drive; 0 = none | SF p.65 |
| **DAC Back Off (LOOP)** | "factory set value" (example 300) | SF p.65 |
| (Int)LNA I(mA), (Ext)LNA I(mA) (LOOP) | LNA current monitors; ±20 % from initial → fault | SF p.65 |
| Cold Stage / NR Cold Finger / WR Cold Finger / Motor Temp / Ambient Temp (TEMP) | see C; columns #1-#6 per channel | SF p.63-64 |
| NSP Cold Stage | relative cold-stage set-point, 0-255; "A larger number indicates a warmer temperature" (example 158) | SF p.66 |
| NSP Cooler Offset | "relative amount of nominal temperature difference between the cold stage and the cold finger" (example 165) | SF p.66 |
| NSP Osc. Divisor | divides "an internal 2MHz clock signal down to the cooler operating frequency, nominally 60Hz", 0-4095 (example 0520) | SF p.66 |
| NSP Switch | "state of some internal digital nodes", STI-only (example 08) | SF p.66 |

### D2. SuperLink System Status Portal (Java GUI over RS-232) [SL p.61-73]

- **Status View tabs.** Time (Runtime since Powerup, System Accumulated, Cooler Accumulated). LED (Status LED, Bypass LED). Relay (Bypass Relay, Forced Bypass, LNA Power). System (LNA Power On, Power/Current Loop Regulating, Power Loop Active, Power Duty Limit Exceeded, **Power Drive Limit Foldback**, Auto Frequency Adjust, Temperature Loop Regulating, and out-of-bounds flags for Cold Stage NR, Cold Stage WR, Cooler Rejection and Ambient). Measure (see A2). State (State Machine Mode: Automatic/Manual; State Machine State). **[SL p.64-69]**
- **Set Points view.** "Displays the values that configure the operation of the SL Rx and debugging information. Changing values in this view is for STI Customer Service use only." Password protected. **[SL p.63]** SL1900 sets Forced Bypass via "View > Set Points ... Relay tab. Check the Forced Bypass box." **[SL1900 p.16]**
- **Fault Records view.** See C. **[SL p.70-73]**

### D3. '444 firmware command set (Appendix PARSER/TASKS.C)

- **Set/inquire commands `S0`-`S13`.** S0 Kp; S1 Ki; S2 "integrator saturation limit"; S3 Kd; S4 "temperature setpoint"; S5 "enable|disable sending debug string"; **S6 "enable|disable state transition mode"** (0 = automatic, otherwise manual); **S7 "set|inquire ImSp"** (manual only); **S8 "set|inquire SmCurrentState.SmCurrentPhase"** (manual only, 0-5); S9 "LNA shut down bit"; S10 "FAULT relay setting"; S11 "BYPASS relay setting"; S12 NvAddress; S13 EEPROM word. **['444-App PDF p.90-94, cols.163-172]**
- **Inquire commands `I0`-`I10`.** I0 Trej "motor heat reject temperature"; I1 Tamb; I2 Vina "LNA power supply voltage"; I3 Ilna; **I4 "ImOut, RMS motor current estimate"**; I6 Tcsw; I7 Tcsn; I8 software version; **I9 "error querry"** (returns SmErrorBitFlag); I10 run-time accumulator. **['444-App PDF p.95-96, cols.173-176]**
- **Debug string (1 Hz when enabled).** "Outputs the debug info string: state.phase,Tcsw,Tcsn, ImSp, ImOut". **['444-App PDF p.100, col.183]**
- **Event log is a stub.** `logEvent` is "written to the EEPROM for later interrogation", but the published function body is empty. **['444-App PDF p.103, col.189]**

---

## E. Gaps: referenced but not explained

1. **How the overstroke detector senses overstroke (SuperFilter).** Fig. 3 shows an "Overstroke Detector" block, and LOOP reports "Back-off Count". No source gives the transducer type, signal, threshold, back-off step, decay or recovery rate, or the units of "Back-off Count". '409 lists candidate sensors (PZT/microphone, back-EMF, current analyzer) but not which one STI fitted. The "STI TEST W/ILNA/PIEZO" user ID is the only hint of a piezo sensor. [SF p.16, p.65, p.60; '409 col.5]
2. **"DAC Back Off".** Only "a factory set value" (example 300). Its relationship to Back-off Count (likely the DAC full-scale or ceiling offset) is not stated. [SF p.65]
3. **Knock sensor processor 66 and limiter 68 internals.** '409 refers to schematic FIGS. 5(A)-(H)/6(A)-(C) (`docs/oem-controller/US6098409/source-pages/p-03..p-26.png`). Tesseract cannot read their labels, so they were **not transcribed here**. The overstroke circuit may be drawn there and should be inspected by eye. ['409 col.5 ll.1-4]
4. **The '444 firmware has no overstroke code.** The patent text claims overstroke protection via "look-up table ... and/or by calculations", but the published Appendix only does temperature-scheduled current limiting (CoolDownSp), motor-temperature derating and MAX_IMOT. Back-EMF is never computed. The DSP-generation "Power Drive Limit Foldback" and "Cooler Impedance/Current Phase" fields in SL suggest later firmware added an impedance/phase or power-based foldback, but no source documents the algorithm. ['444 col.8; '444-App p.97; SL p.67-69]
5. **What sends SF states 4→5→6→7, and the "deviations from the baseline" checks.** No settle criterion, baseline duration or deviation threshold is given. [SF p.33]
6. **Exit conditions out of SF state 8 (Fault).** Not stated (auto-recover vs latch, and whether a power cycle is required).
7. **SL "Shutdown" exit.** "Warmed sufficiently to be out of its valid range" is not quantified, and the NR valid range is not given for SL. SF gives NR 65-83 K. [SL p.39; SF p.64]
8. **Numeric bounds for input voltage, Trej, Tamb, LNA current (SL), and the operating tolerance used for the 300 s dwell.** These are only "out of bounds"; the firmware keeps them in EEPROM (0x0780-0x07AB), and no values are published. Defaults visible in code: emulator `Trej = 200; // 64C`, `Tamb = 614; // 300K`, `TcSp = 512`, `ImLoLimit = 1638400L // 25.0`. ['444-App p.74]
9. **Firmware bypass-relay logic in SM_CONTROL phase 3 looks inverted.** On \|error\| > 200 it calls `RELAY_OFF(BYPASS)` (the same call that selects Normal on CONTROL entry). Otherwise it calls `RELAY_ON(BYPASS)` (the same call used in every Bypass state). Read literally, a large tracking error keeps or forces Normal and a small error forces Bypass. Either it is a bug in the published snapshot or the macro naming is confusing; confirm against hardware. ['444-App p.80 ll.30-45; p.65 ll.45-48]
10. **Firmware vs manual on input-voltage faults.** The code sends any Vin fault to POWERDOWN → FINAL (motor off). SL Table 7 says a Vin fault keeps regulating in state 3. Behaviour differs between firmware generations.
11. **Firmware Tcsn range and Tamb faults are defined but not raised.** `SM_ERROR_TCSN_RANGE` is never set; the Tamb check is commented out. The ILNA fault only sets a flag and does not bypass in this code, unlike the manuals (±20 % → Bypass/State 8).
12. **"Power Duty Limit" value, "Duty" fault limit, cooler impedance bounds, and the PM fault criteria.** Not quantified. [SL p.67, p.71]
13. **Auto Frequency Adjust algorithm** ("to minimize vibration"). Not described. [SL p.67]
14. **The MINOR alarm** is reserved and non-functional, with no defined meaning. [SF p.20, p.50]
15. **Not fully reviewed.** SF-F (830-0012F) and SL1900 (830-0016C) were only checked for differences in states, LEDs, faults and portal fields, and none beyond those noted were found. US 7,137,259 (scanned) was not OCR'd.
