"""Datasheet-derived connection rules, checked against an exported netlist.

Each rule encodes something verified in a manufacturer datasheet (see
../DESIGN_REVIEW.md).
Usage: python3 datasheet_rules.py netlist.net          (main board)
       python3 datasheet_rules.py --imu imu.net        (IMU board, imu/)
"""

import sys

from sexpr import find_all, sval
from verify_netlist import load

# ('net', value, pin, net)            pin is on a named net
# ('same', value, pin_a, pin_b)       two pins of the same part share a net
# ('res', value, pin, ohms, rail)     the pin's net has a resistor of that
# value whose other end is on rail
# ('nc', value, pin)                  pin is not connected
# ('between', part_value, A, B)       a two-terminal part sits between targets
# A and B; a target is
#                                     ('NET', name) or (value, pin)
# ('join', value, pin, value2, pin2)  two parts' pins share a net (net may be
# auto-named)
# ('resjoin', value, pin, ohms, value2, pin2)  pin's net has a resistor whose
# far end is on value2.pin2's net
# ('fetdrive', value, pin, ohms, net)  pin is the drain of a BSS138 with source
# on GND and its gate through `ohms` to `net`
# ('nores', value, pin, rail)          no resistor joins the pin's net to rail
# ('caps', net, value, count, net2)   at least `count` capacitors of that value
# sit between net and net2
RULES = [
    # 4-pin fans (Intel 4-wire spec): PWM open drain through a BSS138 with the
    # gate pulled to +3V3 (0% drive at reset), tach open collector with a
    # pull-up at the connector and 4.7k to the GPIO
    ('fetdrive', 'FAN (4-pin PWM)', '4', '1k', 'FAN_PWM'),
    ('res', 'FAN (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'FAN (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '4.7k', ('FAN (4-pin PWM)', '3'), ('NET', 'FAN_TACH')),
    ('net', 'FAN (4-pin PWM)', '2', '+12V'),
    ('net', 'FAN (4-pin PWM)', '1', 'GND'),
    ('fetdrive', 'PUMP (4-pin PWM)', '4', '1k', 'PUMP_PWM'),
    ('res', 'PUMP (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'PUMP (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '4.7k', ('PUMP (4-pin PWM)', '3'), ('NET', 'PUMP_TACH')),
    ('net', 'PUMP (4-pin PWM)', '2', '+12V'),
    ('net', 'PUMP (4-pin PWM)', '1', 'GND'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '17', 'FAN_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '22', 'PUMP_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '8', 'FAN_TACH'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '23', 'PUMP_TACH'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '17', '10k', '+3V3'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '22', '10k', '+3V3'),
    # ECS-2520MV (ECS datasheet): 1 tri-state (high = enabled), 2 GND, 3 OUT, 4 VDD
    ('net', 'ECS-2520MV-160-BN-TR', '4', '+3V3_SG'),
    ('net', 'ECS-2520MV-160-BN-TR', '1', '+3V3_SG'),
    ('net', 'ECS-2520MV-160-BN-TR', '2', 'GND'),
    # AD9837 (ADI rev A): 16 MHz MCLK max (B grade), so the 16 MHz oscillator
    ('join', 'ECS-2520MV-160-BN-TR', '3', 'AD9837BCPZ', '5'),
    # LT3097: both regulators from the ADP5071 rails, enables tied to their
    # inputs, VOUT = 100 uA x RSET (147k = 14.7 V, the +15 V side is limited
    # to 15 V), pad 23 = GND and pad 24 = INN, ILIM pins grounded
    ('net', 'LT3097ADJC', '1', '+16V5'),
    ('net', 'LT3097ADJC', '2', '+16V5'),
    ('same', 'LT3097ADJC', '3', '1'),
    ('net', 'LT3097ADJC', '6', '-16V5'),
    ('net', 'LT3097ADJC', '7', '-16V5'),
    ('net', 'LT3097ADJC', '24', '-16V5'),
    ('same', 'LT3097ADJC', '8', '6'),
    ('net', 'LT3097ADJC', '21', '+15V'),
    ('net', 'LT3097ADJC', '22', '+15V'),
    ('same', 'LT3097ADJC', '20', '21'),
    ('net', 'LT3097ADJC', '15', '-15V'),
    ('net', 'LT3097ADJC', '16', '-15V'),
    ('same', 'LT3097ADJC', '14', '15'),
    ('net', 'LT3097ADJC', '13', 'GND'),
    ('net', 'LT3097ADJC', '19', 'GND'),
    ('net', 'LT3097ADJC', '23', 'GND'),
    ('net', 'LT3097ADJC', '5', 'GND'),
    ('net', 'LT3097ADJC', '11', 'GND'),
    ('res', 'LT3097ADJC', '18', '147k', 'GND'),
    ('res', 'LT3097ADJC', '12', '147k', 'GND'),
    # power-good thresholds: 0.3 V x (1 + 432k / 10k) = 13.3 V
    ('res', 'LT3097ADJC', '17', '432k', '+15V'),
    ('res', 'LT3097ADJC', '17', '10k', 'GND'),
    ('res', 'LT3097ADJC', '10', '432k', '-15V'),
    ('res', 'LT3097ADJC', '10', '10k', 'GND'),
    # PGP and PGN each pull their own node low; each node is fed from +15 V so
    # it reads 0 V when its rail is missing (the two are ANDed into PG_15V)
    ('net', 'LT3097ADJC', '4', 'PGP_15V'),
    ('net', 'LT3097ADJC', '9', 'PGN_15V'),
    ('res', 'LT3097ADJC', '4', '220k', '+15V'),
    ('res', 'LT3097ADJC', '4', '62k', 'GND'),
    ('res', 'LT3097ADJC', '9', '220k', '+15V'),
    ('res', 'LT3097ADJC', '9', '62k', 'GND'),
    # ADP5071 LFCSP (datasheet pin table, Fig. 47, Tables 9-11): inputs and enables
    # on 5 V, SEQ on VREG starts both channels together, SYNC/FREQ low = 1.2 MHz,
    # SLEW on AGND = slowest edges, SS open
    ('net', 'ADP5071ACPZ', '15', '+5V_PS15'),
    ('net', 'ADP5071ACPZ', '17', '+5V_PS15'),
    ('net', 'ADP5071ACPZ', '16', '+5V_PS15'),
    ('net', 'ADP5071ACPZ', '7', '+5V_PS15'),
    ('net', 'ADP5071ACPZ', '9', '+5V_PS15'),
    ('net', 'ADP5071ACPZ', '13', 'GND'),
    ('net', 'ADP5071ACPZ', '19', 'GND'),
    ('net', 'ADP5071ACPZ', '21', 'GND'),
    ('net', 'ADP5071ACPZ', '2', 'GND'),
    ('net', 'ADP5071ACPZ', '4', 'GND'),
    ('same', 'ADP5071ACPZ', '3', '14'),
    ('nc', 'ADP5071ACPZ', '8'),
    ('between', '1uF', ('ADP5071ACPZ', '14'), ('NET', 'GND')),
    ('between', '1uF', ('ADP5071ACPZ', '12'), ('NET', 'GND')),
    # boost: INBK -> L -> SW1 -> diode -> +16.4 V, VFB1 0.8 V x (1 + 2.67M / 137k)
    ('between', 'SRP7050TA-3R3M', ('ADP5071ACPZ', '1'), ('ADP5071ACPZ', '20')),
    ('between', 'DFLS240', ('ADP5071ACPZ', '20'), ('NET', '+16V5')),
    ('res', 'ADP5071ACPZ', '5', '2.67M', '+16V5'),
    ('res', 'ADP5071ACPZ', '5', '137k', 'GND'),
    # inverting: SW2 -> L -> GND, SW2 -> diode -> -16.5 V, FB2 between rail and VREF
    ('between', 'SRP7050TA-6R8M', ('ADP5071ACPZ', '18'), ('NET', 'GND')),
    ('between', 'DFLS240', ('ADP5071ACPZ', '18'), ('NET', '-16V5')),
    ('res', 'ADP5071ACPZ', '11', '2.55M', '-16V5'),
    ('resjoin', 'ADP5071ACPZ', '11', '118k', 'ADP5071ACPZ', '12'),
    # the boost diode conducts into +16V5, the inverting diode out of -16V5
    ('net', 'DFLS240', '1', ('+16V5', 'Net-(D5-K)')),
    ('net', 'DFLS240', '2', ('Net-(D4-A)', '-16V5')),
    # J14: off-board Adafruit LSM6DSOX module, wired by the J14 table in
    # kicad/README.md (the pins don't follow its pad order); its 3Vo pad is not
    # wired. Vin = 3.3 V keeps the module's logic at 3.3 V. Each signal passes a
    # NUF6401MN channel (100 R series) next to the connector; the decoder holds CS high
    # with the cable unplugged, and the ESD clamps sit on the jack side.
    # J14 is a Molex Micro-Lock Plus 2x4 (505448-0891, drawing 5054480003-SD),
    # same pin numbers as the RJ45 it replaced; its two nails are unconnected
    ('net', '505448-0891', '4', '+3V3'),
    ('net', '505448-0891', '2', 'GND'),
    # NUF6401MN (onsemi NUF6401/D rev 5): channels 1-12, 2-11, 3-10, 4-9, 5-8, 6-7,
    # ground pad 13
    ('channel', 'NUF6401MNT1G', ('NET', 'SPI_SCK'), ('505448-0891', '1')),
    ('channel', 'NUF6401MNT1G', ('NET', 'SPI_MOSI'), ('505448-0891', '3')),
    ('channel', 'NUF6401MNT1G', ('NET', 'SPI_MISO'), ('505448-0891', '6')),
    ('channel', 'NUF6401MNT1G', ('NET', 'IMU_CS'), ('505448-0891', '5')),
    ('channel', 'NUF6401MNT1G', ('NET', 'IMU_INT1'), ('505448-0891', '7')),
    ('channel', 'NUF6401MNT1G', ('NET', 'IMU_INT2'), ('505448-0891', '8')),
    ('net', 'NUF6401MNT1G', '13', ('GND',)),
    # SRL05P7 (MCC rev 3-5): GND 2, VBUS 5; 1-6 and 3-4 are joined inside, so each
    # data line passes through it (connector on 1/3, ESP32 on 6/4)
    ('net', 'SRL05P7', '2', 'GND'),
    ('net', 'SRL05P7', '5', 'USB_VBUS'),
    ('join', 'SRL05P7', '1', 'USB_C', 'A6'),
    ('join', 'SRL05P7', '3', 'USB_C', 'A7'),
    ('join', 'SRL05P7', '6', 'ESP32-S3-WROOM-2-N32R16V', '14'),
    ('join', 'SRL05P7', '4', 'ESP32-S3-WROOM-2-N32R16V', '13'),
    # SP3422-04UTG (Littelfuse rev GD): IO 1, 3, 4, 5; GND 2. Channels: GPIO side of
    # the 4.7k tach resistors (U33), connector side of J10 (U35)
    ('net', 'SP3422-04UTG', '2', ('GND',)),
    ('net', 'SP3422-04UTG', '1', ('FAN_TACH', 'RTD_1')),
    ('net', 'SP3422-04UTG', '3', ('PUMP_TACH', 'RTD_2')),
    ('net', 'SP3422-04UTG', '4', ('FLOW_TACH', 'RTD_3')),
    ('net', 'SP3422-04UTG', '5', ('NTC_ADC', 'RTD_4')),
    ('net', 'RTD PT1000 4-wire', '1', 'RTD_1'),
    ('net', 'RTD PT1000 4-wire', '2', 'RTD_2'),
    ('net', 'RTD PT1000 4-wire', '3', 'RTD_3'),
    ('net', 'RTD PT1000 4-wire', '4', 'RTD_4'),
    # TPD1E05U06 (TI SLVSBO5): panel button line, 1 IO, 2 GND
    ('net', 'TPD1E05U06DPYR', '2', 'GND'),
    ('join', 'TPD1E05U06DPYR', '1', 'LTC2954CDDB-2', '3'),
    # supply jumpers: pin 1 on the main rail, pin 2 on the switched rail
    ('net', 'EN SG3', '1', '+3V3'),
    ('net', 'EN SG3', '2', '+3V3_SG'),
    ('net', 'EN PS15', '1', '+5V'),
    ('net', 'EN PS15', '2', '+5V_PS15'),
    ('net', 'EN ISO5', '1', '+5V_OR'),
    ('net', 'EN ISO5', '2', '+5V_ISO'),
    ('net', 'EN COOL', '1', '+3V3'),
    ('net', 'EN COOL', '2', '+3V3_COOL'),
    # the cold head feed has a ferrite ahead of its jumper
    ('between', 'BLM18PG121SN1D', ('NET', '+3V3'), ('EN CH', '1')),
    ('net', 'EN CH', '2', '+3V3_CH'),
    # ISOW7741 (TI SLLSEZ3, DFM): VSEL on VISOOUT = 5 V, EN_IO2 on the isolated side,
    # beads from VISOOUT to VISOIN and GND2 to GISOIN, EN/FLT pulled up (fault use
    # needs at least 5 k), no F suffix = outputs default high when an input is lost
    ('net', 'ISOW7741DFMR', '1', '+3V3'),
    ('net', 'ISOW7741DFMR', '7', '+3V3'),
    ('net', 'ISOW7741DFMR', '9', '+5V_ISO'),
    ('net', 'ISOW7741DFMR', '6', 'GND'),
    ('net', 'ISOW7741DFMR', '10', 'GND'),
    ('res', 'ISOW7741DFMR', '8', '10k', '+3V3'),
    ('net', 'ISOW7741DFMR', '12', 'VISOOUT'),
    ('net', 'ISOW7741DFMR', '13', 'VISOOUT'),
    ('net', 'ISOW7741DFMR', '20', 'ISO_5V'),
    ('net', 'ISOW7741DFMR', '14', 'ISO_5V'),
    ('net', 'ISOW7741DFMR', '15', 'ISO_GND'),
    ('net', 'ISOW7741DFMR', '11', 'ISO_GND2'),
    ('between', 'BLM15EX331SN1D', ('NET', 'VISOOUT'), ('NET', 'ISO_5V')),
    ('between', 'BLM15EX331SN1D', ('NET', 'ISO_GND'), ('NET', 'ISO_GND2')),
    ('net', 'ISOW7741DFMR', '2', 'ACS_MOSI'),
    ('net', 'ISOW7741DFMR', '3', 'ACS_SCK'),
    ('net', 'ISOW7741DFMR', '4', 'ACS_CS'),
    ('net', 'ISOW7741DFMR', '5', 'ACS_MISO'),
    # ACS37800 on the isolated 5 V domain
    ('net', 'ACS37800KMACTR-015B5-SPI', '13', 'ISO_5V'),
    ('net', 'ACS37800KMACTR-015B5-SPI', '14', 'ISO_GND'),
    ('net', 'ACS37800KMACTR-015B5-SPI', '15', 'ISO_GND'),
    # isolated SPI: OUTA/OUTB/OUTC carry MOSI/SCK/CS forward, IND returns MISO
    ('join', 'ISOW7741DFMR', '19', 'ACS37800KMACTR-015B5-SPI', '10'),
    ('join', 'ISOW7741DFMR', '18', 'ACS37800KMACTR-015B5-SPI', '11'),
    ('join', 'ISOW7741DFMR', '17', 'ACS37800KMACTR-015B5-SPI', '9'),
    ('join', 'ISOW7741DFMR', '16', 'ACS37800KMACTR-015B5-SPI', '12'),
    # AD5453 (ADI, CP-8-3): 1 IOUT1, 2 GND, 3 SCLK, 4 SDIN, 5 SYNC, 6 VDD, 7 VREF,
    # 8 RFB, 9 exposed pad. U5B (OPA2991) is its output stage; VREF is clamped because
    # the datasheet limits it to +/-12 V while U5A swings further
    ('net', 'AD5453WBCPZ-RL', '6', '+3V3_SG'),
    ('net', 'AD5453WBCPZ-RL', '2', 'GND'),
    ('net', 'AD5453WBCPZ-RL', '9', 'GND'),
    ('net', 'AD5453WBCPZ-RL', '3', 'SPI_SCK'),
    ('net', 'AD5453WBCPZ-RL', '4', 'SPI_MOSI'),
    ('net', 'AD5453WBCPZ-RL', '5', 'AD5453_SYNC'),
    ('join', 'AD5453WBCPZ-RL', '1', 'OPA2991IDSGR', '6'),
    # RFB reaches the output through the 0 ohm gain trim land (Figure 44, R2)
    ('between', '0', ('AD5453WBCPZ-RL', '8'), ('OPA2991IDSGR', '7')),
    ('between', '22pF/C0G', ('AD5453WBCPZ-RL', '1'), ('OPA2991IDSGR', '7')),
    ('net', 'OPA2991IDSGR', '5', 'GND'),
    ('between', '220', ('OPA2991IDSGR', '1'), ('AD5453WBCPZ-RL', '7')),
    # MMBZ9V1ALT1G (onsemi MMBZ5V6ALT1 family): 1 and 2 cathodes, 3 common anode.
    # Used between the cathodes, so the two zeners clamp both polarities
    ('join', 'MMBZ9V1ALT1G', '1', 'AD5453WBCPZ-RL', '7'),
    ('net', 'MMBZ9V1ALT1G', '2', 'GND'),
    ('nc', 'MMBZ9V1ALT1G', '3'),
    # OPA2991 DSG (TI SBOS969): A 1 OUT, 2 -IN, 3 +IN; B 5 +IN, 6 -IN, 7 OUT; 4 V-,
    # 8 V+, thermal pad 9 to V-
    ('net', 'OPA2991IDSGR', '8', '+15V'),
    ('net', 'OPA2991IDSGR', '4', '-15V'),
    ('net', 'OPA2991IDSGR', '9', '-15V'),
    # INA239 (SPI, SLYS027A): VS 3.3 V, VBUS on the +12V side, 49.9 ohm /
    # 470 nF input filter on IN+/IN-, ALERT open-drain pulled up and read by the
    # expander, CS idles high
    ('net', 'INA239AIDGSR', '6', '+3V3'),
    ('net', 'INA239AIDGSR', '7', 'GND'),
    # VBUS shares the filtered IN- node (adjacent pins, 0.6 mV drop)
    ('join', 'INA239AIDGSR', '8', 'INA239AIDGSR', '9'),
    ('between', '49.9', ('INA239AIDGSR', '10'), ('NET', 'VSW')),
    ('between', '49.9', ('INA239AIDGSR', '9'), ('NET', '+12V')),
    ('between', '470nF', ('INA239AIDGSR', '10'), ('INA239AIDGSR', '9')),
    ('net', 'INA239AIDGSR', '1', 'INA239_CS'),
    ('net', 'INA239AIDGSR', '2', 'SPI_MOSI'),
    ('net', 'INA239AIDGSR', '4', 'SPI_MISO'),
    ('net', 'INA239AIDGSR', '5', 'SPI_SCK'),
    ('res', 'INA239AIDGSR', '3', '10k', '+3V3'),
    ('net', 'INA239AIDGSR', '3', 'INA239_ALERT'),
    # ADS1220 (SPI, SBAS501D, RVA pins): AVDD/DVDD 3.3 V, AVSS/DGND/REFN0 on GND,
    # internal oscillator (CLK to GND), AIN2 unused, decoder drives CS push-pull,
    # 1k limits the IDAC line if the cable shorts
    ('net', 'ADS1220IRVAR', '10', '+3V3_CH'),
    ('net', 'ADS1220IRVAR', '11', '+3V3_CH'),
    ('net', 'ADS1220IRVAR', '3', 'GND'),
    ('net', 'ADS1220IRVAR', '2', 'GND'),
    ('net', 'ADS1220IRVAR', '6', 'GND'),
    ('net', 'ADS1220IRVAR', '1', 'GND'),
    ('net', 'ADS1220IRVAR', '17', 'GND'),
    ('nc', 'ADS1220IRVAR', '5'),
    ('net', 'ADS1220IRVAR', '16', 'ADS1220_CS'),
    ('net', 'ADS1220IRVAR', '15', 'SPI_SCK'),
    ('net', 'ADS1220IRVAR', '14', 'SPI_MOSI'),
    ('net', 'ADS1220IRVAR', '13', 'SPI_MISO'),
    ('between', '1k', ('ADS1220IRVAR', '4'), ('NET', 'RTD_1')),
    ('net', 'ADS1220IRVAR', '7', 'RTD_4'),
    ('res', 'ADS1220IRVAR', '7', '3.9k', 'GND'),
    # MCP23S08 (Microchip DS20001919F, QFN-20): supply on the unswitched rail,
    # exposed pad and VSS on GND, RESET and address pins biased (Table 1-1),
    # SO on the shared MISO, power-good, alert and touch flags in, backlight out
    ('net', 'MCP23S08-E/ML', '18', '+3V3'),
    ('net', 'MCP23S08-E/ML', '17', 'GND'),
    ('net', 'MCP23S08-E/ML', '21', 'GND'),
    ('net', 'MCP23S08-E/ML', '2', 'GND'),
    ('net', 'MCP23S08-E/ML', '3', 'GND'),
    ('net', 'MCP23S08-E/ML', '1', 'SPI_MISO'),
    ('net', 'MCP23S08-E/ML', '19', 'SPI_SCK'),
    ('net', 'MCP23S08-E/ML', '20', 'SPI_MOSI'),
    ('net', 'MCP23S08-E/ML', '5', 'EXPANDER_CS'),
    ('net', 'MCP23S08-E/ML', '4', '+3V3'),
    ('net', 'MCP23S08-E/ML', '9', 'PGP_15V'),
    ('net', 'MCP23S08-E/ML', '10', 'PGN_15V'),
    ('net', 'MCP23S08-E/ML', '13', 'DISP_BL_EN'),
    ('net', 'MCP23S08-E/ML', '15', 'INA239_ALERT'),
    ('net', 'MCP23S08-E/ML', '16', 'TOUCH_IRQ'),
    ('nc', 'MCP23S08-E/ML', '11'),
    ('nc', 'MCP23S08-E/ML', '12'),
    ('nc', 'MCP23S08-E/ML', '14'),
    # -15 V guard: an unpowered LT3097 cannot pull PGN low, so the midpoint of two
    # 470k between the rails turns this FET on when -15 V is missing
    ('net', 'BSS138W', '3', 'PGN_15V'),
    ('net', 'BSS138W', '2', 'GND'),
    ('between', '470k', ('NET', '+15V'), ('BSS138W', '1')),
    ('between', '470k', ('NET', '-15V'), ('BSS138W', '1')),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '12', 'CS_EN_N'),
    # compressor relay driver (same stage as the amplifier REM switch)
    ('net', 'BSS138', '2', 'GND'),
    ('net', 'BSS84', '2', '+12V'),
    ('between', '1N4148W', ('NET', 'COMP_RELAY'), ('NET', 'GND')),
    # AP63205 5 V buck (datasheet Fig. 1 / Table 3): 1 FB, 2 EN, 3 VIN, 4 GND,
    # 5 SW, 6 BST
    ('net', 'AP63205WU-7', '3', '+12V'),
    ('net', 'AP63205WU-7', '2', '+12V'),
    ('net', 'AP63205WU-7', '4', 'GND'),
    ('net', 'AP63205WU-7', '1', '+5V'),
    ('between', 'SRP4020TA-4R7M', ('AP63205WU-7', '5'), ('NET', '+5V')),
    ('between', '100nF', ('AP63205WU-7', '6'), ('AP63205WU-7', '5')),
    # TPS62822 (SLUSCY3, DLC): 1 EN, 2 FB, 3 AGND, 4 NC, 5 PGND, 6 SW, 7 VIN, 8 PG.
    # 0.6 V x (1 + 453k / 100k) = 3.32 V, feed-forward 120 pF
    ('net', 'TPS62822DLCR', '7', '+5V_OR'),
    ('net', 'TPS62822DLCR', '1', '+5V_OR'),
    ('net', 'TPS62822DLCR', '3', 'GND'),
    ('net', 'TPS62822DLCR', '5', 'GND'),
    ('nc', 'TPS62822DLCR', '4'),
    ('nc', 'TPS62822DLCR', '8'),
    ('between', 'SRP4020TA-R47M', ('TPS62822DLCR', '6'), ('NET', '+3V3')),
    ('res', 'TPS62822DLCR', '2', '453k', '+3V3'),
    ('res', 'TPS62822DLCR', '2', '100k', 'GND'),
    ('between', '120pF', ('TPS62822DLCR', '2'), ('NET', '+3V3')),
    # TPS2116 (SLVSEH8 7.6.1, DRL): 1 GND, 2 and 7 VOUT, 3 VIN1, 4 PR1, 5 MODE, 6 VIN2,
    # 8 ST. MODE on VIN1 selects priority; 33k / 10k from VIN1 sets about 4.3 V
    ('net', 'TPS2116DRLR', '3', '+5V'),
    ('net', 'TPS2116DRLR', '5', '+5V'),
    ('net', 'TPS2116DRLR', '6', 'USB_VBUS'),
    ('net', 'TPS2116DRLR', '2', '+5V_OR'),
    ('net', 'TPS2116DRLR', '7', '+5V_OR'),
    ('net', 'TPS2116DRLR', '1', 'GND'),
    ('nc', 'TPS2116DRLR', '8'),
    ('res', 'TPS2116DRLR', '4', '33k', '+5V'),
    ('res', 'TPS2116DRLR', '4', '10k', 'GND'),
    ('net', 'AD9837BCPZ', '2', '+3V3_SG'),
    ('net', 'AD9837BCPZ', '4', 'GND'),
    ('net', 'AD9837BCPZ', '9', 'GND'),
    ('net', 'AD9837BCPZ', '11', 'GND'),  # exposed pad to ground (Figure 4)
    # Power path. AONR21307 (AOS): 1-3 S, 4 G, 5-8 D. EN# reaches the gate through
    # 10k; 47 nF gate-drain slows the ramp; 470 nF gate-source holds Vgs under the
    # threshold on a hot plug; the 15 V zener caps Vgs for input transients
    ('net', 'AONR21307', '1', 'VIN'),
    ('net', 'AONR21307', '5', 'VSW'),
    ('between', '10k', ('LTC2954CDDB-2', '7'), ('AONR21307', '4')),
    ('between', 'BZT52C15', ('NET', 'VIN'), ('AONR21307', '4')),
    ('net', 'BZT52C15', '1', 'VIN'),
    ('between', '470nF', ('NET', 'VIN'), ('AONR21307', '4')),
    ('between', '47nF', ('AONR21307', '4'), ('NET', 'VSW')),
    ('res', 'AONR21307', '4', '100k', 'VIN'),
    # LTC2954-2 (DDB): 1 GND, 2 ONT, 3 PB, 4 VIN, 5 KILL, 6 PDT, 7 EN, 8 INT, 9 pad.
    # 1 uF on PDT gives about 6.4 s for firmware to shut down
    ('net', 'LTC2954CDDB-2', '4', 'VIN'),
    ('net', 'LTC2954CDDB-2', '1', 'GND'),
    ('net', 'LTC2954CDDB-2', '9', 'GND'),
    ('nc', 'LTC2954CDDB-2', '2'),
    ('net', 'LTC2954CDDB-2', '8', 'PWR_INT'),
    ('res', 'LTC2954CDDB-2', '8', '10k', '+3V3'),
    ('between', '1uF', ('LTC2954CDDB-2', '6'), ('NET', 'GND')),
    ('resjoin', 'LTC2954CDDB-2', '5', '220k', 'LM4040DBZ-5', '1'),
    ('net', 'LM4040DBZ-5', '2', 'GND'),
    ('resjoin', 'LM4040DBZ-5', '1', '82k', 'LTC2954CDDB-2', '4'),
    # status LED (Kingbright APGB0607G22R23C rev V.3A: 1 GA, 2 GK, 3 RK, 4 RA): red
    # 13k from VIN, shorted by a BSS138 once +3V3 is up; green 2.2k from +5V
    ('between', '13k', ('NET', 'VIN'), ('STATUS G=on R=standby', '4')),
    ('net', 'STATUS G=on R=standby', '3', 'GND'),
    ('net', 'STATUS G=on R=standby', '2', 'GND'),
    ('res', 'STATUS G=on R=standby', '1', '2.2k', '+5V'),
    # switch state LEDs: dies anti-parallel between the bus and 2.2k to +5V, so
    # each die's reverse voltage is the other's VF (< 5 V VR)
    ('net', 'AMP_REM G=on R=off', '1', 'AMP_REM'),
    ('net', 'AMP_REM G=on R=off', '3', 'AMP_REM'),
    ('res', 'AMP_REM G=on R=off', '2', '2.2k', '+5V'),
    ('res', 'AMP_REM G=on R=off', '4', '2.2k', '+5V'),
    ('net', 'COMP_RELAY G=on R=off', '1', 'COMP_RELAY'),
    ('net', 'COMP_RELAY G=on R=off', '3', 'COMP_RELAY'),
    ('res', 'COMP_RELAY G=on R=off', '2', '2.2k', '+5V'),
    ('res', 'COMP_RELAY G=on R=off', '4', '2.2k', '+5V'),
    # power good LEDs: green 2.2k from +5V (VF up to 3.3 V), red 1.5k from +3V3
    ('res', 'PG +15V G=good R=bad', '1', '2.2k', '+5V'),
    ('res', 'PG +15V G=good R=bad', '4', '1.5k', '+3V3'),
    ('res', 'PG -15V G=good R=bad', '1', '2.2k', '+5V'),
    ('res', 'PG -15V G=good R=bad', '4', '1.5k', '+3V3'),
    # single-die indicators
    ('net', 'ALERT (red)', '3', 'INA239_ALERT'),
    ('res', 'ALERT (red)', '4', '1.5k', '+3V3'),
    ('res', 'ISO 5V (green)', '1', '3.3k', 'ISO_5V'),
    ('net', 'ISO 5V (green)', '2', 'ISO_GND'),
    # 74AHCT1G125GM (Nexperia rev 15.1, SOT886): 1 OE, 2 A, 3 GND, 4 Y, 5 n.c., 6 VCC
    ('net', '74AHCT1G125GM', '6', '+5V'),
    ('net', '74AHCT1G125GM', '1', 'GND'),
    ('net', '74AHCT1G125GM', '3', 'GND'),
    ('net', '74AHCT1G125GM', '2', 'STATUS_RGB'),
    ('nc', '74AHCT1G125GM', '5'),
    # ESP32-S3-WROOM-2: pins 28-30 are NC on this module, IO47/48 are 1.8 V
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '28'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '29'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '30'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '24'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '25', 'DISP_DC_1V8'),
    # SN74LVC138A (TI SCAS291, RGY): 1 A, 2 B, 3 C, 4 G2A, 5 G2B, 6 G1, 7 Y7, 8 GND,
    # 9-15 Y6-Y0, 16 VCC, 17 exposed pad. The enable pull-up holds all outputs high at reset;
    # GPIO3 and GPIO45 keep their strap resistors, now on the address lines
    ('net', 'SN74LVC138ARGYR', '16', '+3V3'),
    ('net', 'SN74LVC138ARGYR', '8', 'GND'),
    ('net', 'SN74LVC138ARGYR', '17', 'GND'),
    ('net', 'SN74LVC138ARGYR', '6', '+3V3'),
    ('net', 'SN74LVC138ARGYR', '5', 'GND'),
    ('net', 'SN74LVC138ARGYR', '1', 'CS_ADDR_A'),
    ('net', 'SN74LVC138ARGYR', '2', 'CS_ADDR_B'),
    ('net', 'SN74LVC138ARGYR', '3', 'CS_ADDR_C'),
    ('net', 'SN74LVC138ARGYR', '4', 'CS_EN_N'),
    ('res', 'SN74LVC138ARGYR', '4', '10k', '+3V3'),
    ('res', 'SN74LVC138ARGYR', '1', '10k', '+3V3'),
    ('res', 'SN74LVC138ARGYR', '3', '10k', 'GND'),
    ('net', 'SN74LVC138ARGYR', '15', 'AD9833_FSYNC'),
    ('net', 'SN74LVC138ARGYR', '14', 'AD5453_SYNC'),
    ('net', 'SN74LVC138ARGYR', '13', 'INA239_CS'),
    ('net', 'SN74LVC138ARGYR', '12', 'EXPANDER_CS'),
    ('net', 'SN74LVC138ARGYR', '11', 'DISP_CS'),
    ('net', 'SN74LVC138ARGYR', '10', 'TOUCH_CS'),
    ('net', 'SN74LVC138ARGYR', '9', 'ADS1220_CS'),
    ('net', 'SN74LVC138ARGYR', '7', 'IMU_CS'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '15', 'CS_ADDR_A'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '36', 'CS_ADDR_B'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '26', 'CS_ADDR_C'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '39', 'PWR_INT'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '5'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '7'),
    # 74LV1T34GX (Nexperia rev 4, X2SON5): 1 n.c. (grounded for the footprint
    # bridge), 2 A, 3 GND, 4 Y, 5 VCC; VIH 1.37 V at VCC 3.0-3.3 V
    ('net', '74LV1T34GX', '5', '+3V3'),
    ('net', '74LV1T34GX', '3', 'GND'),
    ('net', '74LV1T34GX', '1', 'GND'),
    ('net', '74LV1T34GX', '2', 'DISP_DC_1V8'),
    ('net', '74LV1T34GX', '4', 'DISP_DC'),
    # ACS_CS is on GPIO17 (module pin 10), not GPIO43 / U0TXD (pin 37), which
    # toggles with ROM boot messages; it carries the power-good flag (active
    # low) behind a 1k series resistor
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '37', 'PG_15V_N'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '10', 'ACS_CS'),
    # TE 1571300-2 power button (drawing C-1571300): contact from LTC2954 PB to GND
    ('join', 'POWER', '1', 'LTC2954CDDB-2', '3'),
    ('net', 'POWER', '2', 'GND'),
    # WS2812B-2020 status LED (WorldSemi V1.3 p.2): 1 DO, 2 GND, 3 DI, 4 VDD; DO unused
    ('net', 'WS2812B-2020', '2', 'GND'),
    ('net', 'WS2812B-2020', '4', '+5V'),
    ('between', '330', ('74AHCT1G125GM', '4'), ('WS2812B-2020', '3')),
    # EVP-AA802Q reset and boot buttons (Panasonic ANCTB18E No. 1): contact from the
    # strap net to GND. Pads 1-1' (top row) and 2-2' (bottom row) are common.
    ('net', 'RESET', '1', 'ESP_EN'),
    ('net', 'RESET', '2', 'GND'),
    ('net', 'BOOT', '1', 'ESP_BOOT'),
    ('net', 'BOOT', '2', 'GND'),
    # Phoenix 2.4" display FPC (datasheet 109921 p.7) and TSC2046E (TI SBAS417, QFN pins)
    ('net', 'FH12-14S-0.5SH(55)', '5', 'GND'),
    ('net', 'FH12-14S-0.5SH(55)', '6', '+3V3'),
    ('net', 'FH12-14S-0.5SH(55)', '7', 'DISP_CS'),
    ('net', 'FH12-14S-0.5SH(55)', '8', 'DISP_RST'),
    ('net', 'FH12-14S-0.5SH(55)', '9', 'DISP_DC'),
    ('net', 'FH12-14S-0.5SH(55)', '10', 'SPI_SCK'),
    ('net', 'FH12-14S-0.5SH(55)', '11', 'SPI_MOSI'),
    ('nc', 'FH12-14S-0.5SH(55)', '12'),
    ('res', 'FH12-14S-0.5SH(55)', '13', '39', '+5V_OR'),
    ('join', 'FH12-14S-0.5SH(55)', '4', 'TSC2046EIRGVT', '6'),
    ('join', 'FH12-14S-0.5SH(55)', '1', 'TSC2046EIRGVT', '7'),
    ('join', 'FH12-14S-0.5SH(55)', '2', 'TSC2046EIRGVT', '8'),
    ('join', 'FH12-14S-0.5SH(55)', '3', 'TSC2046EIRGVT', '9'),
    ('net', 'TSC2046EIRGVT', '5', '+3V3'),
    ('net', 'TSC2046EIRGVT', '14', '+3V3'),
    ('net', 'TSC2046EIRGVT', '10', 'GND'),
    ('net', 'TSC2046EIRGVT', '17', 'GND'),
    ('net', 'TSC2046EIRGVT', '4', 'SPI_SCK'),
    ('net', 'TSC2046EIRGVT', '2', 'SPI_MOSI'),
    ('net', 'TSC2046EIRGVT', '16', 'SPI_MISO'),
    ('net', 'TSC2046EIRGVT', '3', 'TOUCH_CS'),
    ('nc', 'TSC2046EIRGVT', '13'),
    ('net', 'TSC2046EIRGVT', '15', 'TOUCH_IRQ'),
    # J12 pin 3 (cryocooler protective ground) on board GND; J11 / J12 minus
    # on the isolated side
    ('net', 'CRYOCOOLER (+ / - / GND)', '3', 'GND'),
    ('net', 'CRYOCOOLER (+ / - / GND)', '2', 'ISO_GND'),
    ('net', 'AMP OUT (+ / -)', '2', 'ISO_GND'),
]


# IMU board (imu/): LSM6DSOX DS12814 rev 3 (Table 1 pin description, Section 7
# application hints, Table 20 internal pin status) and the J14 cable map
RULES_IMU = [
    # Mode 1: SDx / SCx to VDDIO or GND, OCS_Aux unconnected, SDO_Aux to VDDIO
    # or unconnected
    ('net', 'LSM6DSOXTR', '2', 'GND'),
    ('net', 'LSM6DSOXTR', '3', 'GND'),
    ('nc', 'LSM6DSOXTR', '10'),
    ('nc', 'LSM6DSOXTR', '11'),
    ('net', 'LSM6DSOXTR', '6', 'GND'),
    ('net', 'LSM6DSOXTR', '7', 'GND'),
    ('net', 'LSM6DSOXTR', '8', '+3V3'),
    ('net', 'LSM6DSOXTR', '5', '+3V3'),
    # "Recommended 100 nF filter capacitor" on VDD and on VDDIO
    ('caps', '+3V3', '100nF', 2, 'GND'),
    # 4-wire SPI: CS 12, SPC 13, SDI 14, SDO 1; CS idles high
    ('net', 'LSM6DSOXTR', '12', 'IMU_CS'),
    ('net', 'LSM6DSOXTR', '13', 'SPI_SCK'),
    ('net', 'LSM6DSOXTR', '14', 'SPI_MOSI'),
    ('net', 'LSM6DSOXTR', '1', 'SPI_MISO'),
    ('res', 'LSM6DSOXTR', '12', '10k', '+3V3'),
    ('net', 'LSM6DSOXTR', '4', 'IMU_INT1'),
    ('net', 'LSM6DSOXTR', '9', 'IMU_INT2'),
    # INT1 must be low or open at power-up when SPI is used (Table 20 note 2)
    ('nores', 'LSM6DSOXTR', '4', '+3V3'),
    # J1 carries the J14 pin map, so the cable is wired pin to pin
    ('net', '505448-0891', '1', 'SPI_SCK'),
    ('net', '505448-0891', '2', 'GND'),
    ('net', '505448-0891', '3', 'SPI_MOSI'),
    ('net', '505448-0891', '4', '+3V3'),
    ('net', '505448-0891', '5', 'IMU_CS'),
    ('net', '505448-0891', '6', 'SPI_MISO'),
    ('net', '505448-0891', '7', 'IMU_INT1'),
    ('net', '505448-0891', '8', 'IMU_INT2'),
]


def run(path, rules=RULES):
    comps, nets = load(path)
    value_of = {
        ref: sval(find_all(c, 'value')[0][1]) for ref, c in comps.items()
    }
    pin_net = {}
    members = {}
    for name, nodes in nets.items():
        short = name.split('/')[-1]
        members[short] = nodes
        for ref, pin, _ in nodes:
            pin_net[(ref, pin)] = short
    refs_by_value = {}
    for ref, value in value_of.items():
        refs_by_value.setdefault(value, []).append(ref)
    failures = 0

    def check(ok, text):
        nonlocal failures
        print(('ok    ' if ok else 'FAIL  ') + text)
        failures += 0 if ok else 1

    for rule in rules:
        kind, value = rule[0], rule[1]
        if kind == 'caps':
            net, cap_value, count, other = rule[1:]
            found = sum(
                1
                for ref, pin, _ in members.get(net, [])
                if ref.startswith('C') and value_of[ref] == cap_value
                and pin_net.get((ref, '2' if pin == '1' else '1')) == other
            )
            check(found >= count, f'{count} x {cap_value} between {net} and '
                  f'{other} (found {found})')
            continue
        refs = refs_by_value.get(value)
        if not refs:
            check(False, f'{value}: part not found')
            continue
        ref = refs[0]
        if kind == 'net' and isinstance(rule[3], tuple):
            # every part of this value must sit on one of the listed nets
            gots = [pin_net.get((r, rule[2])) for r in refs]
            check(
                all(got in rule[3] for got in gots),
                f'{value}.{rule[2]} on one of {rule[3]} (got {gots})',
            )
        elif kind == 'net':
            got = pin_net.get((ref, rule[2]))
            check(
                got == rule[3], f'{value}.{rule[2]} on {rule[3]} (got {got})'
            )
        elif kind == 'same':
            a, b = pin_net.get((ref, rule[2])), pin_net.get((ref, rule[3]))
            check(
                a is not None and a == b,
                f'{value} pins {rule[2]} and {rule[3]} share a net ({a}, {b})',
            )
        elif kind == 'nc':
            net = pin_net.get((ref, rule[2]), '')
            check(
                net == '' or net.startswith('unconnected'),
                f'{value}.{rule[2]} unconnected (got {net or "none"})',
            )
        elif kind == 'between':

            def target_net(target):
                if target[0] == 'NET':
                    return target[1]
                target_refs = refs_by_value.get(target[0], [])
                return (
                    pin_net.get((target_refs[0], target[1]))
                    if target_refs
                    else None
                )

            want = {target_net(rule[2]), target_net(rule[3])}
            found = False
            for part_ref in refs_by_value.get(value, []):
                got = {
                    pin_net.get((part_ref, '1')),
                    pin_net.get((part_ref, '2')),
                }
                found = found or got == want
            check(found, f'{value} between {rule[2]} and {rule[3]}')
            continue
        elif kind == 'channel':
            # a filter channel (pin k with pin 13 - k) joins the two targets

            def channel_net(target):
                if target[0] == 'NET':
                    return target[1]
                target_refs = refs_by_value.get(target[0], [])
                return pin_net.get((target_refs[0], target[1])) if target_refs else None

            want = {channel_net(rule[2]), channel_net(rule[3])}
            found = any(
                {pin_net.get((part_ref, near)), pin_net.get((part_ref, far))} == want
                for part_ref in refs
                for near, far in ((str(pin), str(13 - pin)) for pin in range(1, 7))
            )
            check(found, f'{value} channel joins {rule[2]} and {rule[3]}')
            continue
        elif kind == 'join':
            other = refs_by_value.get(rule[3])
            a = pin_net.get((ref, rule[2]))
            b = pin_net.get((other[0], rule[4])) if other else None
            check(
                a is not None and a == b,
                f'{value}.{rule[2]} joined with {rule[3]}.{rule[4]} ({a}, '
                f'{b})',
            )
        elif kind == 'resjoin':
            net = pin_net.get((ref, rule[2]))
            target_refs = refs_by_value.get(rule[4], [])
            target_net = (
                pin_net.get((target_refs[0], rule[5])) if target_refs else None
            )
            found = False
            for other_ref, other_pin, _ in members.get(net, []):
                if value_of[other_ref] != rule[3] or not other_ref.startswith(
                    'R'
                ):
                    continue
                far_pin = '2' if other_pin == '1' else '1'
                if pin_net.get((other_ref, far_pin)) == target_net:
                    found = True
            check(
                found,
                f'{value}.{rule[2]} has {rule[3]} to {rule[4]}.{rule[5]}',
            )
        elif kind == 'fetdrive':
            drain = pin_net.get((ref, rule[2]))
            found = False
            for fet in refs_by_value.get('BSS138', []):
                if (
                    pin_net.get((fet, '3')) != drain
                    or pin_net.get((fet, '2')) != 'GND'
                ):
                    continue
                for other_ref, other_pin, _ in members.get(
                    pin_net.get((fet, '1')), []
                ):
                    if value_of[other_ref] != rule[3] or not other_ref.startswith(
                        'R'
                    ):
                        continue
                    far_pin = '2' if other_pin == '1' else '1'
                    found = found or pin_net.get((other_ref, far_pin)) == rule[4]
            check(
                found,
                f'{value}.{rule[2]} driven by BSS138, gate {rule[3]} to '
                f'{rule[4]}',
            )
        elif kind == 'res':
            net = pin_net.get((ref, rule[2]))
            found = False
            for other_ref, other_pin, _ in members.get(net, []):
                if value_of[other_ref] != rule[3] or not other_ref.startswith(
                    'R'
                ):
                    continue
                far_pin = '2' if other_pin == '1' else '1'
                if pin_net.get((other_ref, far_pin)) == rule[4]:
                    found = True
            check(found, f'{value}.{rule[2]} has {rule[3]} to {rule[4]}')
        elif kind == 'nores':
            net = pin_net.get((ref, rule[2]))
            joined = [
                other_ref
                for other_ref, other_pin, _ in members.get(net, [])
                if other_ref.startswith('R') and pin_net.get(
                    (other_ref, '2' if other_pin == '1' else '1')) == rule[3]
            ]
            check(not joined, f'{value}.{rule[2]} has no resistor to '
                  f'{rule[3]} (found {joined or "none"})')
    print(f'{len(rules) - failures}/{len(rules)} datasheet rules pass')
    return failures


if __name__ == '__main__':
    if sys.argv[1] == '--imu':
        sys.exit(1 if run(sys.argv[2], RULES_IMU) else 0)
    sys.exit(1 if run(sys.argv[1]) else 0)
