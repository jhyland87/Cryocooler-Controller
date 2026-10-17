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
RULES = [
    # EMC2303: ADDR_SEL decoded from a pull-up (33k -> 0x4D), CLK pull-up sets
    # default drive, PWM open-drain pull-ups
    ('res', 'EMC2303-x-KP', '4', '33k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '9', '4.7k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '5', '10k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '7', '10k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '6', '4.7k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '8', '4.7k', '+3V3_COOL'),
    ('res', 'EMC2303-x-KP', '10', '10k', '+3V3_COOL'),
    ('net', 'EMC2303-x-KP', '3', '+3V3_COOL'),
    ('net', 'EMC2303-x-KP', '13', 'GND'),
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
    ('net', 'SG-8002CA-PH 25MHz', '4', '+5V'),
    ('net', 'SG-8002CA-PH 25MHz', '2', 'GND'),
    ('net', 'SG-8002CA-PH 25MHz', '1', '+5V'),
    # ADP7182: EN must be |VEN| >= 2 V (tied to VIN), never ground
    ('same', 'ADP7182AUJZ', '2', '3'),
    ('net', 'ADP7182AUJZ', '2', '-16V5'),
    ('net', 'ADP7182AUJZ', '1', 'GND'),
    ('net', 'ADP7182AUJZ', '5', '-15V'),
    ('res', 'ADP7182AUJZ', '4', '113k', '-15V'),
    ('res', 'ADP7182AUJZ', '4', '10k', 'GND'),
    # ADP7142: EN tied to VIN, VOUT = 1.2 V x (1 + R1/R2)
    ('same', 'ADP7142AUJZ', '1', '3'),
    ('net', 'ADP7142AUJZ', '1', '+16V5'),
    ('net', 'ADP7142AUJZ', '2', 'GND'),
    ('net', 'ADP7142AUJZ', '5', '+15V'),
    ('res', 'ADP7142AUJZ', '4', '115k', '+15V'),
    ('res', 'ADP7142AUJZ', '4', '10k', 'GND'),
    # ADP5071 (datasheet Fig. 47)
    ('net', 'ADP5071AREZ', '17', '+5V_PS15'),
    ('net', 'ADP5071AREZ', '18', '+5V_PS15'),
    ('net', 'ADP5071AREZ', '19', '+5V_PS15'),
    ('net', 'ADP5071AREZ', '9', '+5V_PS15'),
    ('net', 'ADP5071AREZ', '11', '+5V_PS15'),
    ('net', 'ADP5071AREZ', '4', 'GND'),
    ('net', 'ADP5071AREZ', '1', 'GND'),
    ('net', 'ADP5071AREZ', '15', 'GND'),
    ('res', 'ADP5071AREZ', '7', '2.67M', '+16V5'),
    ('res', 'ADP5071AREZ', '7', '137k', 'GND'),
    ('resjoin', 'ADP5071AREZ', '13', '118k', 'ADP5071AREZ', '14'),
    ('res', 'ADP5071AREZ', '13', '2.55M', '-16V5'),
    # J14: off-board Adafruit LSM6DSOX module. Pins 1-8 follow the module's
    # pads (Vin, GND, SCL, SDA, DO, CS, INT1, INT2); its 3Vo pad is not
    # wired. Vin = 3.3 V keeps the module's logic at 3.3 V. Each signal has a
    # 100 R series resistor next to the connector; CS keeps a 10 k pull-up on
    # the board side so it idles high with the cable unplugged.
    ('net', 'IMU LSM6DSOX module', '1', '+3V3'),
    ('net', 'IMU LSM6DSOX module', '2', 'GND'),
    ('between', '100', ('NET', 'SPI_SCK'), ('IMU LSM6DSOX module', '3')),
    ('between', '100', ('NET', 'SPI_MOSI'), ('IMU LSM6DSOX module', '4')),
    ('between', '100', ('NET', 'SPI_MISO'), ('IMU LSM6DSOX module', '5')),
    ('between', '100', ('NET', 'IMU_CS'), ('IMU LSM6DSOX module', '6')),
    ('between', '100', ('NET', 'IMU_INT1'), ('IMU LSM6DSOX module', '7')),
    ('between', '100', ('NET', 'IMU_INT2'), ('IMU LSM6DSOX module', '8')),
    # supply jumpers: pin 1 on the main rail, pin 2 on the switched rail
    ('net', 'EN SG3', '1', '+3V3'),
    ('net', 'EN SG3', '2', '+3V3_SG'),
    ('net', 'EN PS15', '1', '+5V'),
    ('net', 'EN PS15', '2', '+5V_PS15'),
    ('net', 'EN ISO5', '1', '+5V'),
    ('net', 'EN ISO5', '2', '+5V_ISO'),
    ('net', 'EN COOL', '1', '+3V3'),
    ('net', 'EN COOL', '2', '+3V3_COOL'),
    ('net', 'EN CH', '1', '+3V3'),
    ('net', 'EN CH', '2', '+3V3_CH'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '39', '10k', '+3V3'),
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
    ('net', 'OPA188ID', '7', '+15V'),
    ('net', 'OPA188ID', '4', '-15V'),
    ('net', 'OPA1656ID', '8', '+15V'),
    ('net', 'OPA1656ID', '4', '-15V'),
    ('net', 'MCP4921-E/SN', '1', '+3V3_SG'),
    ('net', 'MCP4921-E/SN', '5', 'GND'),
    ('net', 'MCP4921-E/SN', '7', 'GND'),
    ('res', 'MCP4921-E/SN', '6', '6.8k', '+3V3_SG'),
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
    ('res', 'INA239AIDGSR', '1', '10k', '+3V3'),
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
    ('res', 'ADS1220IPW', '2', '10k', '+3V3'),
    ('res', 'ADS1220IPW', '14', '10k', '+3V3_CH'),
    # SC18IS604 (SPI to I2C bridge, NXP rev 1.0 TSSOP16): VDD and VREFP on
    # 3.3 V, VSS on GND, CS/RESET/INT# pulled up, I2C pull-ups, MISO gated by
    # a 74LVC1G125 whose OE# follows CS
    ('net', 'SC18IS604PW', '12', '+3V3_COOL'),
    ('net', 'SC18IS604PW', '15', '+3V3_COOL'),
    ('net', 'SC18IS604PW', '13', 'GND'),
    ('net', 'SC18IS604PW', '8', 'BRIDGE_CS'),
    ('net', 'SC18IS604PW', '11', 'SPI_SCK'),
    ('net', 'SC18IS604PW', '10', 'SPI_MOSI'),
    ('net', 'SC18IS604PW', '4', 'BRIDGE_RESET'),
    ('res', 'SC18IS604PW', '8', '10k', '+3V3'),
    ('res', 'SC18IS604PW', '4', '10k', '+3V3'),
    ('res', 'SC18IS604PW', '3', '10k', '+3V3_COOL'),
    ('net', 'SC18IS604PW', '1', 'SDA'),
    ('net', 'SC18IS604PW', '2', 'SCL'),
    ('res', 'SC18IS604PW', '1', '4.7k', '+3V3_COOL'),
    ('res', 'SC18IS604PW', '2', '4.7k', '+3V3_COOL'),
    ('join', 'SC18IS604PW', '1', 'EMC2303-x-KP', '1'),
    ('join', 'SC18IS604PW', '2', 'EMC2303-x-KP', '2'),
    ('join', 'SC18IS604PW', '14', '74LVC1G125', '2'),
    ('net', '74LVC1G125', '1', 'BRIDGE_CS'),
    ('net', '74LVC1G125', '4', 'SPI_MISO'),
    ('net', '74LVC1G125', '5', '+3V3_COOL'),
    ('net', '74LVC1G125', '3', 'GND'),
    ('nc', 'SC18IS604PW', '9'),
    ('nc', 'SC18IS604PW', '16'),
    ('nc', 'SC18IS604PW', '7'),
    ('nc', 'SC18IS604PW', '6'),
    ('nc', 'SC18IS604PW', '5'),
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
    ('between', 'SRN6045TA-4R7M', ('AP63205WU-7', '5'), ('NET', '+5V')),
    ('between', '100nF', ('AP63205WU-7', '6'), ('AP63205WU-7', '5')),
    ('net', 'LD1117S33TR', '3', '+5V'),
    ('net', 'LD1117S33TR', '2', '+3V3'),
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
    ('nc', 'ESP32-S3-WROOM-2-N32R16V', '25'),
    # ACS_CS is on GPIO17 (module pin 10), not GPIO43 / U0TXD (pin 37), which
    # toggles with ROM boot messages
    ('net', 'ESP32-S3-WROOM-2-N32R16V', '37', 'UART0_TX'),
    ('res', 'ESP32-S3-WROOM-2-N32R16V', '10', '10k', '+3V3'),
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
