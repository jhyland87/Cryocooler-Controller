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
# ('fetdrive', value, pin, ohms, net)  pin is the drain of a BSS138 (or one
# BSS138DW element) with source on GND and its gate through `ohms` to `net`
# ('nores', value, pin, rail)          no resistor joins the pin's net to rail
# ('each', value, pin, ohms, rail)     as 'res', for every part of that value
# ('eachjoin', value, pin, ohms, pin2) every part of that value has the resistor
# between its own two pins
# ('caps', net, value, count, net2)   at least `count` capacitors of that value
# sit between net and net2
# N-FETs the open-drain rules accept: (value, gate, source, drain) per element.
# BSS138DW (Diodes ds30203): 1 S, 2 G, 6 D and 4 S, 5 G, 3 D.
NFET_ELEMENTS = (
    ('BSS138', '1', '2', '3'),
    ('BSS138DW', '2', '1', '6'),
    ('BSS138DW', '5', '4', '3'),
)


def far_pin(ref, pin):
    """The other end of a resistor. RN parts are 4-element arrays (Yageo YC124):
    element n joins pins n and 9 - n.
    """
    if ref.startswith('RN'):
        return str(9 - int(pin))
    return '2' if pin == '1' else '1'


def element_pins(ref):
    """Pin pairs of a two-terminal part's elements."""
    if ref.startswith('RN'):
        return [(str(pin), str(9 - pin)) for pin in range(1, 5)]
    return [('1', '2')]


# universal I/O: the per-channel net of each signal, any channel
IO_NETS = {
    name: tuple(f'IO{n}_{name}' for n in range(1, 5))
    for name in ('PIN', 'DAC', 'GATE', 'OUT_EN', 'AMP_FLT_N', 'DIV', 'DIRECT', 'PULLUP',
                 'BURDEN', 'SENS_EN', 'SENS_FLT_N', 'BUF_OE_N', 'LOGIC', 'BUF', 'LEVEL',
                 'DRV')
}

RULES = [
    # 4-pin fans (Intel 4-wire spec): PWM open drain through a BSS138 with the
    # gate pulled to +3V3 (0% drive at reset), tach open collector with a
    # pull-up at the connector and 4.7k to the GPIO. Rev 4: both drivers are one
    # BSS138DW, the 4.7k and 10k parts are array elements, the headers XKB X2510WRS
    ('fetdrive', 'FAN (4-pin PWM)', '4', '1k', 'FAN_PWM'),
    ('res', 'FAN (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'FAN (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '4.7k', ('FAN (4-pin PWM)', '3'), ('NET', 'FAN_TACH')),
    # each header's +12 V goes through its own Bourns MF-MSMF resettable fuse
    # (mfmsmf.pdf p. 1-2, 9-10): fan F3 MF-MSMF050/24X, 0.5 A hold (0.40 A at 50 C)
    # for 3 fans at 0.15 A; pump F4 MF-MSMF250/16X, 2.5 A hold (1.98 A at 50 C) for 1.5 A
    ('net', 'FAN (4-pin PWM)', '2', '+12V_FAN'),
    ('between', 'MF-MSMF050/24X', ('FAN (4-pin PWM)', '2'), ('NET', '+12V')),
    ('net', 'FAN (4-pin PWM)', '1', 'GND'),
    ('fetdrive', 'PUMP (4-pin PWM)', '4', '1k', 'PUMP_PWM'),
    ('res', 'PUMP (4-pin PWM)', '4', '10k', '+3V3_COOL'),
    ('res', 'PUMP (4-pin PWM)', '3', '4.7k', '+3V3_COOL'),
    ('between', '4.7k', ('PUMP (4-pin PWM)', '3'), ('NET', 'PUMP_TACH')),
    ('net', 'PUMP (4-pin PWM)', '2', '+12V_PUMP'),
    ('between', 'MF-MSMF250/16X', ('PUMP (4-pin PWM)', '2'), ('NET', '+12V')),
    ('net', 'PUMP (4-pin PWM)', '1', 'GND'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '17', 'FAN_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '22', 'PUMP_PWM'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '8', 'FAN_TACH'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '23', 'PUMP_TACH'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '17', '10k', '+3V3'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '22', '10k', '+3V3'),
    # ECS-2520MV (ECS datasheet): 1 tri-state (high = enabled), 2 GND, 3 OUT, 4 VDD
    ('net', 'ECS-2520MV-160-BN-TR', '4', ('+3V3_SG', '+3V3')),
    ('net', 'ECS-2520MV-160-BN-TR', '1', ('+3V3_SG', '+3V3')),
    ('net', 'ECS-2520MV-160-BN-TR', '2', ('GND',)),
    # AD9837 (ADI rev A): 16 MHz MCLK max (B grade), so the 16 MHz oscillator
    ('join', 'ECS-2520MV-160-BN-TR', '3', 'AD9837BCPZ', '5'),
    # LT3045 (ADI rev D, DD): 1-2 IN, 3 EN/UV, 4 PG, 5 ILIM, 6 PGFB, 7 SET, 8 GND,
    # 9 OUTS, 10 OUT, pad 11 GND. LT3094 (DD): 1-2 IN, 3 EN/UV, 4 PG, 5 PGFB,
    # 6 ILIM, 7 VIOC (float), 8 SET, 9 GND, 10 OUTS, 11-12 OUT, pad 13 IN.
    # Both: EN/UV to IN, ILIM to GND when unused, VOUT = 100 uA x RSET (147k = 14.7 V;
    # the LT3045 stops at 15 V), inputs within +-20 V
    *(('net', 'LT3045EDD', pin, '+16V5') for pin in ('1', '2', '3')),
    *(('net', 'LT3045EDD', pin, '+15V') for pin in ('10', '9')),
    *(('net', 'LT3045EDD', pin, 'GND') for pin in ('8', '11', '5')),
    ('res', 'LT3045EDD', '7', '147k', 'GND'),
    *(('net', 'LT3094HDD', pin, '-16V5') for pin in ('1', '2', '13', '3')),
    *(('net', 'LT3094HDD', pin, '-15V') for pin in ('11', '12', '10')),
    *(('net', 'LT3094HDD', pin, 'GND') for pin in ('9', '6')),
    ('nc', 'LT3094HDD', '7'),
    ('res', 'LT3094HDD', '8', '147k', 'GND'),
    # power-good thresholds: 0.3 V x (1 + 432k / 10k) = 13.3 V
    ('res', 'LT3045EDD', '6', '432k', '+15V'),
    ('res', 'LT3045EDD', '6', '10k', 'GND'),
    ('res', 'LT3094HDD', '5', '432k', '-15V'),
    ('res', 'LT3094HDD', '5', '10k', 'GND'),
    # each PG pin pulls its own node low; each node is fed from +15 V so it reads
    # 0 V when its rail is missing (the two are ANDed into PG_15V)
    ('net', 'LT3045EDD', '4', 'PGP_15V'),
    ('net', 'LT3094HDD', '4', 'PGN_15V'),
    ('res', 'LT3045EDD', '4', '220k', '+15V'),
    ('res', 'LT3045EDD', '4', '62k', 'GND'),
    ('res', 'LT3094HDD', '4', '220k', '+15V'),
    ('res', 'LT3094HDD', '4', '62k', 'GND'),
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
    # TPD1E05U06 (TI SLVSBO5): 1 IO, 2 GND; on the power button and display lines
    ('net', 'TPD1E05U06DPYR', '2', ('GND',)),
    ('net', 'TPD1E05U06DPYR', '1',
     ('PWR_BTN', 'ESP_EN', 'DISP_PWR_BTN', 'DISP_RESET', 'AUX11_HDR', 'AUX13_HDR')),
    ('net', 'LTC2954CDDB-2', '3', 'PWR_BTN'),
    # supply jumpers: pin 1 on the main rail, pin 2 on the switched rail
    ('net', 'EN SG3', '1', '+3V3'),
    ('net', 'EN SG3', '2', '+3V3_SG'),
    ('net', 'EN PS15', '1', '+5V'),
    ('net', 'EN PS15', '2', '+5V_PS15'),
    ('net', 'EN ISO3', '1', '+3V3'),
    ('net', 'EN ISO3', '2', '+3V3_ISO'),
    ('net', 'EN COOL', '1', '+3V3'),
    ('net', 'EN COOL', '2', '+3V3_COOL'),
    # the cold head feed has a ferrite ahead of its jumper
    ('between', 'BLM18PG121SN1D', ('NET', '+3V3'), ('EN CH', '1')),
    ('net', 'EN CH', '2', '+3V3_CH'),
    # ISOW7841A-Q1 (TI SLLSFG1B, DWE): 1 VCC, 2 and 8 GND1, 3-5 INA-INC, 6 OUTD, 7 NC,
    # 9 and 15 GND2, 10 SEL, 11 IND, 12-14 OUTC-OUTA, 16 VISO. VIH = 0.7 x VCC, so VCC
    # is 3.3 V like the logic that drives it; SEL on VISO = 5 V out, 40 mA from 3.3 V.
    # No F suffix = outputs default high when an input is lost
    ('net', 'ISOW7841AQDWERQ1', '1', '+3V3_ISO'),
    ('net', 'ISOW7841AQDWERQ1', '2', 'GND'),
    ('net', 'ISOW7841AQDWERQ1', '8', 'GND'),
    ('net', 'ISOW7841AQDWERQ1', '16', 'ISO_5V'),
    ('net', 'ISOW7841AQDWERQ1', '10', 'ISO_5V'),
    ('net', 'ISOW7841AQDWERQ1', '9', 'ISO_GND'),
    ('net', 'ISOW7841AQDWERQ1', '15', 'ISO_GND'),
    ('nc', 'ISOW7841AQDWERQ1', '7'),
    # rev 4: the ACS37800 shares the SPI bus. Its datasheet says MISO stays driven
    # with CS high and is silent on SCLK with CS high, so SN74LVC1G125 gates (TI
    # SCES223, DRY: 1 OE, 2 A, 3 GND, 4 Y, 5 n.c., 6 VCC; off while OE is high) pass
    # SCK in and MISO out only while ACS_CS is low
    ('net', 'ISOW7841AQDWERQ1', '3', 'SPI_MOSI'),
    ('net', 'ISOW7841AQDWERQ1', '4', 'ACS_SCK'),
    ('net', 'ISOW7841AQDWERQ1', '5', 'ACS_CS'),
    ('net', 'ISOW7841AQDWERQ1', '6', 'ACS_MISO'),
    ('res', 'ISOW7841AQDWERQ1', '4', '10k', '+3V3'),
    ('net', 'SN74LVC1G125DRYR', '1', ('ACS_CS', 'EXP_CS_A', 'EXP_CS_B', *IO_NETS['BUF_OE_N'])),
    ('net', 'SN74LVC1G125DRYR', '2', ('SPI_SCK', 'ACS_MISO', 'EXP_MISO', *IO_NETS['LOGIC'])),
    ('net', 'SN74LVC1G125DRYR', '4', ('ACS_SCK', 'SPI_MISO', *IO_NETS['BUF'])),
    ('net', 'SN74LVC1G125DRYR', '3', ('GND',)),
    ('net', 'SN74LVC1G125DRYR', '6', ('+3V3',)),
    ('nc', 'SN74LVC1G125DRYR', '5'),
    # ACS37800 on the isolated 5 V domain
    ('net', 'ACS37800KMACTR-015B5-SPI', '13', 'ISO_5V'),
    ('net', 'ACS37800KMACTR-015B5-SPI', '14', 'ISO_GND'),
    ('net', 'ACS37800KMACTR-015B5-SPI', '15', 'ISO_GND'),
    # isolated SPI: OUTA/OUTB/OUTC carry MOSI/SCK/CS forward, IND returns MISO
    ('join', 'ISOW7841AQDWERQ1', '14', 'ACS37800KMACTR-015B5-SPI', '10'),
    ('join', 'ISOW7841AQDWERQ1', '13', 'ACS37800KMACTR-015B5-SPI', '11'),
    ('join', 'ISOW7841AQDWERQ1', '12', 'ACS37800KMACTR-015B5-SPI', '9'),
    ('join', 'ISOW7841AQDWERQ1', '11', 'ACS37800KMACTR-015B5-SPI', '12'),
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
    # 4-terminal shunt (Vishay WSK2512, doc 30108): 4 and 1 carry the current, 3 and 2 are the
    # sense pads at the same two ends. The filter starts on the sense pads only, and
    # VBUS sits on the rail, not on the filtered IN- node (hardware/TODO.md, rev 5)
    # 12 V input: Mini-Fit Jr 2 x 2 pinned as the ATX 12 V connector (1, 2 ground;
    # 3, 4 +12 V) into a 10 A fuse (Littelfuse 453 series, same land as the 5 A)
    ('net', '12V IN (ATX 4-PIN)', '1', 'GND'),
    ('net', '12V IN (ATX 4-PIN)', '2', 'GND'),
    ('same', '12V IN (ATX 4-PIN)', '3', '4'),
    ('between', '10A backup', ('12V IN (ATX 4-PIN)', '3'), ('NET', 'VIN')),
    ('net', '10m', '4', 'VSW'),
    ('net', '10m', '1', '+12V'),
    ('net', 'INA239AIDGSR', '8', '+12V'),
    ('between', '49.9', ('INA239AIDGSR', '10'), ('10m', '3')),
    ('between', '49.9', ('INA239AIDGSR', '9'), ('10m', '2')),
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
    ('net', 'MCP23S08-E/ML', '13', 'IO_EXP_INT_N'),
    ('net', 'MCP23S08-E/ML', '15', 'INA239_ALERT'),
    ('nc', 'MCP23S08-E/ML', '16'),
    ('net', 'MCP23S08-E/ML', '14', 'IO_ADC_DRDY_N'),
    # -15 V guard: an unpowered LT3094 cannot pull PGN low, so the midpoint of two
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
    # single LEDs, Kingbright APHHS1005SURCK (V.18A) / APHHS1005LZGCK-V (V.6B):
    # 1 cathode, 2 anode
    ('net', 'ALERT (red)', '1', 'INA239_ALERT'),
    ('res', 'ALERT (red)', '2', '1.5k', '+3V3'),
    ('res', 'ISO 5V (green)', '2', '3.3k', 'ISO_5V'),
    ('net', 'ISO 5V (green)', '1', 'ISO_GND'),
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
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '25'),
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '16'),
    # 74HC154BQ (Nexperia 74HC_HCT154 rev 9, SOT815-1): 1-11 Y0-Y10, 12 GND, 13-17 Y11-Y15,
    # 18 E0, 19 E1, 20-23 A3-A0, 24 VCC, 25 exposed pad (floating or VCC). The enable
    # pull-up holds all outputs high at reset; E1 is grounded.
    ('net', '74HC154BQ', '24', '+3V3'),
    ('net', '74HC154BQ', '12', 'GND'),
    ('net', '74HC154BQ', '19', 'GND'),
    ('nc', '74HC154BQ', '25'),
    ('net', '74HC154BQ', '23', 'CS_ADDR_A'),
    ('net', '74HC154BQ', '22', 'CS_ADDR_B'),
    ('net', '74HC154BQ', '21', 'CS_ADDR_C'),
    ('net', '74HC154BQ', '20', 'CS_ADDR_D'),
    ('net', '74HC154BQ', '18', 'CS_EN_N'),
    ('res', '74HC154BQ', '18', '10k', '+3V3'),
    ('res', '74HC154BQ', '23', '10k', '+3V3'),
    ('res', '74HC154BQ', '21', '10k', 'GND'),
    ('net', '74HC154BQ', '1', 'AD9833_FSYNC'),
    ('net', '74HC154BQ', '2', 'AD5453_SYNC'),
    ('net', '74HC154BQ', '3', 'INA239_CS'),
    ('net', '74HC154BQ', '4', 'EXPANDER_CS'),
    ('net', '74HC154BQ', '5', 'IO_DAC_CS'),
    ('net', '74HC154BQ', '6', 'ACS_CS'),
    ('net', '74HC154BQ', '7', 'ADS1220_CS'),
    ('net', '74HC154BQ', '8', 'IMU_CS'),
    ('net', '74HC154BQ', '9', 'AMBIENT_CS'),
    ('net', '74HC154BQ', '10', 'IO_ADC_CS'),
    ('net', '74HC154BQ', '11', 'IO_EXP_CS'),
    ('net', '74HC154BQ', '13', 'RS485_CS'),
    ('net', '74HC154BQ', '14', 'EXP_CS_A'),
    ('net', '74HC154BQ', '15', 'EXP_CS_B'),
    # address bit D: GPIO47 is 1.8 V, so 74LV1T34GX lifts it (VIH 1.37 V at 3.3 V)
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '24', 'CS_ADDR_D_1V8'),
    # ADT7320 (Analog Devices rev 0, CP-16-17): 1 SCLK, 2 DOUT, 3 DIN, 4 CS, 9 INT, 10 CT,
    # 11 GND, 12 VDD, 5-8 and 13-16 NC, 17 exposed pad (floating or GND). INT and CT are
    # open drain with 10 k pull-ups.
    ('net', 'ADT7320UCPZ', '12', '+3V3'),
    ('net', 'ADT7320UCPZ', '11', 'GND'),
    ('net', 'ADT7320UCPZ', '17', 'GND'),
    ('net', 'ADT7320UCPZ', '1', 'SPI_SCK'),
    ('net', 'ADT7320UCPZ', '2', 'SPI_MISO'),
    ('net', 'ADT7320UCPZ', '3', 'SPI_MOSI'),
    ('net', 'ADT7320UCPZ', '4', 'AMBIENT_CS'),
    ('net', 'ADT7320UCPZ', '9', 'AMBIENT_INT'),
    ('net', 'ADT7320UCPZ', '10', 'AMBIENT_CT'),
    ('res', 'ADT7320UCPZ', '9', '10k', '+3V3'),
    ('res', 'ADT7320UCPZ', '10', '10k', '+3V3'),
    ('net', 'MCP23S08-E/ML', '11', 'AMBIENT_INT'),
    ('net', 'MCP23S08-E/ML', '12', 'AMBIENT_CT'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '15', 'CS_ADDR_A'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '36', 'CS_ADDR_B'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '26', 'CS_ADDR_C'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '39', 'PWR_INT'),
    # ── universal I/O (rev 5) ──
    # fast channels 1-4 keep GPIO5, 7, 11 and 13 (module pins 5, 7, 19, 21)
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '5', 'AUX_IO5'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '7', 'AUX_IO7'),
    # AUX header (rev 6): GPIO11 (module pin 19) and GPIO13 (pin 21), each through
    # 100 R; supplies on pins 1 and 2
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '19', 'AUX_IO11'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '21', 'AUX_IO13'),
    ('net', 'AUX HEADER', '1', '+5V'),
    ('net', 'AUX HEADER', '2', '+3V3'),
    ('net', 'AUX HEADER', '5', 'GND'),
    ('between', '100', ('AUX HEADER', '3'), ('NET', 'AUX_IO11')),
    ('between', '100', ('AUX HEADER', '4'), ('NET', 'AUX_IO13')),
    # Output drivers: TSB582 (ST DS13378 rev 2, DFN8): 1 Out1, 2 In1-, 3 In1+, 4 VCC-,
    # 5 In2+, 6 In2-, 7 Out2, 8 VCC+, pad floating or VCC-. 4-36 V, inputs from VCC- to
    # VCC+ - 1.5 V (0-2.5 V is inside), 150 mA min output. Gain 1 + 191k / 49.9k = 4.83,
    # feedback ahead of the switch
    ('net', 'TSB582IQ2T', '8', ('+12V',)),
    ('net', 'TSB582IQ2T', '4', ('GND',)),
    ('net', 'TSB582IQ2T', '9', ('GND',)),
    *(('net', 'TSB582IQ2T', pin, (*IO_NETS['LEVEL'][:2], *IO_NETS['DAC'][2:]))
      for pin in ('3', '5')),
    *(('net', 'TSB582IQ2T', pin, IO_NETS['DRV']) for pin in ('1', '7')),
    *(('each', 'TSB582IQ2T', pin, '49.9k', 'GND') for pin in ('2', '6')),
    *(('eachjoin', 'TSB582IQ2T', minus, '191k', out) for minus, out in (('2', '1'), ('6', '7'))),
    ('caps', '+12V', '100nF', 4, 'GND'),
    # SN74LVC1G3157 (TI SCES424O, DSF): 1 B2, 2 GND, 3 B1, 4 A, 5 VCC, 6 S; A to B1
    # while S is low. B1 on GND, so the driver input is 0 V while the GPIO floats
    ('net', 'SN74LVC1G3157DSFR', '5', ('+3V3',)),
    ('net', 'SN74LVC1G3157DSFR', '2', ('GND',)),
    ('net', 'SN74LVC1G3157DSFR', '3', ('GND',)),
    ('net', 'SN74LVC1G3157DSFR', '1', IO_NETS['DAC']),
    ('net', 'SN74LVC1G3157DSFR', '4', IO_NETS['LEVEL']),
    ('net', 'SN74LVC1G3157DSFR', '6', IO_NETS['GATE']),
    ('each', 'SN74LVC1G3157DSFR', '6', '100k', 'GND'),
    # fast channels: pin -> 1 M -> buffer input (clamped to +3V3) -> 1 k -> GPIO; the
    # buffer enable is pulled high (off) and the GPIO reaches the gate through 1 k
    *(('between', '1M', ('NET', f'IO{n}_PIN'), ('NET', f'IO{n}_LOGIC')) for n in range(1, 3)),
    *(('between', '1N4148W', ('NET', f'IO{n}_LOGIC'), ('NET', '+3V3')) for n in range(1, 3)),
    *(('between', '10k', ('NET', f'IO{n}_BUF_OE_N'), ('NET', '+3V3')) for n in range(1, 3)),
    *(('between', '1k', ('NET', f'IO{n}_BUF'), ('NET', f'AUX_IO{gpio}'))
      for n, gpio in ((1, 5), (2, 7))),
    *(('between', '1k', ('NET', f'IO{n}_GATE'), ('NET', f'AUX_IO{gpio}'))
      for n, gpio in ((1, 5), (2, 7))),
    # ── RS-485 port ──
    # SC16IS750 (NXP rev 7.1, HVQFN24): 1 RESET, 2 XTAL1, 4 VDD, 5 I2C/SPI (low = SPI),
    # 6 CS, 7 SI, 8 SO, 9 SCLK, 10 VSS in SPI mode, 11 IRQ (open drain, 1 k pull-up at
    # 3.3 V), 16 VSS, 21 RTS, 22 CTS, 23 TX, 24 RX
    ('net', 'SC16IS750IBS', '4', '+3V3'),
    *(('net', 'SC16IS750IBS', pin, 'GND') for pin in ('5', '10', '16', '25', '22')),
    ('net', 'SC16IS750IBS', '6', 'RS485_CS'),
    ('net', 'SC16IS750IBS', '9', 'SPI_SCK'),
    ('net', 'SC16IS750IBS', '7', 'SPI_MOSI'),
    ('net', 'SC16IS750IBS', '8', 'SPI_MISO'),
    ('net', 'SC16IS750IBS', '1', 'ESP_EN'),
    ('net', 'SC16IS750IBS', '11', 'RS485_IRQ_N'),
    ('res', 'SC16IS750IBS', '11', '1k', '+3V3'),
    # clocked by a second ECS-2520MV-160 (16 MHz); its supply pins are covered by the
    # oscillator rules above, and UART_CLK having two nodes by the single-node check
    ('net', 'SC16IS750IBS', '2', 'UART_CLK'),
    ('nc', 'SC16IS750IBS', '3'),
    # THVD2410 (TI SLLSF20B, DRB): 1 R, 2 /RE, 3 DE, 4 D, 5 GND, 6 A, 7 B, 8 VCC
    ('net', 'THVD2410DRBR', '8', '+3V3'),
    ('net', 'THVD2410DRBR', '5', 'GND'),
    ('net', 'THVD2410DRBR', '9', 'GND'),
    ('join', 'THVD2410DRBR', '1', 'SC16IS750IBS', '24'),
    ('join', 'THVD2410DRBR', '4', 'SC16IS750IBS', '23'),
    ('same', 'THVD2410DRBR', '3', '2'),
    ('res', 'THVD2410DRBR', '3', '10k', '+3V3'),
    ('res', 'THVD2410DRBR', '1', '10k', '+3V3'),
    # Qwiic / STEMMA QT pin order (SparkFun Qwiic spec; Adafruit STEMMA QT technical
    # specs: 1 GND, 2 V+, 3 SDA, 4 SCL), on the same lines as J40 pins 3 and 4
    ('net', 'QWIIC / STEMMA QT', '1', 'GND'),
    ('net', 'QWIIC / STEMMA QT', '2', '+3V3'),
    ('join', 'QWIIC / STEMMA QT', '3', 'AUX HEADER', '3'),
    ('join', 'QWIIC / STEMMA QT', '4', 'AUX HEADER', '4'),
    ('join', 'THVD2410DRBR', '6', 'RS-485 (A / B / GND / NC)', '1'),
    ('join', 'THVD2410DRBR', '7', 'RS-485 (A / B / GND / NC)', '2'),
    ('net', 'RS-485 (A / B / GND / NC)', '3', 'GND'),
    # XKB makes no 3-pin X2510WRS: the 3-wire ports use the 4-pin part, pin 4 unused
    ('nc', 'RS-485 (A / B / GND / NC)', '4'),
    *(('nc', f'PRESSURE {n} (5V / SIG / GND / NC)', '4') for n in (1, 2)),
    *(('nc', f'IO{n} (V+ / IO / GND / NC)', '4') for n in range(1, 5)),
    # SPI expansion header: MISO reaches the bus only through the two CS-gated buffers
    ('net', 'SPI EXPANSION', '1', '+3V3'),
    ('net', 'SPI EXPANSION', '2', '+5V'),
    ('net', 'SPI EXPANSION', '9', 'GND'),
    ('net', 'SPI EXPANSION', '10', 'GND'),
    ('net', 'SPI EXPANSION', '5', 'EXP_MISO'),
    ('net', 'SPI EXPANSION', '6', 'EXP_INT_N'),
    ('between', '100', ('SPI EXPANSION', '3'), ('NET', 'SPI_SCK')),
    ('between', '100', ('SPI EXPANSION', '4'), ('NET', 'SPI_MOSI')),
    ('between', '100', ('SPI EXPANSION', '7'), ('NET', 'EXP_CS_A')),
    ('between', '100', ('SPI EXPANSION', '8'), ('NET', 'EXP_CS_B')),
    # DAC60508Z (TI SLASEL1D, RTE): 1 REF, 2-5 OUT0-3, 6 GND, 7 VDD, 8-11 OUT4-7,
    # 12 CS, 13 SCLK, 14 SDI, 15 SDO, 16 VIO; >= 150 nF on REF
    ('net', 'DAC60508ZRTER', '7', '+3V3'),
    ('net', 'DAC60508ZRTER', '16', '+3V3'),
    ('net', 'DAC60508ZRTER', '6', 'GND'),
    ('net', 'DAC60508ZRTER', '17', 'GND'),
    ('net', 'DAC60508ZRTER', '12', 'IO_DAC_CS'),
    ('net', 'DAC60508ZRTER', '13', 'SPI_SCK'),
    ('net', 'DAC60508ZRTER', '14', 'SPI_MOSI'),
    ('net', 'DAC60508ZRTER', '15', 'SPI_MISO'),
    *(('net', 'DAC60508ZRTER', pin, f'IO{n}_DAC')
      for n, pin in enumerate(('2', '3', '4', '5'), 1)),
    *(('nc', 'DAC60508ZRTER', pin) for pin in ('8', '9', '10', '11')),
    # ADS124S08 (TI SBAS660C, RHB): 1 AINCOM, 2-7 AIN5-0, 8 START, 9 CS, 10 DIN,
    # 11 SCLK, 12 DOUT, 13 DRDY, 14 DGND, 15 IOVDD, 16 DVDD, 17 CLK, 18 RESET,
    # 23 REFOUT, 24 REFCOM, 26 AVDD, 27 AVSS, 28 AVSS-SW, 31 AIN7, 32 AIN6. START and
    # CLK to DGND, RESET to IOVDD, REFCOM to AVSS (section 10.1.5)
    ('net', 'ADS124S08IRHBR', '26', '+5V_IO'),
    ('net', 'ADS124S08IRHBR', '16', '+3V3'),
    ('net', 'ADS124S08IRHBR', '15', '+3V3'),
    ('net', 'ADS124S08IRHBR', '18', '+3V3'),
    *(('net', 'ADS124S08IRHBR', pin, 'GND')
      for pin in ('27', '28', '14', '33', '24', '17', '8', '1')),
    ('net', 'ADS124S08IRHBR', '9', 'IO_ADC_CS'),
    ('net', 'ADS124S08IRHBR', '11', 'SPI_SCK'),
    ('net', 'ADS124S08IRHBR', '10', 'SPI_MOSI'),
    ('net', 'ADS124S08IRHBR', '12', 'SPI_MISO'),
    ('net', 'ADS124S08IRHBR', '13', 'IO_ADC_DRDY_N'),
    *(('net', 'ADS124S08IRHBR', pin, f'IO{n}_ADC')
      for n, pin in enumerate(('7', '6', '5', '4'), 1)),
    # pressure ports on AIN4 / AIN5: 5 V excitation on pin 1, signal behind 2.2 k with
    # 100k to ground; AIN6 / AIN7 unused (left open, section 10.1.5)
    ('net', 'ADS124S08IRHBR', '3', 'PRESS1_ADC'),
    ('net', 'ADS124S08IRHBR', '2', 'PRESS2_ADC'),
    *(('nc', 'ADS124S08IRHBR', pin) for pin in ('32', '31')),
    *(('net', f'PRESSURE {n} (5V / SIG / GND / NC)', '1', 'PREC_EXC') for n in (1, 2)),
    *(('net', f'PRESSURE {n} (5V / SIG / GND / NC)', '3', 'GND') for n in (1, 2)),
    *(('between', '2.2k', (f'PRESSURE {n} (5V / SIG / GND / NC)', '2'), ('NET', f'PRESS{n}_ADC'))
      for n in (1, 2)),
    *(('between', '100k', ('NET', f'PRESS{n}_ADC'), ('NET', 'GND')) for n in (1, 2)),
    # precision ports: AIN8 / AIN9 port A, AIN10 / AIN11 port B, each behind 2.2 k;
    # REFP0 / REFN0 take the excitation and its ground through 1 k (VREF up to AVDD).
    # AVDD is 5 V (2.7-5.25 V allowed) so a bridge gets 5 V and still fits the reference
    ('net', 'ADS124S08IRHBR', '22', 'PREC_A_P'),
    ('net', 'ADS124S08IRHBR', '21', 'PREC_A_N'),
    ('net', 'ADS124S08IRHBR', '20', 'PREC_B_P'),
    ('net', 'ADS124S08IRHBR', '19', 'PREC_B_N'),
    ('net', 'ADS124S08IRHBR', '30', 'PREC_REFP'),
    ('net', 'ADS124S08IRHBR', '29', 'PREC_REFN'),
    ('between', '1k', ('NET', 'PREC_EXC'), ('NET', 'PREC_REFP')),
    ('between', '1k', ('NET', 'GND'), ('NET', 'PREC_REFN')),
    *(('between', '2.2k', (f'SENSOR {port} (EXC / IN+ / IN- / GND)', pin),
       ('NET', f'PREC_{port}_{side}'))
      for port in 'AB' for pin, side in (('2', 'P'), ('3', 'N'))),
    *(('net', f'SENSOR {port} (EXC / IN+ / IN- / GND)', '1', 'PREC_EXC') for port in 'AB'),
    *(('net', f'SENSOR {port} (EXC / IN+ / IN- / GND)', '4', 'GND') for port in 'AB'),
    *(('between', '100k', ('NET', f'IO{n}_PIN'), ('NET', f'IO{n}_ADC')) for n in range(1, 5)),
    *(('between', '20k', ('NET', f'IO{n}_ADC'), ('NET', f'IO{n}_DIV')) for n in range(1, 5)),
    # MCP23S17 (Microchip DS20001952C, QFN): 5 VDD, 6 VSS, 7 CS, 8 SCK, 9 SI, 10 SO,
    # 11-13 A0-A2, 14 RESET, 15 INTB, 16 INTA. A2 low on every device (errata DS80311A)
    ('net', 'MCP23S17-E/ML', '5', ('+3V3',)),
    ('net', 'MCP23S17-E/ML', '6', ('GND',)),
    ('net', 'MCP23S17-E/ML', '29', ('GND',)),
    ('net', 'MCP23S17-E/ML', '7', ('IO_EXP_CS',)),
    ('net', 'MCP23S17-E/ML', '8', ('SPI_SCK',)),
    ('net', 'MCP23S17-E/ML', '9', ('SPI_MOSI',)),
    ('net', 'MCP23S17-E/ML', '10', ('SPI_MISO',)),
    ('net', 'MCP23S17-E/ML', '14', ('ESP_EN',)),
    ('net', 'MCP23S17-E/ML', '13', ('GND',)),
    ('net', 'MCP23S17-E/ML', '11', ('GND', '+3V3')),
    ('net', 'MCP23S17-E/ML', '12', ('GND', '+3V3')),
    ('net', 'MCP23S17-E/ML', '16', ('IO_EXP_INT_N',)),
    ('net', 'MCP23S17-E/ML', '15', ('IO_EXP_INT_N',)),
    ('res', 'MCP23S17-E/ML', '16', '10k', '+3V3'),
    # TMUX1111 (TI, RSV): 1 S1, 3 GND, 4 S4, 5 D4, 6 SEL4, 7 SEL3, 8 D3, 9 S3, 11 VDD,
    # 12 S2, 13 D2, 14 SEL2, 15 SEL1, 16 D1; closed while SEL is low
    ('net', 'TMUX1111RSVR', '11', ('+5V_IO',)),
    ('net', 'TMUX1111RSVR', '3', ('GND',)),
    *(('net', 'TMUX1111RSVR', pin, ('GND',)) for pin in ('16', '13', '8', '5')),
    *(('net', 'TMUX1111RSVR', pin, IO_NETS['DIV']) for pin in ('1', '12', '9', '4')),
    *(('net', 'TMUX1111RSVR', pin, IO_NETS['DIRECT']) for pin in ('15', '14', '7', '6')),
    *(('between', '100k', ('NET', f'IO{n}_DIRECT'), ('NET', 'GND')) for n in range(1, 5)),
    # TMUX7412F (TI, RRP): same signal pins, 2 VSS, 10 FF, pad to GND; 8-44 V single
    # supply, closed while SEL is high, source pins fault protected to +-60 V, 100 mA
    # continuous. Two are the pull-up switches (drain through 10k to +3V3), two the
    # output switches (drain on the driver, FF to the expander)
    ('net', 'TMUX7412FRRPR', '11', ('+12V',)),
    *(('net', 'TMUX7412FRRPR', pin, ('GND',)) for pin in ('2', '3', '17')),
    *(('net', 'TMUX7412FRRPR', pin, IO_NETS['PIN']) for pin in ('1', '12', '9', '4')),
    *(('net', 'TMUX7412FRRPR', pin, (*IO_NETS['PULLUP'], *IO_NETS['OUT_EN']))
      for pin in ('15', '14', '7', '6')),
    *(('between', '100k', ('NET', f'IO{n}_PULLUP'), ('NET', 'GND')) for n in range(1, 5)),
    *(('between', '100k', ('NET', f'IO{n}_OUT_EN'), ('NET', 'GND')) for n in range(1, 5)),
    ('between', '10k', ('NET', 'IO_OUT_FLT_A_N'), ('NET', '+3V3')),
    # TPS26625 (TI SLVSDT4F, DRC): 1 IN, 2 UVLO, 3 OVP, 4 SHDN, 5 RTN, 6 GND, 7 ILIM,
    # 8 dVdT, 9 FLT, 10 OUT. UVLO to IN through >= 1 M, OVP to RTN when unused; SHDN
    # floats high (on), so 22k holds it low; ILIM 53.6k -> 6.636 / 53.6 = 124 mA
    *(('net', 'TPS26625DRCR', pin, ('GND',)) for pin in ('3', '5', '6', '11')),
    ('net', 'TPS26625DRCR', '4', (*IO_NETS['SENS_EN'], 'PREC_EXC_EN')),
    ('net', 'TPS26625DRCR', '9', (*IO_NETS['SENS_FLT_N'], 'PREC_EXC_FLT_N')),
    ('eachjoin', 'TPS26625DRCR', '2', '1M', '1'),
    ('each', 'TPS26625DRCR', '4', '22k', 'GND'),
    ('each', 'TPS26625DRCR', '7', '53.6k', 'GND'),
    ('each', 'TPS26625DRCR', '9', '10k', '+3V3'),
    # TVS1800 (TI, DRV): 1-3 and pad GND, 4-6 IN
    *(('net', 'TVS1800DRVR', pin, ('GND',)) for pin in ('1', '2', '3', '7')),
    # burden switch CSD17381F4: 1 gate, 2 source, 3 drain (SLPS411G top view)
    ('net', 'CSD17381F4', '2', ('GND',)),
    ('net', 'CSD17381F4', '1', (*IO_NETS['BURDEN'], 'RS485_RTS_N')),
    *(('between', '100k', ('NET', f'IO{n}_BURDEN'), ('NET', 'GND')) for n in range(1, 5)),
    # RS-485 direction: RTS (high after reset) -> FET gate, drain -> DE and /RE
    ('net', 'SC16IS750IBS', '21', 'RS485_RTS_N'),
    *(('net', f'IO{n} (V+ / IO / GND / NC)', '2', f'IO{n}_PIN') for n in range(1, 5)),
    *(('net', f'IO{n} (V+ / IO / GND / NC)', '3', 'GND') for n in range(1, 5)),
    ('nc', 'ALPHACOOL ES FLOW (pin 4 NC)', '4'),
    # 74LV1T34GX (Nexperia rev 4, X2SON5): 1 n.c. (grounded for the footprint
    # bridge), 2 A, 3 GND, 4 Y, 5 VCC; VIH 1.37 V at VCC 3.0-3.3 V
    ('net', '74LV1T34GX', '5', '+3V3'),
    ('net', '74LV1T34GX', '3', 'GND'),
    ('net', '74LV1T34GX', '1', 'GND'),
    ('net', '74LV1T34GX', '2', 'CS_ADDR_D_1V8'),
    ('net', '74LV1T34GX', '4', 'CS_ADDR_D'),
    # GPIO43 / U0TXD (pin 37) toggles with ROM boot messages; it carries the
    # power-good flag (active low) behind a 1k series resistor
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '37', 'PG_15V_N'),
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
    # Waveshare ESP32-S3-Touch-LCD-4.3B link. TCAN3414 (TI SLLSFS8A, DRB): 1 TXD,
    # 2 GND, 3 VCC (3.0-3.6 V), 4 RXD, 5 SHDN (high = shutdown), 6 CANL, 7 CANH,
    # 8 STB (high = standby), pad to GND
    ('net', 'TCAN3414DRBR', '3', '+3V3'),
    ('net', 'TCAN3414DRBR', '2', 'GND'),
    ('net', 'TCAN3414DRBR', '9', 'GND'),
    ('net', 'TCAN3414DRBR', '5', 'GND'),
    ('net', 'TCAN3414DRBR', '8', 'GND'),
    ('net', 'TCAN3414DRBR', '1', 'CAN_TX'),
    ('net', 'TCAN3414DRBR', '4', 'CAN_RX'),
    ('res', 'TCAN3414DRBR', '1', '10k', '+3V3'),
    # 120 R from CAN_L through the fitted 0 R link JP20 to CAN_H
    ('between', '120', ('TCAN3414DRBR', '6'), ('CAN 0R', '2')),
    ('join', 'TCAN3414DRBR', '7', 'CAN 0R', '1'),
    # pass-through header J42: 1 CAN_L, 2 CAN_H, 3 GND
    ('join', 'TCAN3414DRBR', '6', 'CAN OUT', '1'),
    ('join', 'TCAN3414DRBR', '7', 'CAN OUT', '2'),
    ('net', 'CAN OUT', '3', 'GND'),
    ('join', 'TCAN3414DRBR', '7', 'DISPLAY CABLE', '3'),
    ('join', 'TCAN3414DRBR', '6', 'DISPLAY CABLE', '4'),
    ('net', 'DISPLAY CABLE', '1', 'GND'),
    # the display feed has its own resettable fuse (Bourns MF-MSMF050/24X: 24 V, 0.5 A
    # hold, 1 A trip)
    ('between', 'MF-MSMF050/24X', ('DISPLAY CABLE', '2'),
     ('NET', 'VIN')),
    # ESD2CAN24 (TI SLVSFW5D): 1 and 2 the bus lines, 3 GND
    ('net', 'ESD2CAN24DBZR', '1', 'CAN_H'),
    ('net', 'ESD2CAN24DBZR', '2', 'CAN_L'),
    ('net', 'ESD2CAN24DBZR', '3', 'GND'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '10', 'CAN_TX'),
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '20', 'CAN_RX'),
    # the display's open-collector outputs act as the power and reset buttons
    ('between', '100', ('DISPLAY CABLE', '5'), ('NET', 'PWR_BTN')),
    ('between', '100', ('DISPLAY CABLE', '6'), ('NET', 'ESP_EN')),
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
    comps, nets = load(path, source_names=True)
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
                for first, second in element_pins(part_ref):
                    got = {pin_net.get((part_ref, first)), pin_net.get((part_ref, second))}
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
                if pin_net.get((other_ref, far_pin(other_ref, other_pin))) == target_net:
                    found = True
            check(
                found,
                f'{value}.{rule[2]} has {rule[3]} to {rule[4]}.{rule[5]}',
            )
        elif kind == 'fetdrive':
            drain = pin_net.get((ref, rule[2]))
            found = False
            for fet_value, gate_pin, source_pin, drain_pin in NFET_ELEMENTS:
                for fet in refs_by_value.get(fet_value, []):
                    if (
                        pin_net.get((fet, drain_pin)) != drain
                        or pin_net.get((fet, source_pin)) != 'GND'
                    ):
                        continue
                    for other_ref, other_pin, _ in members.get(
                        pin_net.get((fet, gate_pin)), []
                    ):
                        if value_of[other_ref] != rule[3] or not other_ref.startswith('R'):
                            continue
                        far_net = pin_net.get((other_ref, far_pin(other_ref, other_pin)))
                        found = found or far_net == rule[4]
            check(
                found,
                f'{value}.{rule[2]} driven by BSS138, gate {rule[3]} to '
                f'{rule[4]}',
            )
        elif kind in ('each', 'eachjoin'):
            # every part of this value: its pin has the resistor to the rail ('each')
            # or to another pin of the same part ('eachjoin')
            bad = []
            for part_ref in refs:
                want = rule[4] if kind == 'each' else pin_net.get((part_ref, rule[4]))
                if not any(
                    value_of[other_ref] == rule[3] and other_ref.startswith('R')
                    and pin_net.get((other_ref, far_pin(other_ref, other_pin))) == want
                    for other_ref, other_pin, _ in members.get(
                        pin_net.get((part_ref, rule[2])), [])
                ):
                    bad.append(part_ref)
            check(not bad, f'every {value}.{rule[2]} has {rule[3]} to {rule[4]} '
                  f'(missing on {bad or "none"})')
        elif kind == 'res':
            net = pin_net.get((ref, rule[2]))
            found = False
            for other_ref, other_pin, _ in members.get(net, []):
                if value_of[other_ref] != rule[3] or not other_ref.startswith(
                    'R'
                ):
                    continue
                if pin_net.get((other_ref, far_pin(other_ref, other_pin))) == rule[4]:
                    found = True
            check(found, f'{value}.{rule[2]} has {rule[3]} to {rule[4]}')
        elif kind == 'nores':
            net = pin_net.get((ref, rule[2]))
            joined = [
                other_ref
                for other_ref, other_pin, _ in members.get(net, [])
                if other_ref.startswith('R') and pin_net.get(
                    (other_ref, far_pin(other_ref, other_pin))) == rule[3]
            ]
            check(not joined, f'{value}.{rule[2]} has no resistor to '
                  f'{rule[3]} (found {joined or "none"})')
    print(f'{len(rules) - failures}/{len(rules)} datasheet rules pass')
    return failures


if __name__ == '__main__':
    if sys.argv[1] == '--imu':
        sys.exit(1 if run(sys.argv[2], RULES_IMU) else 0)
    sys.exit(1 if run(sys.argv[1]) else 0)
