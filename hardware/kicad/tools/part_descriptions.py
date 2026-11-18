"""What each schematic part does in this circuit (by final reference) and what
each labelled net carries (by label name).

gen_schematic.py writes these into the hidden Description field of every
symbol and label, and fails if one has no entry or an entry names something
that is gone. Units of one multi-unit part share a description.
"""

DESCRIPTIONS = {
    # ── root: MCU, USB, chip-select decoder ──────────────────────────────
    'U1': 'ESP32-S3 module (32 MB flash, 16 MB PSRAM): runs the cooldown state '
          'machine, WiFi dashboard and every peripheral on this board',
    'U2': 'USB ESD clamp on D+, D- and VBUS at the USB-C connector J1',
    'U32': '4-to-16 decoder: makes the SPI chip selects, the ACS37800 included (one low at a '
           'time) from four ESP32 address lines and an enable',
    'U51': '1.8 V to 3.3 V buffer: lifts GPIO47 to the decoder U32 address bit D',
    'J1': 'USB-C receptacle: native USB console and firmware upload, and 5 V for '
          'the logic when 12 V is absent',
    'SW1': 'RESET button: pulls ESP32 EN low',
    'SW2': 'BOOT button: pulls GPIO0 low to enter the USB download mode',
    'R1': 'Pull-up resistor for ESP32 EN; with C42 it forms the power-on reset delay',
    'R2': 'Pull-up resistor for ESP32 GPIO0 (BOOT strap: normal boot)',
    'R17': 'Pull-up resistor for CS_ADDR_A (GPIO3 strap: keeps the default USB-JTAG)',
    'R18': 'Pull-up resistor for CS_EN_N: keeps decoder U32 disabled, so every chip '
           'select is high, until firmware runs',
    'R19': 'Pull-down resistor for CS_ADDR_C (GPIO45 strap: holds its default low level)',
    'R23': 'USB-C CC1 pull-down (Rd, 5.1 k): tells the host this is a device',
    'R24': 'USB-C CC2 pull-down (Rd, 5.1 k): tells the host this is a device',
    'R514': 'Pull-down resistor for the U51 buffer input: address bit D reads 0 '
            'while GPIO47 floats at boot',
    'C1': 'Bulk decoupling capacitor for the ESP32 module U1 (+3V3)',
    'C13': 'Decoupling capacitor for the ESP32 module U1 (+3V3)',
    'C14': 'Debounce capacitor on the BOOT button line (GPIO0)',
    'C39': 'Decoupling capacitor for the chip-select decoder U32 (+3V3)',
    'C42': 'Reset delay capacitor on ESP32 EN (RC with R1)',
    'C63': 'USB VBUS filter capacitor at connector J1',
    'C306': 'Decoupling capacitor for the address bit D buffer U51 (+3V3)',
    # ── ambient temperature ──────────────────────────────────────────────
    'U50': 'Ambient temperature sensor (16-bit, SPI mode 3) on the shared bus',
    'R511': 'Pull-up resistor for the ADT7320 INT output (open drain) to expander GP2',
    'R512': 'Pull-up resistor for the ADT7320 CT output (open drain) to expander GP3',
    'C305': 'Decoupling capacitor for the ambient temperature sensor U50 (+3V3)',
    # ── amplifier remote control ─────────────────────────────────────────
    'J8': 'Amplifier remote (REM) output: 12 V turns the audio amplifier on',
    'J9': '3.5 mm jack: sine drive signal out to the amplifier input',
    'Q5': 'Level shifter for the amplifier REM switch: GPIO6 high pulls the Q6 gate low',
    'Q6': 'High-side P-FET: switches +12 V onto the amplifier REM line',
    'Q21': 'Power-good interlock: in series with Q5, so REM can only turn on while '
           'both +-15 V rails are good (PG_15V)',
    'D2': 'Amplifier REM state LED: green = on, red = off',
    'R28': 'Pull-down resistor for the Q5 gate: REM off while GPIO6 floats',
    'R29': 'Pull-up resistor for the Q6 gate: holds the REM switch off',
    'R44': 'Pull-down resistor for the AMP_REM line: defined low when off, and the '
           'return path for the red LED',
    'R48': 'Series gate resistor from GPIO6 (AMP_REM_EN) to Q5',
    'R60': 'Current-limit resistor for the amplifier REM LED D2',
    # ── amplifier current (isolated) ─────────────────────────────────────
    'U17': 'Digital isolator with integrated isolated DC-DC: carries SPI to the '
           'ACS37800 and makes its isolated 5 V supply',
    'U18': 'Isolated-side power monitor: measures the cryocooler drive current '
           '(+-15 A Hall) and voltage, read over SPI',
    'U41': 'Tri-state gate: passes SPI_SCK to the isolator only while ACS_CS is low',
    'U42': 'Tri-state gate: puts the ACS37800 MISO on the shared bus only while '
           'ACS_CS is low (the ACS37800 never releases MISO)',
    'J11': 'Amplifier output in (+ / -): the cryocooler drive from the audio amplifier',
    'J12': 'Cryocooler drive out (+ / - / GND), after the ACS37800 current path',
    'R63': 'Lower resistor of the ACS37800 voltage sense divider (4 x 1 M over 4.02 k)',
    'R64': 'Voltage sense divider, upper string 1 of 4 (drive voltage to ACS37800 VINP)',
    'R65': 'Voltage sense divider, upper string 2 of 4 (drive voltage to ACS37800 VINP)',
    'R66': 'Voltage sense divider, upper string 3 of 4 (drive voltage to ACS37800 VINP)',
    'R67': 'Voltage sense divider, upper string 4 of 4 (drive voltage to ACS37800 VINP)',
    'R501': 'Pull-up resistor for the gated ACS_SCK line: idles high (SPI mode 3) '
            'while gate U41 is off',
    'C6': 'Bulk input capacitor for the ISOW7841 supply pin VCC (+3V3_ISO)',
    'C7': 'Output capacitor on the ISOW7841 isolated 5 V output VISO',
    'C31': 'Decoupling capacitor for the ACS37800 U18 (isolated 5 V)',
    'C45': 'Decoupling capacitor for the ACS37800 U18 (isolated 5 V)',
    'C52': 'Decoupling capacitor for the ISOW7841 supply pin VCC (+3V3_ISO)',
    'C53': 'Decoupling capacitor on the ISOW7841 isolated 5 V output VISO',
    'C301': 'Decoupling capacitor for the ACS bus gates U41 / U42 (+3V3)',
    'C302': 'Decoupling capacitor for the ACS bus gates U41 / U42 (+3V3)',
    # ── cold head temperature ────────────────────────────────────────────
    'U14': '24-bit ADC: ratiometric 4-wire PT1000 measurement of the cold head '
           'temperature, on the shared SPI bus',
    'U35': 'ESD clamp array on the four PT1000 cable lines at J10',
    'J10': 'Cold head PT1000 sensor, 4-wire',
    'R49': 'Series resistor for ADS1220 AIN1 (RTD sense): input filter and protection',
    'R50': 'Series resistor for ADS1220 AIN0 (RTD sense): input filter and protection',
    'R55': 'Series resistor for the ADS1220 excitation current output (AIN3) to the '
           'RTD: limits the voltage if the cable shorts',
    'R62': 'Reference resistor Rref (3.9 k): the RTD current returns through it and '
           'its voltage is the ADC reference',
    'C25': 'Decoupling capacitor for the ADS1220 U14 (+3V3_CH)',
    'C26': 'Differential filter capacitor across the ADS1220 RTD sense inputs',
    'C27': 'Filter capacitor across the reference resistor R62',
    'C44': 'Decoupling capacitor for the ADS1220 U14 (+3V3_CH)',
    'C70': 'Common-mode filter capacitor on ADS1220 AIN1',
    'C71': 'Common-mode filter capacitor on ADS1220 AIN0',
    # ── compressor relay ─────────────────────────────────────────────────
    'J13': 'Compressor relay coil output: switched +12 V and GND',
    'Q7': 'Level shifter for the compressor relay switch: GPIO16 high pulls the Q8 '
          'gate low',
    'Q8': 'High-side P-FET: switches +12 V onto the compressor relay coil',
    'D3': 'Compressor relay state LED: green = on, red = off',
    'D14': 'Flyback diode across the compressor relay coil',
    'R30': 'Pull-down resistor for the Q7 gate: relay off while GPIO16 floats',
    'R31': 'Pull-up resistor for the Q8 gate: holds the relay switch off',
    'R45': 'Pull-down resistor for the COMP_RELAY line: defined low when off, and '
           'the return path for the red LED',
    'R51': 'Series gate resistor from GPIO16 (COMP_RELAY_EN) to Q7',
    'R61': 'Current-limit resistor for the compressor relay LED D3',
    # ── debug ────────────────────────────────────────────────────────────
    'D10': 'Isolated 5 V rail indicator LED (green)',
    'R38': 'Current-limit resistor for the isolated 5 V LED D10',
    'TP9': 'Test point: +15 V rail',
    'TP10': 'Test point: -15 V rail',
    'TP11': 'Test point: +16.5 V pre-regulated rail',
    'TP12': 'Test point: -16.5 V pre-regulated rail',
    'TP14': 'Ground loop for the scope ground clip',
    'TP37': 'Test point: DDS output sine (AD9837 VOUT)',
    'TP38': 'Test point: sine drive signal at the amplifier output jack',
    # ── display link (CAN) ──────────────────────────────────────────────────────────
    'DS1': 'Off-board: the 16-way screw terminal strip on the back of the Waveshare '
           'touch display, drawn to show where the J15 cable lands; not a '
           'part of this board',
    'J15': 'Display header (JST PH, top entry): 1 GND, 2 fused unswitched 12 V, 3 CAN_H, '
           '4 CAN_L, 5 power button, 6 reset, to the Waveshare touch display',
    'U52': 'CAN transceiver: carries telemetry to, and commands from, the Waveshare '
           'touch display',
    'U53': 'ESD clamp on the power button line from the display header J15',
    'U54': 'ESD clamp on the reset line from the display header J15',
    'R515': 'Pull-up resistor for CAN_TX: bus stays recessive while GPIO17 floats '
            'at reset',
    'R516': 'CAN bus termination resistor (120 R) at this end of the cable',
    'R517': 'Series resistor on the reset line from the display (to ESP32 EN)',
    'R518': 'Series resistor on the power button line from the display (to the '
            'LTC2954 PB pin)',
    'C307': 'Decoupling capacitor for the CAN transceiver U52 (+3V3)',
    # ── GPIO expander ────────────────────────────────────────────────────
    'U25': 'SPI GPIO expander: reads the +-15 V power-good flags, the INA239 alert '
           'and the ambient sensor interrupts',
    'C35': 'Decoupling capacitor for the GPIO expander U25 (+3V3)',
    # ── IMU ──────────────────────────────────────────────────────────────
    'J14': 'IMU cable header: SPI, chip select, two interrupts and 3.3 V to the '
           'LSM6DSOX on the cryocooler',
    'U36': 'Six-channel EMI filter and ESD clamp (100 R series, 17 pF) on the IMU '
           'cable signals',
    # ── indicators ───────────────────────────────────────────────────────
    'U24': '3.3 V to 5 V level shifter for the status LED data line',
    'D13': 'Addressable RGB status LED (fault / ready indication)',
    'R10': 'Pull-down resistor for STATUS_RGB: buffer input defined while GPIO38 '
           'floats',
    'R85': 'Series resistor on the WS2812B data line: damps ringing',
    'C33': 'Decoupling capacitor for the level shifter U24 (+5V)',
    'C34': 'Decoupling capacitor for the status LED D13 (+5V)',
    # ── power button ─────────────────────────────────────────────────────
    'U11': 'Push-button on/off controller: drives the power switch Q1, asks the '
           'ESP32 to shut down (INT#) and cuts power on KILL# or a long press',
    'U12': '5 V shunt reference: clamps the KILL# bias taken from VIN',
    'U34': 'ESD clamp on the power button line',
    'SW3': 'Power button: tap for on, hold for off',
    'Q1': 'High-side P-FET power switch: connects the 12 V input (VIN) to the '
          'switched rail (VSW)',
    'Q41': 'Shorts the red standby LED once +3V3 is up',
    'D7': 'Status LED: red = standby (12 V present, off), green = on',
    'D17': 'Zener clamp: limits the Q1 gate-source voltage to 15 V',
    'R7': 'Series resistor from GPIO10 (PWR_KILL) to the LTC2954 KILL# pin',
    'R8': 'Pull-up resistor for the LTC2954 INT# output to GPIO1',
    'R20': 'Series gate resistor from LTC2954 EN# to Q1: with C80 it sets the '
           'turn-on ramp',
    'R27': 'Pull-up resistor for the Q1 gate: holds the power switch off',
    'R56': 'Bias resistor holding KILL# high from the 5 V reference until the '
           'ESP32 takes over',
    'R59': 'Feed resistor from VIN to the 5 V shunt reference U12',
    'R93': 'Current-limit resistor for the red standby die of D7 (from VIN)',
    'R401': 'Current-limit resistor for the green die of D7 (from +5V)',
    'C24': 'Decoupling capacitor for the LTC2954 U11 (VIN)',
    'C41': 'Timing capacitor on LTC2954 PDT: sets the long-press power-down delay',
    'C80': 'Gate-drain capacitor on Q1: slows the turn-on ramp to limit inrush',
    'C84': 'Gate-source capacitor on Q1: keeps it off during a hot plug',
    # ── power good ───────────────────────────────────────────────────────
    'D11': '+15 V power-good LED: green = good, red = bad',
    'D12': '-15 V power-good LED: green = good, red = bad',
    'D15': 'Dual Schottky (common anode): ANDs the two power-good nodes into PG_15V',
    'Q22': 'Inverter: makes the active-low PG_15V_N flag for GPIO43',
    'Q23': 'Drives the green die of D11 while the +15 V node is good',
    'Q24': 'Drives the green die of D12 while the -15 V node is good',
    'Q42': '-15 V guard: pulls PGN_15V low when the -15 V rail is missing',
    'Q51': 'Drives the red die of D11 while the +15 V node is bad',
    'Q52': 'Drives the red die of D12 while the -15 V node is bad',
    'R13': 'Pull-up resistor for the PG_15V_N flag',
    'R52': 'Series resistor from the PG_15V_N flag to GPIO43 (TXD0 drives during boot)',
    'R57': 'Upper resistor of the PGP_15V node divider (+15 V to about 3.2 V)',
    'R58': 'Upper resistor of the PGN_15V node divider (+15 V to about 3.2 V)',
    'R83': 'Current-limit resistor for the green die of D11',
    'R84': 'Current-limit resistor for the green die of D12',
    'R86': 'Lower resistor of the PGP_15V node divider',
    'R87': 'Lower resistor of the PGN_15V node divider',
    'R88': 'Pull-up resistor for PG_15V (the AND of both power-good nodes)',
    'R89': 'Upper resistor of the -15 V guard divider (+15 V to the Q42 gate)',
    'R90': 'Lower resistor of the -15 V guard divider (Q42 gate to -15 V)',
    'R402': 'Pull-up resistor for the Q51 gate: red die on when Q23 is off',
    'R403': 'Current-limit resistor for the red die of D11',
    'R404': 'Pull-up resistor for the Q52 gate: red die on when Q24 is off',
    'R405': 'Current-limit resistor for the red die of D12',
    # ── power input ──────────────────────────────────────────────────────
    'J2': '12 V input, Mini-Fit Jr 2 x 2 pinned as the ATX 12 V (CPU) connector: 1 and 2 '
          'ground, 3 and 4 +12 V',
    'F1': 'Backup input fuse (10 A) on the 12 V input',
    'D1': 'TVS diode on the 12 V input: clamps surges, and blows the fuse on '
          'reverse polarity',
    'C65': 'Bulk capacitor on the 12 V input rail (VIN)',
    'C67': 'High-frequency bypass capacitor on the 12 V input rail (VIN)',
    # ── +-15 V rails ─────────────────────────────────────────────────────
    'U20': 'Dual switching converter: boosts 5 V to +16.5 V and inverts it to '
           '-16.5 V ahead of the linear regulator',
    'U21': '+15 V linear regulator: post-regulates +16V5 to a quiet +14.7 V, with '
           'a power-good output',
    'U22': '-15 V linear regulator: post-regulates -16V5 to a quiet -14.7 V, with '
           'a power-good output',
    'L2': 'Boost inductor of the ADP5071 positive converter (+16.5 V)',
    'L3': 'Inductor of the ADP5071 inverting converter (-16.5 V)',
    'D4': 'Rectifier diode of the ADP5071 boost converter (+16.5 V)',
    'D5': 'Rectifier diode of the ADP5071 inverting converter (-16.5 V)',
    'R11': 'Lower resistor of the LT3045 +15 V power-good threshold divider (PGFB)',
    'R12': 'Lower resistor of the LT3094 -15 V power-good threshold divider (PGFB)',
    'R68': 'Compensation resistor on ADP5071 COMP1 (boost loop), in series with C79',
    'R69': 'Compensation resistor on ADP5071 COMP2 (inverting loop), in series with C55',
    'R70': 'Upper feedback resistor setting the +16.5 V rail (ADP5071 FB1)',
    'R71': 'Lower feedback resistor setting the +16.5 V rail (ADP5071 FB1)',
    'R72': 'Feedback resistor from the -16.5 V rail to ADP5071 FB2',
    'R73': 'Feedback resistor from ADP5071 FB2 to VREF: with R72 it sets -16.5 V',
    'R74': 'Upper resistor of the LT3045 +15 V power-good threshold divider (PGFB)',
    'R75': 'Upper resistor of the LT3094 -15 V power-good threshold divider (PGFB)',
    'R76': 'LT3045 SET resistor: sets the positive output (100 uA x 147 k = 14.7 V)',
    'R77': 'LT3094 SET resistor: sets the negative output (100 uA x 147 k = -14.7 V)',
    'C11': 'Input capacitor for the ADP5071 U20 (+5V_PS15)',
    'C12': 'Input capacitor for the ADP5071 U20 (+5V_PS15)',
    'C40': 'High-frequency input bypass capacitor for the ADP5071 U20',
    'C49': 'Bypass capacitor on the ADP5071 internal regulator (VREG)',
    'C50': 'Bypass capacitor on the ADP5071 reference (VREF)',
    'C55': 'Compensation capacitor on ADP5071 COMP2, in series with R69',
    'C56': 'Output capacitor of the +16.5 V converter and input capacitor of the '
           'LT3045 (+15 V regulator)',
    'C57': 'Output capacitor on the +15 V rail (LT3045)',
    'C58': 'Output capacitor on the -15 V rail (LT3094)',
    'C59': 'Output capacitor on the +15 V rail (LT3045)',
    'C60': 'Output capacitor on the -15 V rail (LT3094)',
    'C61': 'Output capacitor of the -16.5 V converter and input capacitor of the '
           'LT3094 (-15 V regulator)',
    'C62': 'Output capacitor of the -16.5 V converter and input capacitor of the '
           'LT3094 (-15 V regulator)',
    'C79': 'Compensation capacitor on ADP5071 COMP1, in series with R68',
    'C81': 'Capacitor across the LT3045 SET resistor: filters reference noise and '
           'sets the soft start',
    'C82': 'Capacitor across the LT3094 SET resistor: filters reference noise and '
           'sets the soft start',
    # ── 5 V and 3.3 V rails ──────────────────────────────────────────────
    'U15': 'Buck regulator: 12 V to the +5V rail',
    'U16': 'Buck regulator: +5V_OR to the +3V3 logic rail',
    'U28': 'Power mux: feeds +5V_OR from the +5V rail, or from USB VBUS when 12 V '
           'is absent',
    'L1': 'Output inductor of the 5 V buck regulator U15 (LC filter with C2 / C4)',
    'L4': 'Output inductor of the 3.3 V buck regulator U16 (LC filter with C5)',
    'R21': 'Lower resistor of the TPS2116 PR1 divider: sets the +5V to USB '
           'changeover threshold',
    'R34': 'Lower feedback resistor setting +3V3 (TPS62822 FB)',
    'R94': 'Upper feedback resistor setting +3V3 (TPS62822 FB)',
    'R95': 'Upper resistor of the TPS2116 PR1 divider: sets the +5V to USB '
           'changeover threshold',
    'C2': 'Output capacitor of the 5 V buck regulator U15 (LC filter with L1)',
    'C3': 'Output capacitor of the power mux U28 and input capacitor of the 3.3 V '
          'buck U16 (+5V_OR)',
    'C4': 'Output capacitor of the 5 V buck regulator U15 (LC filter with L1)',
    'C5': 'Output capacitor of the 3.3 V buck regulator U16 (LC filter with L4)',
    'C28': 'High-frequency input bypass capacitor for the 5 V buck U15 (+12V)',
    'C29': 'Bootstrap capacitor for the 5 V buck U15 high-side driver (SW to BST)',
    'C30': 'High-frequency bypass capacitor on the +3V3 rail at the buck output',
    'C48': 'Input capacitor on the USB VBUS side of the power mux U28',
    'C78': 'Input capacitor for the 5 V buck U15 (+12V)',
    'C87': 'Feed-forward capacitor across the upper +3V3 feedback resistor R94',
    # ── signal generator ─────────────────────────────────────────────────
    'U3': '16 MHz oscillator: master clock for the AD9837 DDS',
    'U4': 'DDS waveform generator: makes the sine that drives the cryocooler, '
          'frequency set over SPI',
    'U5': 'Dual op amp. A: amplifies the DDS sine by 16.3 into the AD5453 '
          'reference. B: current-to-voltage output stage of the AD5453',
    'U6': '14-bit multiplying DAC: sets the sine amplitude over SPI',
    'D16': 'Zener clamp: limits the AD5453 VREF input to about +-9.8 V',
    'R25': 'Bias resistor to ground for the U5A input after the coupling capacitor C43',
    'R26': 'Bleed resistor to ground on the sine output after the coupling capacitor C8',
    'R35': 'Feedback resistor of the U5A gain stage (with R92: 50.6 k)',
    'R36': 'Gain-setting resistor to ground of the U5A stage (gain 16.3)',
    'R39': 'Series resistor into AD5453 VREF: limits the current into the clamp D16',
    'R40': 'Series output resistor: isolates U5B from the cable capacitance',
    'R92': 'Feedback trim resistor of the U5A gain stage, in series with R35',
    'R96': 'Zero-ohm link from the U5B output to the AD5453 feedback resistor (RFB)',
    'C8': 'Output coupling capacitor: blocks DC on the sine to the amplifier',
    'C9': 'Bulk decoupling capacitor for the AD9837 U4 (+3V3_SG)',
    'C10': 'Bulk decoupling capacitor for the AD5453 U6 (+3V3_SG)',
    'C15': 'Bypass capacitor on the AD9837 internal 2.5 V regulator (CAP/2.5V)',
    'C16': 'Decoupling capacitor for the oscillator U3 (+3V3_SG)',
    'C17': 'Decoupling capacitor for the AD9837 U4 (+3V3_SG)',
    'C18': 'Decoupling capacitor for the op amp U5 (+15 V)',
    'C19': 'Decoupling capacitor for the op amp U5 (-15 V)',
    'C20': 'Decoupling capacitor for the AD5453 U6 (+3V3_SG)',
    'C43': 'Coupling capacitor: removes the DC offset of the DDS output ahead of U5A',
    'C69': 'Decoupling capacitor on the AD9837 DAC bias pin (COMP to VDD)',
    'C85': 'Capacitor across the U5A feedback resistors: limits the bandwidth',
    'C86': 'Compensation capacitor across the AD5453 output stage U5B: stability',
    'TP47': 'Test point: U5A output (the amplified sine into the AD5453 reference)',
    # ── supply jumpers ───────────────────────────────────────────────────
    'JP1': 'Zero-ohm jumper: +3V3 to the signal generator (+3V3_SG)',
    'JP2': 'Zero-ohm jumper: +5V to the +-15 V converter (+5V_PS15)',
    'JP3': 'Zero-ohm jumper: +3V3 to the isolator and its isolated supply (+3V3_ISO)',
    'JP4': 'Zero-ohm jumper: +3V3 to the water cooling pull-ups (+3V3_COOL)',
    'JP5': 'Zero-ohm jumper: +3V3 to the cold head ADC (+3V3_CH)',
    'FB3': 'Ferrite bead: filters buck regulator noise from the cold head ADC supply',
    'JP6': 'Zero-ohm jumper: +5V to the universal I/O ADC, range switches and sensor '
           'excitation (+5V_IO)',
    'FB4': 'Ferrite bead: filters buck regulator noise from the universal I/O ADC supply',
    # ── system current ───────────────────────────────────────────────────
    'U23': 'Power monitor: measures the 12 V rail voltage, current and power '
           'across shunt R78, on the shared SPI bus',
    'D6': 'INA239 ALERT indicator LED (red)',
    'R9': 'Pull-up resistor for the INA239 ALERT output (open drain)',
    'R78': 'Current shunt (10 mOhm, 4-terminal) in the switched 12 V rail; its two '
           'sense pads feed the INA239 input filter',
    'R79': 'Series resistor of the INA239 input filter (IN- / VBUS side)',
    'R80': 'Series resistor of the INA239 input filter (IN+ side)',
    'R81': 'Current-limit resistor for the ALERT LED D6',
    'C32': 'Decoupling capacitor for the INA239 U23 (+3V3)',
    'C46': 'Decoupling capacitor for the INA239 U23 (+3V3)',
    'C66': 'Bulk capacitor on the +12V rail after the shunt',
    'C68': 'High-frequency bypass capacitor on the +12V rail after the shunt',
    'C83': 'Differential filter capacitor across the INA239 shunt inputs',
    # ── water cooling ────────────────────────────────────────────────────
    'J3': 'Radiator fan header (4-pin PWM): GND, +12 V, tach, PWM',
    'J4': 'Coolant pump header (4-pin PWM): GND, +12 V, tach, PWM',
    'J5': 'Alphacool ES flow sensor header: GND, +12 V, flow pulses',
    'J6': 'Alphacool ES coolant NTC (10 k) header',
    'Q61': 'Dual N-FET: open-drain PWM drivers for the fan and the pump',
    'U33': 'ESD clamp array on the fan tach, pump tach, flow and NTC lines (GPIO side)',
    'R6': 'Upper resistor of the coolant NTC divider (10 k to +3V3_COOL)',
    'R15': 'Pull-up resistor for FAN_PWM: holds the fan driver on (0 % drive) at reset',
    'R16': 'Pull-up resistor for PUMP_PWM: holds the pump driver on (0 % drive) at '
           'reset',
    'R43': 'Series resistor from the flow sensor output to GPIO18: limits the '
           'current on a 12 V short',
    'R53': 'Series gate resistor from GPIO9 (FAN_PWM) to the fan driver',
    'R54': 'Series gate resistor from GPIO14 (PUMP_PWM) to the pump driver',
    'RN1': 'Fan and pump tach lines: a pull-up to +3V3_COOL and a series resistor '
           'to the GPIO for each (4.7 k)',
    'RN2': 'Pull-up resistors (10 k to +3V3_COOL) for the fan PWM, pump PWM and '
           'flow tach lines; one element spare',
    'C23': 'Filter capacitor on the coolant NTC ADC input',
    'C76': 'Bulk capacitor on +12V at the fan and pump headers',
    'C77': 'Bulk capacitor on +12V at the fan and pump headers',
}


# What each labelled net carries, by label name. Written into the hidden
# Description field of every net label and global label of that name.
NET_DESCRIPTIONS = {
    # shared SPI bus and chip selects
    '{SPI}': 'Shared SPI bus: SPI_SCK, SPI_MOSI and SPI_MISO (ESP32 GPIO42, 41, 40)',
    'SPI_SCK': 'Shared SPI bus clock from the ESP32 (GPIO42)',
    'SPI_MOSI': 'Shared SPI bus data from the ESP32 to the devices (GPIO41)',
    'SPI_MISO': 'Shared SPI bus data from the selected device to the ESP32 (GPIO40)',
    'CS_ADDR_A': 'Chip-select decoder address bit A (GPIO3, strap pulled high)',
    'CS_ADDR_B': 'Chip-select decoder address bit B (GPIO44)',
    'CS_ADDR_C': 'Chip-select decoder address bit C (GPIO45, strap pulled low)',
    'CS_ADDR_D': 'Chip-select decoder address bit D at 3.3 V, after the buffer U51',
    'CS_ADDR_D_1V8': 'Chip-select decoder address bit D from GPIO47 (1.8 V), '
                     'before the buffer U51',
    'CS_EN_N': 'Chip-select decoder enable, active low (GPIO8): high at reset, so '
               'no device is selected',
    'AD9833_FSYNC': 'Chip select (FSYNC, active low) for the AD9837 DDS, decoder Y0',
    'AD5453_SYNC': 'Chip select (SYNC, active low) for the AD5453 amplitude DAC, '
                   'decoder Y1',
    'INA239_CS': 'Chip select (active low) for the INA239 power monitor, decoder Y2',
    'EXPANDER_CS': 'Chip select (active low) for the MCP23S08 GPIO expander, '
                   'decoder Y3',
    'ACS_CS': 'Chip select (active low) for the ACS37800 current monitor, decoder '
              'Y5; also opens the two bus gates U41 / U42',
    'ADS1220_CS': 'Chip select (active low) for the ADS1220 cold head ADC, decoder Y6',
    'IMU_CS': 'Chip select (active low) for the LSM6DSOX IMU on the cable, decoder Y7',
    'AMBIENT_CS': 'Chip select (active low) for the ADT7320 ambient sensor, decoder Y8',
    'ACS_SCK': 'SPI clock to the ACS37800 isolator, passed by gate U41 only while '
               'ACS_CS is low',
    'ACS_MISO': 'ACS37800 data out from the isolator, before gate U42 puts it on '
                'SPI_MISO',
    # ESP32 control and boot
    'ESP_EN': 'ESP32 enable / reset, active low: RESET button, power-on RC delay '
              'and the display reset line (J15)',
    'ESP_BOOT': 'ESP32 GPIO0 boot strap: held low at reset for USB download mode',
    'USB_VBUS': 'USB-C 5 V from the host: feeds +5V_OR when the 12 V supply is absent',
    'STATUS_RGB': 'Data line to the WS2812B status LED (GPIO38, before the level '
                  'shifter)',
    # power button
    'PWR_BTN': 'Power button line to the LTC2954 PB pin, active low: SW3 or the '
               'display output on J15',
    'PWR_INT': 'LTC2954 INT# to GPIO1: pulses low when the button asks for a '
               'shutdown',
    'PWR_KILL': 'GPIO10 to LTC2954 KILL#: driven low to cut the board power',
    'DISP_PWR_BTN': 'Power button line from the display header J15 (DO0), before '
                    'its 100 R series resistor',
    'DISP_RESET': 'Reset line from the display header J15 (DO1), before its 100 R '
                  'series resistor',
    'STATUS_GA': 'Green anode of the status LED D7, fed from +5V (on)',
    'STATUS_RA': 'Red anode of the status LED D7, fed from VIN and shorted by Q41 '
                 'once +3V3 is up (standby)',
    # +-15 V power good
    'PGP_15V': '+15 V power-good node: about 3.2 V when good, low when the regulator '
               'PGP pin pulls it down',
    'PGN_15V': '-15 V power-good node: about 3.2 V when good, low when the regulator '
               'PGN pin or the guard Q42 pulls it down',
    'PG_15V': 'Both +-15 V rails good (AND of PGP_15V and PGN_15V), active high: '
              'gates the amplifier REM switch',
    'PG_15V_N': '+-15 V power-good flag to GPIO43, active low: low when both rails '
                'are good',
    'PGP_LED_GA': 'Green anode of the +15 V power-good LED D11',
    'PGP_LED_GK': 'Green cathode of D11, pulled low by Q23 when +15 V is good; also '
                  'the Q51 gate',
    'PGP_LED_RA': 'Red anode of the +15 V power-good LED D11',
    'PGP_LED_RK': 'Red cathode of D11, pulled low by Q51 when +15 V is bad',
    'PGN_LED_GA': 'Green anode of the -15 V power-good LED D12',
    'PGN_LED_GK': 'Green cathode of D12, pulled low by Q24 when -15 V is good; also '
                  'the Q52 gate',
    'PGN_LED_RA': 'Red anode of the -15 V power-good LED D12',
    'PGN_LED_RK': 'Red cathode of D12, pulled low by Q52 when -15 V is bad',
    # signal chain and amplifier
    'DDS_SINE': 'Sine output of the AD9837 DDS, before the gain stage',
    'SIG_SINE': 'Sine drive signal out to the amplifier input jack J9, amplitude '
                'set by the AD5453',
    'AMP_REM_EN': 'GPIO6: high turns the amplifier REM (remote on) line on',
    'AMP_REM': 'Amplifier remote-on line at J8: 12 V when on',
    'AMP_REM_LED': 'Common node of the amplifier REM LED D2, fed from +5V through R60',
    'COMP_RELAY_EN': 'GPIO16: high switches the compressor relay on',
    'COMP_RELAY': 'Switched +12 V to the compressor relay coil at J13',
    'COMP_RELAY_LED': 'Common node of the compressor relay LED D3, fed from +5V '
                      'through R61',
    # display link
    'CAN_TX': 'CAN transmit data from the ESP32 (GPIO17) to the transceiver U52',
    'CAN_RX': 'CAN receive data from the transceiver U52 to the ESP32 (GPIO12)',
    'CAN_H': 'CAN bus high line to the display header J15',
    'CAN_L': 'CAN bus low line to the display header J15',
    # monitors and sensors
    'INA239_ALERT': 'INA239 ALERT output, open drain, active low: lights D6 and is '
                    'read on expander GP6',
    'ALERT_LED_A': 'Anode of the INA239 ALERT LED D6, fed from +3V3 through R81',
    'AMBIENT_INT': 'ADT7320 INT output, open drain, active low, read on expander GP2',
    'AMBIENT_CT': 'ADT7320 critical temperature output, open drain, active low, '
                  'read on expander GP3',
    'IMU_INT1': 'LSM6DSOX interrupt 1 from the IMU cable to GPIO2',
    'IMU_INT2': 'LSM6DSOX interrupt 2 from the IMU cable to GPIO39',
    'RTD_1': 'PT1000 lead 1 (J10 pin 1): excitation current from the ADS1220',
    'RTD_2': 'PT1000 lead 2 (J10 pin 2): sense line to ADS1220 AIN1',
    'RTD_3': 'PT1000 lead 3 (J10 pin 3): sense line to ADS1220 AIN0',
    'RTD_4': 'PT1000 lead 4 (J10 pin 4): current return through the reference '
             'resistor R62',
    'ISO_5V_LED_A': 'Anode of the isolated 5 V indicator LED D10',
    # water cooling
    'FAN_PWM': 'GPIO9: fan PWM to the open-drain driver (high = 0 % drive)',
    'PUMP_PWM': 'GPIO14: pump PWM to the open-drain driver (high = 0 % drive)',
    'FAN_TACH': 'Fan tach pulses to GPIO15 (2 per revolution)',
    'PUMP_TACH': 'Pump tach pulses to GPIO21 (2 per revolution)',
    'FLOW_TACH': 'Coolant flow sensor pulses to GPIO18',
    'NTC_ADC': 'Coolant NTC divider voltage to GPIO4 (ADC1)',
    # universal I/O fast channels
    'AUX_IO11': 'GPIO11 to the AUX header J40 pin 3 through 100 R: spare pin for a UART, '
                'I2C, 1-Wire, touch (T11) or GPIO',
    'AUX_IO13': 'GPIO13 to the AUX header J40 pin 4 through 100 R: spare pin for a UART, '
                'I2C, 1-Wire, touch (T13) or GPIO',
    'AUX11_HDR': 'GPIO11 line at the AUX header J40 pin 3, after its series resistor',
    'AUX13_HDR': 'GPIO13 line at the AUX header J40 pin 4, after its series resistor',
    'AUX_IO5': 'GPIO5: PWM gate and pulse input of universal I/O channel 1, '
               'MCU side of the two 1 k resistors',
    'AUX_IO7': 'GPIO7: PWM gate and pulse input of universal I/O channel 2, '
               'MCU side of the two 1 k resistors',
}


# ── universal I/O (rev 5) ────────────────────────────────────────────────
# The four channels are one circuit drawn four times, so their parts and nets
# are described by role; gen_schematic.py fills in the channel number {n} (and
# {gpio} on the fast channels) and adds each entry to the tables above.
IO_PART_ROLES = {
    'amp': 'Output drivers of I/O channels {first} and {last}: each section multiplies its '
           'channel level by 4.83 (0-12 V, up to 100 mA through the output switch)',
    'gain_low': 'Gain resistor to ground for the channel {n} output driver '
                '(gain 1 + 191k / 49.9k = 4.83)',
    'gain_high': 'Feedback resistor of the channel {n} output driver (gain 4.83)',
    'gain_cap': 'Feedback capacitor across the 191k of the channel {n} output driver '
                '(cancels the input capacitance)',
    'gate': 'Analog switch for channel {n}: passes the DAC level to the output driver while '
            'GPIO{gpio} is high and ground while it is low (PWM at the configured level)',
    'divider_top': 'Series resistor from the channel {n} pin to its ADC input: top of the '
                   '6:1 divider and the fault-current limit for the ADC',
    'divider_bottom': 'Bottom leg of the channel {n} 6:1 input divider, grounded through the '
                      'range switch (open for the direct 0-2.5 V range)',
    'adc_filter': 'Filter capacitor at the channel {n} ADC input (16 Hz with the 100k)',
    'burden': 'Loop burden for channel {n}: 4-20 mA reads 0.48-2.4 V in the direct range; '
              '2512 so it survives 12 V on the pin',
    'burden_fet': 'Switch that grounds the channel {n} loop burden while IO{n}_BURDEN is high',
    'fast_series': 'Series resistor from the channel {n} pin to its GPIO{gpio} input buffer: '
                   'limits the clamp current when the pin is above 3.3 V',
    'fast_clamp': 'Clamp diode to +3V3 at the channel {n} input buffer, so a 5 V or 12 V '
                  'signal reads as a 3.3 V logic level',
    'fast_buffer': 'Tri-state buffer from the channel {n} pin to GPIO{gpio} (pulse and tach '
                   'input), off while IO{n}_BUF_OE_N is high',
    'fast_out': 'Series resistor between the channel {n} input buffer and GPIO{gpio}: limits '
                'the current if both drive at once',
    'gate_series': 'Series resistor from GPIO{gpio} to the channel {n} output gate select',
    'sensor_switch': 'Sensor supply switch for I/O channel {n}: feeds connector pin 1 from '
                     'the jumper-selected 5 V or 12 V while IO{n}_SENS_EN is high, limited '
                     'to 124 mA, with a fault flag',
    'jumper_5v': 'Fit to give the channel {n} sensor supply 5 V (fitted by default; never '
                 'fit both jumpers of a channel)',
    'jumper_12v': 'Fit instead of the 5 V jumper to give the channel {n} sensor supply 12 V '
                  '(left open by default)',
    'uvlo': 'Ties TPS26625 UVLO to IN for channel {n} (the datasheet asks for at least 1 M '
            'when the lockout is unused)',
    'sensor_in_cap': 'Input capacitor of the channel {n} sensor supply switch',
    'sensor_out_cap': 'Output capacitor of the channel {n} sensor supply at the connector',
    'sensor_limit': 'Current-limit resistor on TPS26625 ILIM for channel {n}: '
                    '53.6k gives 124 mA',
    'connector': 'Universal I/O channel {n}: 1 switched sensor supply (5 V or 12 V), '
                 '2 signal (0-12 V in or out), 3 GND, 4 not connected',
    'supply_clamp': 'Surge clamp on the channel {n} sensor supply pin at the connector',
    'pin_clamp': 'Surge clamp on the channel {n} signal pin at the connector',
    'pull_sens_flt': 'Pull-up resistor for the channel {n} sensor supply fault flag '
                     '(open drain)',
    'pull_out_en': 'Pull-down resistor for IO{n}_OUT_EN: output switch open until the expander '
                   'drives it',
    'pull_sens_en': 'Pull-down resistor for IO{n}_SENS_EN: overrides the TPS26625 internal '
                    'pull-up so the sensor supply is off until the expander drives it',
    'pull_burden': 'Pull-down resistor for IO{n}_BURDEN: loop burden off until the expander '
                   'drives it',
    'pull_buf_oe': 'Pull-up resistor for IO{n}_BUF_OE_N: input buffer off until the expander '
                   'drives it',
    'pull_gate': 'Pull-down resistor for the channel {n} output gate select: ground level '
                 'selected while GPIO{gpio} floats at boot',
    'decoupling': 'Decoupling capacitor for the I/O channel {n} ICs',
    'dac': '8-channel DAC: sets the output level of each universal I/O channel '
           '(pin voltage = DAC output x 4.83)',
    'dac_ref': 'DAC60508 reference capacitor (two 100 nF for the 150 nF minimum)',
    'adc': '24-bit ADC: reads the four universal I/O pins (AIN0-3) against ground, the two pressure ports and the two precision ports',
    'adc_ref': 'ADS124S08 reference capacitor, REFOUT to REFCOM',
    'core_decoupling': 'Decoupling capacitor for the universal I/O DAC or ADC',
    'range_switch': 'Range switches of I/O channels {first}-{last}: each grounds a 20k '
                    'divider leg (0-15 V range) and opens for the direct 0-2.5 V range',
    'pull_switch': 'Pull-up switches of I/O channels {first}-{last}: each joins a pin to '
                   '10k / +3V3 for an NTC or a contact, and blocks a pin above 3.3 V',
    'pull_resistor': 'Switched pull-up resistor to +3V3 for the I/O channel {n} pin',
    'pull_direct': 'Pull-down resistor for IO{n}_DIRECT: divider engaged (0-15 V range) '
                   'until the expander drives it',
    'pull_pullup': 'Pull-down resistor for IO{n}_PULLUP: pull-up off until the expander '
                   'drives it',
    'switch_decoupling': 'Decoupling capacitor for the universal I/O range and pull-up '
                         'switches',
    'expander': 'I/O expander at address {address}: mode bits and fault flags of I/O '
                'channel {a} (port A) and channel {b} (port B)',
    'pull_exp_int': 'Pull-up resistor for IO_EXP_INT_N (open-drain interrupt outputs of '
                    'the two I/O expanders)',
    'expander_decoupling': 'Decoupling capacitor for the universal I/O expanders',
    'display_fuse': 'Resettable fuse in the 12 V feed to the display (J15 pin 2): 0.5 A '
                    'hold, so a shorted cable does not blow the main fuse F1',
    'can_clamp': 'ESD clamp on CAN_H and CAN_L at the display connector J15',
    'auto_on_jumper': 'Fit for auto power-on: connects the 2.2 uF capacitor to the LTC2954 '
                      'PB pin (left open by default)',
    'auto_on_cap': 'Auto power-on capacitor: holds PB low for a moment after 12 V '
                   'arrives (only in circuit with its jumper fitted)',
    'auto_on_diode': 'Empties the auto power-on capacitor into VIN when the supply drops, '
                     'so a short interruption still gives a turn-on pulse',
    'press_connector': 'Pressure port {n} ({scale} transmitter): 1 switched 5 V excitation, '
                       '2 signal (0.5-4.5 V), 3 GND, 4 not connected',
    'press_series': 'Series resistor from the pressure port {n} signal to its ADC pin: limits '
                    'the current into the ADC if the pin is taken above 5 V',
    'press_pull': 'Pull-down resistor on the pressure port {n} signal: an unplugged sensor '
                  'reads 0 V',
    'press_filter': 'Filter capacitor to ground at the pressure port {n} ADC input',
    'press_clamp': 'Surge clamp on the pressure port {n} signal at the connector',
    'prec_connector': 'Precision sensor port {p}: 1 switched 5 V excitation, 2 IN+, 3 IN-, '
                      '4 GND; for a bridge, RTD, thermocouple or millivolt sensor',
    'prec_series': 'Series resistor from a precision port {p} input to its ADC pin: limits '
                   'the fault current into the ADC and forms the input filter',
    'prec_filter': 'Filter capacitor to ground at a precision port {p} ADC input',
    'prec_diff_filter': 'Filter capacitor across the precision port {p} input pair',
    'prec_clamp': 'Surge clamp on a precision port {p} input at the connector',
    'prec_switch': 'Excitation switch for both precision ports: feeds their pin 1 from '
                   '+5V_IO while PREC_EXC_EN is high, limited to 124 mA, with a fault flag',
    'prec_uvlo': 'Ties the excitation switch UVLO to IN (lockout unused)',
    'prec_in_cap': 'Input capacitor of the precision port excitation switch',
    'prec_out_cap': 'Output capacitor on the precision port excitation',
    'prec_limit': 'Current-limit resistor of the excitation switch: 53.6k gives 124 mA',
    'prec_exc_clamp': 'Surge clamp on the precision port excitation at the connectors',
    'prec_ref_series': 'Series resistor from the excitation (or its ground) to the ADC '
                       'external reference input',
    'prec_ref_filter': 'Filter capacitor across the ADC external reference inputs',
    'pull_prec_flt': 'Pull-up resistor for the excitation switch fault flag (open drain)',
    'pull_prec_en': 'Pull-down resistor for PREC_EXC_EN: excitation off until the expander '
                    'drives it',
    'out_switch': 'Output switches of I/O channels {first}-{last}: each joins a driver to '
                  'its pin while OUT_EN is high and opens if the pin is forced past the rails',
    'pull_out_flt': 'Pull-up resistor for the output switch fault flag FF (open drain), '
                    'channels group {g}',
    'driver_decoupling': 'Decoupling capacitor for the universal I/O output drivers and '
                         'switches (+12V)',
    'uart': 'SPI to UART bridge for the RS-485 port; its RTS output switches the bus '
            'direction by itself',
    'rs485_phy': 'RS-485 transceiver for the Modbus port on J34',
    'rs485_rx_pull': 'Pull-up resistor on the UART RX line: idle level while the RS-485 '
                     'receiver output is off (during transmit)',
    'rs485_inverter': 'Inverts the UART RTS output onto RS-485 DE and /RE: receive after '
                      'reset, transmit while RTS is low',
    'rs485_de_pull': 'Pull-up resistor (drain load) of the RS-485 direction inverter',
    'rs485_termination': 'RS-485 bus termination, in circuit only with its jumper fitted',
    'rs485_term_jumper': 'Fit when this board is at an end of the RS-485 bus: connects the '
                         '120 R termination (left open by default)',
    'rs485_connector': 'RS-485 / Modbus port (JST PH, top entry): 1 A, 2 B, 3 GND, 4 not connected',
    'uart_clock': '16 MHz clock for the SC16IS750 UART (same part as the signal generator clock)',
    'exp_miso_gate': 'Buffer that passes the expansion header MISO to the SPI bus only '
                     'while chip select {which} is low',
    'exp_series': 'Series resistor between the SPI bus and the expansion header: limits '
                  'the damage a shorted daughterboard line can do and damps the cable',
    'exp_header': 'SPI expansion header (JST PH, top entry): 1 +3V3, 2 +5V, 3 SCK, 4 MOSI, '
                  '5 MISO, 6 interrupt, 7 chip select A, 8 chip select B, 9 and 10 GND, '
                  'for a future daughterboard',
    'pull_rs485_irq': 'Pull-up resistor for the SC16IS750 IRQ output (open drain; the '
                      'datasheet asks for 1 k at 3.3 V)',
    'pull_exp_hdr_int': 'Pull-up resistor for the expansion header interrupt line',
    'aux_series': 'Series resistor between GPIO{gpio} and the AUX header: limits the '
                  'damage a shorted cable can do',
    'aux_clamp': 'ESD clamp on the AUX header line of GPIO{gpio}, on the cable side of its '
                 'series resistor',
    'aux_pull': 'Pull-up resistor for the AUX header line of GPIO{gpio}, not fitted: fit '
                'for I2C or 1-Wire',
    'aux_header': 'AUX header (JST PH, top entry): 1 +5V, 2 +3V3, 3 GPIO11, 4 GPIO13, '
                  '5 GND; UART, I2C, 1-Wire, touch or GPIO, chosen in firmware',
    'pull_exp_miso': 'Pull-down resistor on the expansion header MISO: defined level with '
                     'no daughterboard fitted',
    'expansion_decoupling': 'Decoupling capacitor for the RS-485 port or the expansion '
                            'header buffers',
}

# key -> (net name, description)
IO_NET_ROLES = {
    'pin': ('IO{n}_PIN', 'I/O channel {n} signal pin (connector pin 2): 0-12 V in or out'),
    'dac': ('IO{n}_DAC', 'DAC output {n}: 0-2.5 V level for the channel {n} output driver '
                         '(pin voltage / 4.83)'),
    'adc': ('IO{n}_ADC', 'Channel {n} pin after the 100k series resistor, to the ADC input'),
    'div': ('IO{n}_DIV', 'Bottom of the channel {n} 20k divider leg, to the range switch'),
    'gate': ('IO{n}_GATE', 'Channel {n} output gate select: high passes the DAC level, low '
                           'grounds the driver input'),
    'out_en': ('IO{n}_OUT_EN', 'Expander output, high closes the channel {n} output '
                               'switch; pulled low'),
    'direct': ('IO{n}_DIRECT', 'Expander output, high opens the channel {n} divider leg '
                               '(direct 0-2.5 V range); pulled low = 0-15 V range'),
    'burden': ('IO{n}_BURDEN', 'Expander output, high switches in the channel {n} 120 R '
                               'loop burden; pulled low'),
    'pullup': ('IO{n}_PULLUP', 'Expander output, high connects 10k to +3V3 on the channel '
                               '{n} pin; pulled low'),
    'sens_en': ('IO{n}_SENS_EN', 'Expander output, high turns on the channel {n} sensor '
                                 'supply; pulled low'),
    'level': ('IO{n}_LEVEL', 'Channel {n} output level after the GPIO gate, to its driver'),
    'drv': ('IO{n}_DRV', 'Channel {n} driver output, ahead of the output switch'),
    'out_flt': ('IO_OUT_FLT_{g}_N', 'Output switch fault flag of channels 1-4 (group {g}): '
                                    'low while a pin is forced past the rails, '
                                    'open drain, to the expander'),
    'sens_flt': ('IO{n}_SENS_FLT_N', 'Channel {n} sensor supply fault flag, open drain, '
                                     'active low, to the expander'),
    'dac_cs': ('IO_DAC_CS', 'Chip select (active low) for the universal I/O DAC, '
                            'decoder Y4'),
    'adc_cs': ('IO_ADC_CS', 'Chip select (active low) for the universal I/O ADC, '
                            'decoder Y9'),
    'exp_cs': ('IO_EXP_CS', 'Chip select (active low) shared by the four universal I/O '
                            'expanders, decoder Y10'),
    'adc_drdy': ('IO_ADC_DRDY_N', 'ADS124S08 data ready, active low, read on expander GP5'),
    'exp_int': ('IO_EXP_INT_N', 'Interrupt of the four universal I/O expanders, open '
                                'drain, active low, read on expander GP4'),
    'logic': ('IO{n}_LOGIC', 'Channel {n} pin behind 1 M, clamped to +3V3: input of the '
                             'pulse buffer'),
    'buf': ('IO{n}_BUF', 'Channel {n} pulse buffer output, ahead of its 1 k to the ESP32 pin'),
    'rs485_cs': ('RS485_CS', 'Chip select (active low) for the SC16IS750 UART bridge, '
                             'decoder Y11'),
    'rs485_irq': ('RS485_IRQ_N', 'SC16IS750 interrupt, open drain, active low, read on '
                                 'I/O expander 2 port A bit 7'),
    'rs485_rts': ('RS485_RTS_N', 'SC16IS750 RTS: low while the UART sends, high after '
                                 'reset; gate of the direction inverter'),
    'uart_clk': ('UART_CLK', '16 MHz oscillator output to SC16IS750 XTAL1'),
    'exp_cs_a': ('EXP_CS_A', 'Chip select A (active low) for the SPI expansion header, '
                             'decoder Y12'),
    'exp_cs_b': ('EXP_CS_B', 'Chip select B (active low) for the SPI expansion header, '
                             'decoder Y13'),
    'hdr_int': ('EXP_INT_N', 'Expansion header interrupt line, active low, read on I/O '
                             'expander 2 port B bit 7'),
    'exp_sck': ('EXP_SCK', 'SPI clock at the expansion header, behind 100 R'),
    'exp_mosi': ('EXP_MOSI', 'SPI MOSI at the expansion header, behind 100 R'),
    'exp_miso': ('EXP_MISO', 'MISO from the expansion header, to the two bus buffers'),
    'exp_csa': ('EXP_CSA', 'Chip select A at the expansion header, behind 100 R'),
    'exp_csb': ('EXP_CSB', 'Chip select B at the expansion header, behind 100 R'),
    'press_pin': ('PRESS{n}_PIN', 'Pressure port {n} signal at the connector (pin 2)'),
    'press_adc': ('PRESS{n}_ADC', 'Pressure port {n} signal, filtered, to the ADC'),
    'prec_p': ('PREC_{p}_P', 'Precision port {p} IN+, filtered, to the ADC'),
    'prec_n': ('PREC_{p}_N', 'Precision port {p} IN-, filtered, to the ADC'),
    'prec_p_pin': ('PREC_{p}_P_PIN', 'Precision port {p} IN+ at the connector'),
    'prec_n_pin': ('PREC_{p}_N_PIN', 'Precision port {p} IN- at the connector'),
    'prec_exc': ('PREC_EXC', 'Switched 5 V excitation for the precision and pressure ports (pin 1)'),
    'prec_refp': ('PREC_REFP', 'Excitation voltage to ADC REFP0 (ratiometric reference)'),
    'prec_refn': ('PREC_REFN', 'Excitation ground to ADC REFN0'),
    'prec_exc_en': ('PREC_EXC_EN', 'I/O expander 3 port A bit 7, high turns the precision '
                                   'port excitation on; pulled low'),
    'prec_exc_flt': ('PREC_EXC_FLT_N', 'Excitation switch fault flag, open drain, active '
                                       'low, read on I/O expander 3 port B bit 7'),
    'buf_oe': ('IO{n}_BUF_OE_N', 'Expander output, low enables the channel {n} input buffer '
                                 'to the ESP32 pin; pulled high'),
}
