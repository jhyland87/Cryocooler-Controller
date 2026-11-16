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
    'FB1': 'Ferrite bead between the isolated DC-DC output (VISOOUT) and the '
           'isolated 5 V rail: filters converter noise',
    'FB2': 'Ferrite bead in the isolated DC-DC ground return (GND2 to ISO_GND)',
    'R22': 'Pull-up resistor for the ISOW7741 EN/FLT pin: converter enabled',
    'R63': 'Lower resistor of the ACS37800 voltage sense divider (4 x 1 M over 4.02 k)',
    'R64': 'Voltage sense divider, upper string 1 of 4 (drive voltage to ACS37800 VINP)',
    'R65': 'Voltage sense divider, upper string 2 of 4 (drive voltage to ACS37800 VINP)',
    'R66': 'Voltage sense divider, upper string 3 of 4 (drive voltage to ACS37800 VINP)',
    'R67': 'Voltage sense divider, upper string 4 of 4 (drive voltage to ACS37800 VINP)',
    'R501': 'Pull-up resistor for the gated ACS_SCK line: idles high (SPI mode 3) '
            'while gate U41 is off',
    'C6': 'Bulk input capacitor for the ISOW7741 DC-DC supply pin VDD (+5V_ISO)',
    'C7': 'Bulk output capacitor on the ISOW7741 isolated output VISOOUT',
    'C31': 'Decoupling capacitor for the ACS37800 U18 (isolated 5 V)',
    'C45': 'Decoupling capacitor for the ACS37800 U18 (isolated 5 V)',
    'C51': 'Decoupling capacitor for the ISOW7741 logic supply VIO (+3V3)',
    'C52': 'Decoupling capacitor for the ISOW7741 DC-DC supply pin VDD (+5V_ISO)',
    'C53': 'Decoupling capacitor on the ISOW7741 isolated output VISOOUT',
    'C54': 'Decoupling capacitor for the ISOW7741 isolated-side supply VISOIN',
    'C72': 'High-frequency decoupling capacitor for the ISOW7741 logic supply VIO',
    'C73': 'High-frequency decoupling capacitor for the ISOW7741 DC-DC supply pin VDD',
    'C74': 'High-frequency decoupling capacitor on the ISOW7741 output VISOOUT',
    'C75': 'High-frequency decoupling capacitor for the ISOW7741 supply VISOIN',
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
           'touch display, drawn to show where the J15 and J21 cables land; not a '
           'part of this board',
    'J15': 'Display link header: unswitched 12 V and GND to power the Waveshare '
           'touch display, and the CAN bus pair',
    'J21': 'Display button header: the display pulls PWR_BTN or RESET low through '
           'its two open-collector outputs',
    'U52': 'CAN transceiver: carries telemetry to, and commands from, the Waveshare '
           'touch display',
    'U53': 'ESD clamp on the power button line from the display header J21',
    'U54': 'ESD clamp on the reset line from the display header J21',
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
    # ── general-purpose I/O ──────────────────────────────────────────────
    'J16': 'General-purpose I/O header: GPIO5 and GND',
    'J17': 'General-purpose I/O header: GPIO7 and GND',
    'J18': 'General-purpose I/O header: GPIO11 and GND',
    'J20': 'General-purpose I/O header: GPIO13 and GND',
    'U43': 'Quad op amp: LED driver for IO11 (three sections spare, wired as '
           'followers)',
    'U44': 'Quad op amp: LED drivers for IO5, IO7 and IO13 (one section spare, '
           'wired as a follower)',
    'U45': 'ESD clamp on the IO5 header pin',
    'U46': 'ESD clamp on the IO13 header pin',
    'U47': 'ESD clamp on the IO7 header pin',
    'U48': 'ESD clamp on the IO11 header pin',
    'D81': 'IO5 activity LED (green): brightness follows the pin voltage',
    'D82': 'IO7 activity LED (green): brightness follows the pin voltage',
    'D83': 'IO11 activity LED (green): brightness follows the pin voltage',
    'D85': 'IO13 activity LED (green): brightness follows the pin voltage',
    'RN3': 'Series protection resistors (100 R) between GPIO5, 7, 11, 13 and their '
           'headers',
    'RN4': 'Upper resistors of the IO5, IO7, IO11, IO13 sense dividers (pin to the '
           'LED driver input)',
    'RN5': 'Lower resistors of the IO5, IO7, IO11, IO13 sense dividers; with RN4 '
           'they also pull an open pin low',
    'R506': 'LED current-set resistor for the IO5 LED driver (I = Vpin / 6.6 k)',
    'R507': 'LED current-set resistor for the IO7 LED driver (I = Vpin / 6.6 k)',
    'R508': 'LED current-set resistor for the IO11 LED driver (I = Vpin / 6.6 k)',
    'R510': 'LED current-set resistor for the IO13 LED driver (I = Vpin / 6.6 k)',
    'C303': 'Decoupling capacitor for the LED driver op amps U43 / U44 (+5V_OR)',
    'C304': 'Decoupling capacitor for the LED driver op amps U43 / U44 (+5V_OR)',
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
    'J2': '12 V DC input jack (5.5 x 2.1 mm, centre positive)',
    'F1': 'Backup input fuse (5 A) on the 12 V input',
    'D1': 'TVS diode on the 12 V input: clamps surges, and blows the fuse on '
          'reverse polarity',
    'C65': 'Bulk capacitor on the 12 V input rail (VIN)',
    'C67': 'High-frequency bypass capacitor on the 12 V input rail (VIN)',
    # ── +-15 V rails ─────────────────────────────────────────────────────
    'U20': 'Dual switching converter: boosts 5 V to +16.5 V and inverts it to '
           '-16.5 V ahead of the linear regulator',
    'U21': 'Dual low-noise linear regulator: makes the +-15 V analog rails (about '
           '+-14.7 V) and their power-good flags',
    'L2': 'Boost inductor of the ADP5071 positive converter (+16.5 V)',
    'L3': 'Inductor of the ADP5071 inverting converter (-16.5 V)',
    'D4': 'Rectifier diode of the ADP5071 boost converter (+16.5 V)',
    'D5': 'Rectifier diode of the ADP5071 inverting converter (-16.5 V)',
    'R11': 'Lower resistor of the LT3097 +15 V power-good threshold divider (PGFBP)',
    'R12': 'Lower resistor of the LT3097 -15 V power-good threshold divider (PGFBN)',
    'R68': 'Compensation resistor on ADP5071 COMP1 (boost loop), in series with C79',
    'R69': 'Compensation resistor on ADP5071 COMP2 (inverting loop), in series with C55',
    'R70': 'Upper feedback resistor setting the +16.5 V rail (ADP5071 FB1)',
    'R71': 'Lower feedback resistor setting the +16.5 V rail (ADP5071 FB1)',
    'R72': 'Feedback resistor from the -16.5 V rail to ADP5071 FB2',
    'R73': 'Feedback resistor from ADP5071 FB2 to VREF: with R72 it sets -16.5 V',
    'R74': 'Upper resistor of the LT3097 +15 V power-good threshold divider (PGFBP)',
    'R75': 'Upper resistor of the LT3097 -15 V power-good threshold divider (PGFBN)',
    'R76': 'LT3097 SETP resistor: sets the positive output (100 uA x 147 k = 14.7 V)',
    'R77': 'LT3097 SETN resistor: sets the negative output (100 uA x 147 k = -14.7 V)',
    'C11': 'Input capacitor for the ADP5071 U20 (+5V_PS15)',
    'C12': 'Input capacitor for the ADP5071 U20 (+5V_PS15)',
    'C40': 'High-frequency input bypass capacitor for the ADP5071 U20',
    'C49': 'Bypass capacitor on the ADP5071 internal regulator (VREG)',
    'C50': 'Bypass capacitor on the ADP5071 reference (VREF)',
    'C55': 'Compensation capacitor on ADP5071 COMP2, in series with R69',
    'C56': 'Output capacitor of the +16.5 V converter and input capacitor of the '
           'LT3097 positive channel',
    'C57': 'Output capacitor on the +15 V rail (LT3097)',
    'C58': 'Output capacitor on the -15 V rail (LT3097)',
    'C59': 'Output capacitor on the +15 V rail (LT3097)',
    'C60': 'Output capacitor on the -15 V rail (LT3097)',
    'C61': 'Output capacitor of the -16.5 V converter and input capacitor of the '
           'LT3097 negative channel',
    'C62': 'Output capacitor of the -16.5 V converter and input capacitor of the '
           'LT3097 negative channel',
    'C79': 'Compensation capacitor on ADP5071 COMP1, in series with R68',
    'C81': 'Capacitor across the LT3097 SETP resistor: filters reference noise and '
           'sets the soft start',
    'C82': 'Capacitor across the LT3097 SETN resistor: filters reference noise and '
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
    'JP3': 'Zero-ohm jumper: +5V_OR to the isolated supply (+5V_ISO)',
    'JP4': 'Zero-ohm jumper: +3V3 to the water cooling pull-ups (+3V3_COOL)',
    'JP5': 'Zero-ohm jumper: +3V3 to the cold head ADC (+3V3_CH)',
    'FB3': 'Ferrite bead: filters buck regulator noise from the cold head ADC supply',
    # ── system current ───────────────────────────────────────────────────
    'U23': 'Power monitor: measures the 12 V rail voltage, current and power '
           'across shunt R78, on the shared SPI bus',
    'D6': 'INA239 ALERT indicator LED (red)',
    'R9': 'Pull-up resistor for the INA239 ALERT output (open drain)',
    'R78': 'Current shunt (15 mOhm) in the switched 12 V rail, sensed by the INA239',
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
              'and the display reset line (J21)',
    'ESP_BOOT': 'ESP32 GPIO0 boot strap: held low at reset for USB download mode',
    'USB_VBUS': 'USB-C 5 V from the host: feeds +5V_OR when the 12 V supply is absent',
    'STATUS_RGB': 'Data line to the WS2812B status LED (GPIO38, before the level '
                  'shifter)',
    # power button
    'PWR_BTN': 'Power button line to the LTC2954 PB pin, active low: SW3 or the '
               'display output on J21',
    'PWR_INT': 'LTC2954 INT# to GPIO1: pulses low when the button asks for a '
               'shutdown',
    'PWR_KILL': 'GPIO10 to LTC2954 KILL#: driven low to cut the board power',
    'DISP_PWR_BTN': 'Power button line from the display header J21 (DO0), before '
                    'its 100 R series resistor',
    'DISP_RESET': 'Reset line from the display header J21 (DO1), before its 100 R '
                  'series resistor',
    'STATUS_GA': 'Green anode of the status LED D7, fed from +5V (on)',
    'STATUS_RA': 'Red anode of the status LED D7, fed from VIN and shorted by Q41 '
                 'once +3V3 is up (standby)',
    # +-15 V power good
    'PGP_15V': '+15 V power-good node: about 3.2 V when good, low when the LT3097 '
               'PGP pin pulls it down',
    'PGN_15V': '-15 V power-good node: about 3.2 V when good, low when the LT3097 '
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
    # general-purpose I/O
    'AUX_IO5': 'General-purpose I/O on GPIO5 (ADC1), MCU side of the 100 R resistor',
    'AUX_IO7': 'General-purpose I/O on GPIO7 (ADC1), MCU side of the 100 R resistor',
    'AUX_IO11': 'General-purpose I/O on GPIO11 (ADC2), MCU side of the 100 R resistor',
    'AUX_IO13': 'General-purpose I/O on GPIO13 (ADC2), MCU side of the 100 R resistor',
    'IO5_HDR': 'IO5 at its header J16, after the 100 R resistor',
    'IO7_HDR': 'IO7 at its header J17, after the 100 R resistor',
    'IO11_HDR': 'IO11 at its header J18, after the 100 R resistor',
    'IO13_HDR': 'IO13 at its header J20, after the 100 R resistor',
    'IO5_SENSE': 'Half the IO5 pin voltage (divider tap) into its LED driver',
    'IO7_SENSE': 'Half the IO7 pin voltage (divider tap) into its LED driver',
    'IO11_SENSE': 'Half the IO11 pin voltage (divider tap) into its LED driver',
    'IO13_SENSE': 'Half the IO13 pin voltage (divider tap) into its LED driver',
}
