"""Datasheet-derived connection rules, checked against an exported netlist.

Each rule encodes something verified in a manufacturer datasheet (see
../DESIGN_REVIEW.md).
Usage: python3 datasheet_rules.py netlist.net
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
RULES = [
    # 4-pin fans (Intel 4-wire spec): PWM open drain through a BSS138 with the
    # gate pulled to +3V3 (0% drive at reset), tach open collector with a
    # pull-up at the connector and 1k to the GPIO
    ('fetdrive', 'FAN (4-pin PWM)', '4', '1k', 'FAN_PWM'),
    ('res', 'FAN (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'FAN (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '1k', ('FAN (4-pin PWM)', '3'), ('NET', 'FAN_TACH')),
    ('net', 'FAN (4-pin PWM)', '2', '+12V'),
    ('net', 'FAN (4-pin PWM)', '1', 'GND'),
    ('fetdrive', 'PUMP (4-pin PWM)', '4', '1k', 'PUMP_PWM'),
    ('res', 'PUMP (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'PUMP (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '1k', ('PUMP (4-pin PWM)', '3'), ('NET', 'PUMP_TACH')),
    ('net', 'PUMP (4-pin PWM)', '2', '+12V'),
    ('net', 'PUMP (4-pin PWM)', '1', 'GND'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '17', 'FAN_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '22', 'PUMP_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '8', 'FAN_TACH'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '23', 'PUMP_TACH'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '17', '10k', '+3V3'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '22', '10k', '+3V3'),
    # MIE1W0505: VSEL to GND2 selects 3.3 V; EN must be driven high
    ('net', 'MIE1W0505BGLVH-3R-Z', '7', 'ISO_GND'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '5_6', 'ISO_3V3'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '9_10', '+5V_ISO'),
    ('res', 'MIE1W0505BGLVH-3R-Z', '8', '100k', '+5V_ISO'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '1', 'GND'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '11_12', 'GND'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '2', 'ISO_GND'),
    ('net', 'MIE1W0505BGLVH-3R-Z', '3_4', 'ISO_GND'),
    # CL25 (SOT-89 / TO-92): VA = 1 (supply side), VB = 2 (centre lead + tab),
    # NC = 3
    ('net', 'CL25N8-G', '1', 'VIN'),
    ('nc', 'CL25N8-G', '3'),
    # SG-8002CA-PH (5 V CMOS): 1 OE (high/open = enabled), 2 GND, 3 OUT, 4 VCC
    ('net', 'SG-8002CA-PH 25MHz', '4', '+5V_OR'),
    ('net', 'SG-8002CA-PH 25MHz', '2', 'GND'),
    ('net', 'SG-8002CA-PH 25MHz', '1', '+5V_OR'),
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
    # LT8582 (datasheet p.30 / p.32): VIN and SHDN on the 5 V input, SYNC1
    # grounded, CLKOUT1 -> SYNC2, RT 53.6k (1.5 MHz), master + slave switches
    # tied, RFBX = (VOUT - 1.204) / 83.3 uA and (|VOUT| + 7 mV) / 83.3 uA
    ('net', 'LT8582EDKD#PBF', '2', '+5V_PS15'),
    ('net', 'LT8582EDKD#PBF', '11', '+5V_PS15'),
    ('net', 'LT8582EDKD#PBF', '22', '+5V_PS15'),
    ('net', 'LT8582EDKD#PBF', '15', '+5V_PS15'),
    ('net', 'LT8582EDKD#PBF', '25', 'GND'),
    ('net', 'LT8582EDKD#PBF', '19', 'GND'),
    ('same', 'LT8582EDKD#PBF', '23', '18'),
    ('nc', 'LT8582EDKD#PBF', '14'),
    ('same', 'LT8582EDKD#PBF', '1', '24'),
    ('same', 'LT8582EDKD#PBF', '12', '13'),
    ('res', 'LT8582EDKD#PBF', '21', '53.6k', 'GND'),
    ('res', 'LT8582EDKD#PBF', '16', '53.6k', 'GND'),
    ('res', 'LT8582EDKD#PBF', '6', '182k', '+16V5'),
    ('res', 'LT8582EDKD#PBF', '7', '198k', '-16V5'),
    ('net', 'LT8582EDKD#PBF', '3', 'PGP_16V5'),
    ('net', 'LT8582EDKD#PBF', '10', 'PGN_16V5'),
    ('between', 'SRP7050TA-4R7M', ('NET', '+5V_PS15'), ('LT8582EDKD#PBF', '1')),
    # MSD7342: winding 1-3 (dot 1) from VIN to SW2, winding 2-4 (dot 2) from
    # node X to VOUT; C1 couples SW2 to node X
    ('net', 'MSD7342-103MLC', '1', '+5V_PS15'),
    ('join', 'MSD7342-103MLC', '3', 'LT8582EDKD#PBF', '12'),
    ('net', 'MSD7342-103MLC', '2', '-16V5'),
    ('between', '2.2uF/50V', ('LT8582EDKD#PBF', '12'), ('MSD7342-103MLC', '4')),
    # J14: off-board Adafruit LSM6DSOX module. Pins 1-8 follow the module's
    # pads (Vin, GND, SCL, SDA, DO, CS, INT1, INT2); its 3Vo pad is not
    # wired. Vin = 3.3 V keeps the module's logic at 3.3 V. Each signal has a
    # 100 R series resistor next to the connector; CS keeps a 10 k pull-up on
    # the board side so it idles high with the cable unplugged.
    # J14 is a plain shielded RJ45 (RJSSE-5380), T568B pairs 1-2 SCK/GND,
    # 3-6 MOSI/MISO, 4-5 +3V3/CS, 7-8 INT1/INT2; shield to GND
    ('net', 'RJSSE-5380', '4', '+3V3'),
    ('net', 'RJSSE-5380', '2', 'GND'),
    ('net', 'RJSSE-5380', 'SH', 'GND'),
    ('between', '100', ('NET', 'SPI_SCK'), ('RJSSE-5380', '1')),
    ('between', '100', ('NET', 'SPI_MOSI'), ('RJSSE-5380', '3')),
    ('between', '100', ('NET', 'SPI_MISO'), ('RJSSE-5380', '6')),
    ('between', '100', ('NET', 'IMU_CS'), ('RJSSE-5380', '5')),
    ('between', '100', ('NET', 'IMU_INT1'), ('RJSSE-5380', '7')),
    ('between', '100', ('NET', 'IMU_INT2'), ('RJSSE-5380', '8')),
    # supply jumpers: pin 1 on the main rail, pin 2 on the switched rail
    ('net', 'EN SG3', '1', '+3V3'),
    ('net', 'EN SG3', '2', '+3V3_SG'),
    ('net', 'EN PS15', '1', '+5V'),
    ('net', 'EN PS15', '2', '+5V_PS15'),
    ('net', 'EN ISO5', '1', '+5V_OR'),
    ('net', 'EN ISO5', '2', '+5V_ISO'),
    ('net', 'EN COOL', '1', '+3V3'),
    ('net', 'EN COOL', '2', '+3V3_COOL'),
    ('net', 'EN CH', '1', '+3V3'),
    ('net', 'EN CH', '2', '+3V3_CH'),
    ('res', 'SN74LVC138A', '7', '10k', '+3V3'),  # IMU_CS held high with the cable unplugged
    # ISO7741 input idle levels while the ESP32 GPIOs float (CS, SCLK, MOSI
    # pulled to 3V3)
    ('res', 'ISO7741DW', '5', '10k', '+3V3'),
    ('res', 'ISO7741DW', '4', '10k', '+3V3'),
    ('res', 'ISO7741DW', '3', '10k', '+3V3'),
    # ACS37800 + ISO7741 isolated domain
    ('net', 'ACS37800KMACTR-030B3-SPI', '13', 'ISO_3V3'),
    ('net', 'ACS37800KMACTR-030B3-SPI', '14', 'ISO_GND'),
    ('net', 'ACS37800KMACTR-030B3-SPI', '15', 'ISO_GND'),
    ('net', 'ISO7741DW', '1', '+3V3'),
    ('net', 'ISO7741DW', '7', '+3V3'),
    # isolated SPI: OUTA/OUTB/OUTC carry MOSI/SCK/CS forward, IND returns MISO
    ('join', 'ISO7741DW', '14', 'ACS37800KMACTR-030B3-SPI', '10'),
    ('join', 'ISO7741DW', '13', 'ACS37800KMACTR-030B3-SPI', '11'),
    ('join', 'ISO7741DW', '12', 'ACS37800KMACTR-030B3-SPI', '9'),
    ('join', 'ISO7741DW', '11', 'ACS37800KMACTR-030B3-SPI', '12'),
    ('net', 'ISO7741DW', '2', 'GND'),
    ('net', 'ISO7741DW', '16', 'ISO_3V3'),
    ('net', 'ISO7741DW', '10', 'ISO_3V3'),
    ('net', 'ISO7741DW', '9', 'ISO_GND'),
    # AD633JR (SOIC): 1 Y1, 2 Y2, 3 -VS, 4 Z, 5 W, 6 +VS, 7 X1, 8 X2
    ('net', 'AD633JRZ-R7', '6', '+15V'),
    ('net', 'AD633JRZ-R7', '3', '-15V'),
    ('net', 'AD633JRZ-R7', '2', 'GND'),
    ('net', 'AD633JRZ-R7', '4', 'GND'),
    ('net', 'AD633JRZ-R7', '8', 'GND'),
    # Op-amps and DAC
    ('net', 'OPA188AIDBVR', '5', '+15V'),
    ('net', 'OPA188AIDBVR', '2', '-15V'),
    ('join', 'MCP4921-E/MC', '8', 'OPA188AIDBVR', '3'),
    ('net', 'OPA1655DBVR', '5', '+15V'),
    ('net', 'OPA1655DBVR', '2', '-15V'),
    ('net', 'MCP4921-E/MC', '1', '+3V3_SG'),
    ('net', 'MCP4921-E/MC', '5', 'GND'),
    ('net', 'MCP4921-E/MC', '7', 'GND'),
    # DS22248 3.8: exposed pad tied to VSS on the PCB
    ('net', 'MCP4921-E/MC', '9', 'GND'),
    ('res', 'MCP4921-E/MC', '6', '6.8k', '+3V3_SG'),
    # INA239 (SPI, SLYS027A): VS 3.3 V, VBUS on the +12V side, 49.9 ohm /
    # 470 nF input filter on IN+/IN-, ALERT open-drain pulled up, CS idles high
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
    # ADS1220 (SPI, SBAS501D TSSOP-16): AVDD/DVDD 3.3 V, AVSS/DGND/REFN0 on
    # GND, internal oscillator (CLK to GND), AIN2 unused, CS and DRDY pulled up
    ('net', 'ADS1220IPW', '12', '+3V3_CH'),
    ('net', 'ADS1220IPW', '13', '+3V3_CH'),
    ('net', 'ADS1220IPW', '4', 'GND'),
    ('net', 'ADS1220IPW', '5', 'GND'),
    ('net', 'ADS1220IPW', '8', 'GND'),
    ('net', 'ADS1220IPW', '3', 'GND'),
    ('nc', 'ADS1220IPW', '7'),
    ('net', 'ADS1220IPW', '2', 'ADS1220_CS'),
    ('net', 'ADS1220IPW', '1', 'SPI_SCK'),
    ('net', 'ADS1220IPW', '16', 'SPI_MOSI'),
    ('net', 'ADS1220IPW', '15', 'SPI_MISO'),
    ('res', 'ADS1220IPW', '2', '10k', '+3V3_CH'),  # switched: no back-feed
    ('res', 'ADS1220IPW', '14', '10k', '+3V3_CH'),
    # MCP23S08 (Microchip DS20001919F, QFN-20): supply on the unswitched rail,
    # exposed pad and VSS on GND, RESET and address pins biased (Table 1-1),
    # SO on the shared MISO, power-good flags in, backlight and LEDs out
    ('net', 'MCP23S08-E/ML', '18', '+3V3'),
    ('net', 'MCP23S08-E/ML', '17', 'GND'),
    ('net', 'MCP23S08-E/ML', '21', 'GND'),
    ('net', 'MCP23S08-E/ML', '2', 'GND'),
    ('net', 'MCP23S08-E/ML', '3', 'GND'),
    ('net', 'MCP23S08-E/ML', '1', 'SPI_MISO'),
    ('net', 'MCP23S08-E/ML', '19', 'SPI_SCK'),
    ('net', 'MCP23S08-E/ML', '20', 'SPI_MOSI'),
    ('net', 'MCP23S08-E/ML', '5', 'EXPANDER_CS'),
    ('res', 'MCP23S08-E/ML', '4', '10k', '+3V3'),
    ('net', 'MCP23S08-E/ML', '9', 'PGP_15V'),
    ('net', 'MCP23S08-E/ML', '10', 'PGN_15V'),
    ('net', 'MCP23S08-E/ML', '11', 'PGP_16V5'),
    ('net', 'MCP23S08-E/ML', '12', 'PGN_16V5'),
    ('net', 'MCP23S08-E/ML', '13', 'DISP_BL_EN'),
    ('net', 'MCP23S08-E/ML', '14', 'LED_READY'),
    ('net', 'MCP23S08-E/ML', '15', 'LED_FAULT'),
    ('nc', 'MCP23S08-E/ML', '16'),
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
    ('between', 'SRP6050CA-4R7M', ('AP63205WU-7', '5'), ('NET', '+5V')),
    ('between', '100nF', ('AP63205WU-7', '6'), ('AP63205WU-7', '5')),
    ('net', 'LD1117S33TR', '3', '+5V_OR'),
    ('net', 'LD1117S33TR', '2', '+3V3'),
    # LM66100 pair (SLVSEZ8A pin table, Fig. 17): 1 VIN, 2 GND, 3 CE, 5 ST, 6 VOUT
    ('net', 'LM66100', '1', ('+5V', 'USB_VBUS')),
    ('net', 'LM66100', '2', ('GND',)),
    ('net', 'LM66100', '3', ('USB_VBUS', 'USB_SEL')),
    ('net', 'LM66100', '5', ('USB_SEL', 'GND')),
    ('net', 'LM66100', '6', ('+5V_OR',)),
    ('net', 'AD9833BRMZ', '2', '+5V_OR'),
    ('net', 'LD1117S33TR', '1', 'GND'),
    # Power path
    ('net', 'IRF4905S', '2', 'VSW'),
    ('net', 'IRF4905S', '3', 'VIN'),
    ('join', 'IRF4905S', '1', 'LTC2954CTS8-2', '6'),
    ('net', 'LTC2954CTS8-2', '1', 'VIN'),
    ('nc', 'LTC2954CTS8-2', '3'),
    ('resjoin', 'LTC2954CTS8-2', '8', '220k', 'LM4040DBZ-5', '1'),
    ('net', 'LM4040DBZ-5', '2', 'GND'),
    ('resjoin', 'LM4040DBZ-5', '1', '82k', 'LTC2954CTS8-2', '1'),
    ('net', '74AHCT1G125', '5', '+5V'),
    ('net', '74AHCT1G125', '1', 'GND'),
    ('net', '74AHCT1G125', '3', 'GND'),
    # ESP32-S3-WROOM-2: pins 28-30 are NC on this module, IO47/48 are 1.8 V
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '28'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '29'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '30'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '24'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '25', 'DISP_DC_1V8'),
    # SN74LVC138A (TI SCAS291, PW): 1 A, 2 B, 3 C, 4 G2A, 5 G2B, 6 G1, 7 Y7, 8 GND,
    # 9-15 Y6-Y0, 16 VCC. The enable pull-up holds all outputs high at reset;
    # GPIO3 and GPIO45 keep their strap resistors, now on the address lines
    ('net', 'SN74LVC138A', '16', '+3V3'),
    ('net', 'SN74LVC138A', '8', 'GND'),
    ('net', 'SN74LVC138A', '6', '+3V3'),
    ('net', 'SN74LVC138A', '5', 'GND'),
    ('net', 'SN74LVC138A', '1', 'CS_ADDR_A'),
    ('net', 'SN74LVC138A', '2', 'CS_ADDR_B'),
    ('net', 'SN74LVC138A', '3', 'CS_ADDR_C'),
    ('net', 'SN74LVC138A', '4', 'CS_EN_N'),
    ('res', 'SN74LVC138A', '4', '10k', '+3V3'),
    ('res', 'SN74LVC138A', '1', '10k', '+3V3'),
    ('res', 'SN74LVC138A', '3', '10k', 'GND'),
    ('net', 'SN74LVC138A', '15', 'AD9833_FSYNC'),
    ('net', 'SN74LVC138A', '14', 'MCP4921_CS'),
    ('net', 'SN74LVC138A', '13', 'INA239_CS'),
    ('net', 'SN74LVC138A', '12', 'EXPANDER_CS'),
    ('net', 'SN74LVC138A', '11', 'DISP_CS'),
    ('net', 'SN74LVC138A', '10', 'TOUCH_CS'),
    ('net', 'SN74LVC138A', '9', 'ADS1220_CS'),
    ('net', 'SN74LVC138A', '7', 'IMU_CS'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '15', 'CS_ADDR_A'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '36', 'CS_ADDR_B'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '26', 'CS_ADDR_C'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '39'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '5'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '7'),
    # SN74LV1T34 (TI, DBV): 2 A, 3 GND, 4 Y, 5 VCC; VIH 1.36 V at VCC 3.3 V
    ('net', 'SN74LV1T34', '5', '+3V3'),
    ('net', 'SN74LV1T34', '3', 'GND'),
    # ACS_CS is on GPIO17 (module pin 10), not GPIO43 / U0TXD (pin 37), which
    # toggles with ROM boot messages; it carries the power-good flag (active
    # low) behind a 1k series resistor
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '37', 'PG_15V_N'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '10', '10k', '+3V3'),
    # Phoenix 2.4" display FPC (datasheet 109921 p.7) and TSC2046 (TI SBAS417)
    ('net', 'FH12-14S-0.5SH(55)', '5', 'GND'),
    ('net', 'FH12-14S-0.5SH(55)', '6', '+3V3'),
    ('net', 'FH12-14S-0.5SH(55)', '7', 'DISP_CS'),
    ('net', 'FH12-14S-0.5SH(55)', '8', 'DISP_RST'),
    ('net', 'FH12-14S-0.5SH(55)', '9', 'DISP_DC'),
    ('net', 'FH12-14S-0.5SH(55)', '10', 'SPI_SCK'),
    ('net', 'FH12-14S-0.5SH(55)', '11', 'SPI_MOSI'),
    ('nc', 'FH12-14S-0.5SH(55)', '12'),
    ('res', 'FH12-14S-0.5SH(55)', '13', '39', '+5V_OR'),
    ('join', 'FH12-14S-0.5SH(55)', '4', 'TSC2046EIPW', '2'),
    ('join', 'FH12-14S-0.5SH(55)', '1', 'TSC2046EIPW', '3'),
    ('join', 'FH12-14S-0.5SH(55)', '2', 'TSC2046EIPW', '4'),
    ('join', 'FH12-14S-0.5SH(55)', '3', 'TSC2046EIPW', '5'),
    ('net', 'TSC2046EIPW', '1', '+3V3'),
    ('net', 'TSC2046EIPW', '10', '+3V3'),
    ('net', 'TSC2046EIPW', '6', 'GND'),
    ('net', 'TSC2046EIPW', '16', 'SPI_SCK'),
    ('net', 'TSC2046EIPW', '14', 'SPI_MOSI'),
    ('net', 'TSC2046EIPW', '12', 'SPI_MISO'),
    ('net', 'TSC2046EIPW', '15', 'TOUCH_CS'),
    ('nc', 'TSC2046EIPW', '9'),
    # J12 pin 3 (cryocooler protective ground) on board GND; J11 / J12 minus
    # on the isolated side
    ('net', 'CRYOCOOLER (+ / - / GND)', '3', 'GND'),
    ('net', 'CRYOCOOLER (+ / - / GND)', '2', 'ISO_GND'),
    ('net', 'AMP OUT (+ / -)', '2', 'ISO_GND'),
]


def run(path):
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

    for rule in RULES:
        kind, value = rule[0], rule[1]
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
    print(f'{len(RULES) - failures}/{len(RULES)} datasheet rules pass')
    return failures


if __name__ == '__main__':
    sys.exit(1 if run(sys.argv[1]) else 0)
