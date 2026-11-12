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
