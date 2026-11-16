# [11/01/2026] Board testing results
- [x] R45 needed to be changed from 55k to 22k in parallel with a 1nF ceramic capacitor — done (22k ∥ 1 nF)
  - Superseded: 51k on the rev 1 board measured 10.3 Vpp at 10 V in, so R45 is now 47k + R122 2.4k in series, trimmable by swapping R122 (1 nF kept across both)
  - More details on this can be found in chat: https://claude.ai/chat/9b111fed-44a9-41c4-91a6-cf42005338c9
- [x] Labeling the test points with names that describe what the point is testing, instead of just TP# would have helped. — done (test points print their net name)
- Some extra test points could have been of use:
  - [x] The ±15v test points should be in the ±15v rails section, ideally close to the regulators — done (+15V, −15V, +16V5, −16V5 beside U20 / U21)
  - [x] The sine wave coming out of the DDS IC — done (TP37 `DDS`)
- [x] The 1.27mm pitch jumpers were a mistake, they should have been 2.54mm pitch — done (Keystone 5110 0603 jumpers JP1–JP5)
  - For future boards, instead of using through-hole headers for the jumpers, use the 0R jumpers found here: https://www.keyelco.com/userAssets/file/K75p60.pdf (Digikey items 36-5110CT-ND (for 0603), 36-5106CT-ND (for 0805), 36-5108CT-ND (for 1206))
- [x] The white LEDs are way too bright. Switch them with something dimmer. Maybe green for when they're in a good state. — done (0402 Kingbright, green = good, red = fault)
- [x] The +15V LED is labeled, there is no -15V next to the other LED. — done (D13 `-15V`)
- [x] Feel free to use discrete components as small as 0402 to save space. — done
- [x] Incorporate the improvements we made in the lt3097_power_good branch, as well as other changes: — done (LT3097, LT8582, PG pins to the SC18IS604 GPIOs)
  - Switch to LT3097
  - Switch to the LT8582 instead of the ADP5071AREZ so we can use the power good pin as an indicator.
  - Tie the power good pins of the LT3097 and LT8582 to GPIO pins on the ESP32 so we can programatically handle the faults.
- [x] Add a 0.5mm pitch 14 pin FPC connector horizontally to the top side of the PCB near the back of the PCB. This will be used to connect it to the touchscreen same one as whats found on the "UCS 125-87-F-GD-D2,4-TRG 9005" enclosure by Phoenix Contact.)  This uses a 4-wire SPI half duplex interface. Do wire this up to the ESP32 and have it output just very basic text for now. We can spice up the UI later. — done (J15 Hirose FH12-14S on the top edge, top side; display firmware prints basic text)
- [x] Lets try the 145x125 enclosure again since were now ok using 0402 components. A refresher for the PCB size can be found at: dev/pxc_2203448_01_00_UCS-145-125-F-CCD-9005_PCB2D_UCS-PCB-145-125.pdf — done (120 x 100 board, UCS-PCB-145-125 outline)
- [x] If you're running low on space when making this, then you can start to forfeit some LED's and/or test points. Even omitting some of the SMD component labels is ok if necessary. — used: refs hidden where crowded, 2 section names and some ESP32 pin names dropped
- [x] Be sure to use both sides of the board adiquately. Your last attempt on this PCB had all but a few components on one side, which made for a difficult time. — done
- [x] For the connection to the IMU, use surface mount RJ45 that has 8 leads, since the IMU also just uses 8 positions, this should help free up some room. Pick something like one of the following: — done (Amphenol RJSSE-5380: the three linked parts have magnetics, so a plain 8P8C was used)
  - https://www.digikey.com/en/products/detail/kycon-inc/GLPLX-SMT-188S7-QQ-Y-G/9990208
  - https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/7498111120AR/17737783
  - https://www.digikey.com/en/products/detail/ease-electronics/AAOE-8P8C-10610/21736317
- [x] The plug the cryocooler uses has 3 pins since its normally connected to a 3 pin socket that outputs AC voltage from a variac. Hot, Live and Ground. The amplifier output only has the + and - pins, so we need a 2 pin connector for the amplifier to connect to, then the + and - get ran through the ACS37800, and then it needs to connect to a three pin connector for the cryocooler. The 3rd pin should connect to ground.  — done (J11 2-pin from amp, J12 3-pin to cryocooler with pin 3 on GND)
- [x] The PCB should be blue. — done
- [x] Again, the board in this branch needs to be optimized to use both sides of the PCB, its pretty crowded on one side and baren on the other. — done

# Deferred (do only when needed)

- [x] **Free GPIO 11, 12, 13 and 17 by moving the ACS37800 (U18) onto the shared SPI bus.** — done on
  `ucs-125-87-rev4` for GPIO 11, 12 and 13. CS stays on GPIO17: U32 has no spare output. A second
  gate on SCK was added (see `kicad/DESIGN_REVIEW.md`, rev 4). Not bench tested.
  Only worth doing if we run out of GPIO. U18 keeps driving MISO while its CS is high,
  which is why it has its own SPI3 bus (`include/config/pin_config.h`, `docs/acs37800.md` gotcha 5).
  - Add a 74LVC1G125 tri-state buffer on U18's MISO. Its /OE is active-low, so the
    ACS37800 CS drives it directly (no inverter). The SC18IS604 MISO used the same trick.
  - Put the buffer on the ESP32 side of the U17 isolator: U17's MISO output also drives
    all the time. Take /OE from the ESP32-side CS.
  - Route SCLK/MOSI from the shared bus (GPIO 42/41) through U17, and the buffered MISO
    to GPIO 40. CS can move to a spare decoder ID (U32, IDs 100-107) or stay a GPIO.
  - Firmware: drop the SPI3_HOST bus and use the shared `SPIClass` with LSBFIRST, SPI mode 3,
    one 40-bit frame per CS. Keep the `primeSPI()` idle-clock fix: on a shared bus,
    mode changes between devices make the first-frame shift more likely (gotcha 4).
  - Verify every part and pin against its datasheet before changing the schematic.

# [11/15/2026] INA239 sense routing: check this board
- [ ] **Not yet checked on rev 4.** The bench board on the `main` line read system current about
  2.9x high because its INA239 sense lines tap the 12 V copper away from the shunt pads (details
  under "Rev 5 ideas" below and in `hardware/TODO.md` on `main`).
  - Check the rev 4 layout: both sense lines must start on the shunt's own pads and carry no
    load current.
  - Check a built rev 4 board: compare the dashboard's system amps with a multimeter in series
    in the 12 V lead. If they differ, measure millivolts across the shunt end caps and at the
    shunt-side pads of the filter resistors.
  - The firmware correction on `main` (effective shunt value in `src/modules/sysinfo.cpp`) was
    measured on that one board and is deliberately not ported here.

# Rev 5 ideas (only if there is ever a rev 5)

- [ ] **Kelvin-connect the INA239 shunt sense lines.** On the bench board (the `main` line) the
  system current read about 2.9x high: 0.60 A shown for 0.21 A real.
  - Measured there at 0.21 A: 2.7 mV across the 15 mΩ shunt's end caps, but 8.3 mV where the
    sense lines pick up the signal. The sense lines tapped the 12 V copper away from the shunt
    pads, so the supply current's drop in about 25 mΩ of copper was measured as shunt voltage.
  - Rule: both sense lines start on the shunt's own pads (inside edge) and run as a thin
    dedicated pair carrying no load current, straight to the filter resistors. Give the shunt
    a 4-terminal footprint or net-tie the sense nets so the router cannot join them elsewhere,
    and check the routed board before ordering.
  - Also: do not hang VBUS on the filtered IN− line. Its 12 µA through the 49.9 Ω filter
    resistor adds 0.6 mV (0.04 A at 15 mΩ). Take VBUS from the rail directly, or use 10 Ω.
  - A larger shunt value makes stray copper matter less; the cost is more drop and heat.
  - Firmware on `main` works around it with a measured effective shunt value
    (`src/modules/sysinfo.cpp`); see `hardware/TODO.md` on `main`, 11/15/2026.
- [ ] **Auto power-on.** Let the system turn on as soon as 12 V reaches the board, with no button
  press. Maybe enabled by a jumper, or in software if that is possible.
  - Idea: a 2.2 µF capacitor from the LTC2954 PB pin to GND, with a jumper in series. PB's
    internal 100 k pull-up (to 1.9 V) charges it, so PB is low for roughly 80-500 ms after 12 V
    arrives and high from then on. Holding the button still forces power off (6.4 s on PDT).
  - Assumed, not bench tested: PB held low for 32 ms from power-up counts as a turn-on, even
    though PB never starts high (the datasheet also describes turn-on as a high-to-low
    transition). Test on rev 4 with a capacitor across SW3.
  - Open: a short 12 V interruption may not discharge the capacitor, so there would be no pulse
    when power returns. A diode from PB to VIN might fix that.
- [ ] **Move J12 (cryocooler output) and J14 (IMU) closer together**, since both cables go to the
  cryocooler. Ideally directly opposite each other, on the two sides of the board.
  - J12 is the isolated 120 VAC section with its clearance barrier and J14 is low-voltage SPI.
    The same edge is fine, but J14 has to stay outside the barrier.
  - The two cables would then run side by side to the cooler, so consider a shielded IMU cable.
- [ ] **Move J5 (flow sensor) and J6 (NTC) closer together**: the NTC and the flow sensor are in
  the same device.
  - Adjacent headers keep the stock cables. If the Alphacool unit's two plugs allow it, one
    6-pin connector would also work (not checked).
- [ ] **GPIO output level set in software.** Possibly let each GPIO header drive up to 3.3 V, 5 V
  or 12 V, chosen by a software setting, so it can switch devices that need different levels
  (the air compressor needs a 12 V "enable" signal, for example).
  - Idea: one circuit for this and the analog outputs below. A DAC on the SPI bus feeds an
    op-amp stage run from the +15 V rail, giving 0-12 V per channel. A digital output is that
    channel driven to zero or to its configured ceiling.
  - Limit: an op-amp output sources only tens of milliamps. Enough for an enable signal, not
    for powering a load.
  - Safety: a wrong setting could put 12 V into a 3.3 V device. Default every channel to off
    and 3.3 V at boot, and show the configured level on the dashboard.
  - If the headers stay usable as inputs, their protection has to survive 12 V applied from
    outside.
  - No parts chosen or checked against a datasheet yet.
- [ ] **Drop J8 (amp remote) and J13 (compressor relay).** With configurable GPIO outputs they
  can go away: each becomes a GPIO output set to 12 V.
  - J8 is interlocked in hardware today: REM only switches on while both ±15 V rails are good.
    The firmware already reads the ±15 V power-good signals (`src/modules/amplifier.cpp`), so
    the interlock moves to software: the output may only be enabled while both rails are good.
    Unlike the hardware one, a software interlock does not act if the firmware hangs.
  - J13 drives a relay coil at up to 130 mA with a flyback diode. That is more than an op-amp
    output stage sources, so the GPIO output it moves to needs a stronger driver and the diode.
- [ ] **Analog outputs follow that setting**: an analog output should cover the range up to the
  voltage configured for it.
  - With the DAC and op-amp stage above, this is the same output set anywhere between zero and
    the ceiling, with the ceiling enforced in software.
