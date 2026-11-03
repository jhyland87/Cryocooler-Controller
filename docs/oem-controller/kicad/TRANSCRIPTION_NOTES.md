# KiCad transcription notes (US6098409 FIG 5A–6C)

Every anomaly, uncertainty and guess made while transcribing the schematics. Source pages are the 150 dpi renders in
[../US6098409/source-pages/](../US6098409/source-pages/) (PDF page = file number). The rules (refs and values as
printed, `?` for unprinted values, `Printed_Ref` / `Note` / `Probable_Part` fields) are in [README.md](README.md).

## Project-wide decisions

### Nets joined across figures (`ALIASES` in `tools/gen_oem_schematic.py`)
Each page that has one of these lists it in its title note. The label shows the name that was used, not the
printed name.

| Printed | On | Joined to | Why |
|---|---|---|---|
| `COOLER.MON` | 5H | `COOLER_MON` (5G U22 PE5) | Punctuation only |
| `ERR.WARMERS` | 5H | `ERR_WARNERS` (5G U22 PE2) | Misprint; same signal |
| `CS_CNTRL` | 5A | `CS_CTRL` (5B, 5H) | Misprint |
| `DEMAR_TEMP` | 5H | `DEWAR_TEMP` (5A) | Misprint |
| `RAM_SHUTO_T-` | 5E | `RAW_SHUTO_T-` (5B) | Misprint |
| `HOT TOTAL` | 5E | `NOT_TOTAL` (5C) | **[inference]**. 5C U33 drives `NOT_TOTAL` (TP1) and nothing reads it; 5E (pot reference input) and 5G (U22 PE4/AN4) read `HOT TOTAL`/`HOT-TOTAL` and nothing drives it. |
| `HOT-TOTAL` | 5G | `NOT_TOTAL` | Same as above |

### Kept apart on purpose
- **`HSP_CLK` / `HSP_PROG` / `HSP_READ` (5G-4)** are not misprints of `NSP_*`. They are the outputs of three U19
  HC04 inverters (pins 8/10/12), while U22 pin 1 drives `NSP_CLK` directly on the same figure. Joining them would
  short two outputs. **[inference]** They are an inverted copy of the pot bus. 5E prints its pot's PROG/READ inputs
  as `NSP_PROG-`/`NSP_READ-` (active low), which may be where they go; this is kept as `NSP_PROG`/`NSP_READ` as the 5E
  agent mapped it.
- **`ALIVE1..3` (5G, opto inputs)** vs **`FAM.ALIVE1..3` (5E, J8 pins 10/9/8)**: probably the same lines via the
  connector, but the names differ and nothing on the pages ties them, so they are separate.
- **NSP serial chain ends** `NSP_SER0`, `NSP_SER9` (5B), `NSP_SER5`, `NSP_SER8` (5D), `NSP_SER2` (5E) and `NSP_SERF`
  (5G U22 pin 81) each appear once. The daisy-chain order between figures is not printed.
- **Grounds.** The patent uses two ground symbols. 5A/5B map the filled-arrow symbol to `DGND`, 5G maps both
  styles to `GND`, and 5F uses `5F_GND_D` for its local digital return. These were left as the figure agents chose;
  treat any ground difference as uncertain.
- `POLARIZATION KEY` / `POLARIZING KEY` are connector keys, not nets.

### ERC results that are expected
`kicad-cli sch erc` on the root reports only these:
- `isolated_pin_label` (104): a label used on only one page, e.g. a signal that leaves the transcribed boards or
  a stub kept for a printed arrow.
- `power_pin_not_driven` (10): no PWR_FLAGs on a transcription.
- `pin_not_connected` (31): pins drawn with nothing attached. They are mostly on 5G (U22 spare pins, relay NC
  contacts, RS-232 spare channels, J10/J11 spare pins), plus J12 pin 9 (5F) and V2 pins 21/22 (5H).

`tools/verify_netlist.py` confirms KiCad's connectivity matches the specs exactly (2362 pins, 0 problems).

### Refs
- The patent reuses designators between figures. Such refs get a figure suffix (`R16_5D`) and keep the printed ref
  in `Printed_Ref`.
- Duplicates within one figure get `B`/`C` suffixes.
- Parts with no printed ref are named by figure plus role (`J5A1`, `UX1`, `RX1`, `U5G_MEM`, `6C_R?1`). The `?` refs
  pass ERC; rename them if annotation ever complains.

## Per figure

### FIG 5A (PDF p5), 46 parts
- The three connectors have no printed refs (`J5A1`/`J5A2`/`J5A3`).
- `BWT_4P` is printed on J5A3 pins 9 and 11, so they are shorted as drawn.
- Repeated pin numbers: U44B, U29, U17 (pin 10 printed three times).
- U56 supply pins are unnumbered. R276 has no value.
- Spare op-amp "+" signs are drawn on the fed-back input.
- The rack/tower option table is reproduced as page notes.
- `Probable_Part`: MC93 = MC14093B, MC04 = 74HC04/MC14069, LMC6-482 = LMC6482.

### FIG 5B (PDF p6), 35 parts
- U43A has two pins labelled V-.
- R296, C109 and C98 have no value. C108 is printed "10K".
- C90 appears twice. `R2-48` and `R2-49` have hyphenated refs.
- Repeated pins: U36 (13, 6), U29 (6).
- U29 O3 has an N/C mark but the line continues, so it is treated as connected.
- `NSP_SERO` is read as `NSP_SER0`.
- U29 is printed MC93 on 5A but MC2001 on 5B.

### FIG 5C (PDF p7–8, 5C-1 + 5C-2), 109 parts: overstroke back-off counter
- The two halves are joined by matching their 8 edge lines in order.
- The circuit is described in [../analysis/OVERSTROKE.md §2.3](../analysis/OVERSTROKE.md).
- Duplicates: R199, C155, C141, R285 (resistor and pot), C76, R194, R162.
- U26 is drawn both as an LT1124 and as a single op-amp pinout, so it is split into U26A/U26B.
- On the second U28 section, Q is printed as pin 3 and Cext as "OK".
- U33 V- goes to the R162/R187 node (as drawn).
- R266 is printed "221K(RM)/49.0K", R283 has no value, C49 is ".001SUF". CR10/CR11 are printed 1N4140.
- R163 is printed "XXX".
- Unlabelled arrows are kept as `5C_R126_ARROW` / `5C_R191_ARROW`.
- Dotted names kept: `WP.SHOSET`, `WP.SHTR`.
- **[assumption]** `HOG_T` is the knock/overstroke sensor channel.

### FIG 5D (PDF p9–11), 162 parts: six "butter warmer" heater drivers
- All six drivers have the same topology.
- Serial pot chains: `NSP_SERI`→V9→V7→V22→`NSP_SER5` and `NSP_SERI`→V24→V39→V51→`NSP_SER8`.
- Circuit #1's output is printed `BWT_1P` (the same as its input), and #4's input is printed `BWH_4P`. Both are
  shorts as printed. #5's output is `BWK_5P`.
- Duplicate refs: R78 ×3, R16, R3, R6, R176, R179. CR13/17/19 are printed 1N4140.
- The MC2030 GND pin is unnumbered. MC2030 is unidentified (a dual 1K serial digital pot).

### FIG 5E (PDF p12, drawn rotated), 38 parts
- Unref'd parts: RX1/RX2 (RX2 is probably R135), CX1–6, UX1 (an MC2030-family pot), UX2 (SPI device), UG1 (OR
  gate with bubbled inputs; pin 4 is printed on both an input and the output).
- No values on R35, R134, R136, R132, R270. There is no L3.
- `NSP_PROG-`/`NSP_READ-` are mapped to `NSP_PROG`/`NSP_READ` (see above).
- `+27URET` (probably +27VRET) and `99-` are kept as printed.
- Unlabelled down-arrows are kept as separate nets. U46 pin 4 and U10 V- are assumed to be -15V.

### FIG 5F (PDF p13–14), 72 parts: references and power
- Duplicates: C112, C130 ×3, C149, C159, U45, R229 ×3.
- Both input flags print "+27VINK(RM)/+48VINK(TM)". The return side is named `5F_VIN_RTN`.
- "+SUREF" is probably +5VREF (kept as printed).
- Regulators, the NPN, the fuse and the test points have no refs (UX1–4, QX1, FX1, TPX1–4).
- L0 and L7 are both printed +5V.
- R230's connection to +15V across the sheet edge is assumed. LT1007 V- is assumed to be pin 4.
- `Probable_Part`: URE319 = VRE310 (paralleled with AD2710).

### FIG 5G (PDF p15–18, 2×2 mosaic), 81 parts: microcontroller
- U22 is split into U22A (upper box) and U22B (lower box). Part number is printed `XXXXXXX XXX`.
- **ADC inputs (U22B):** PE7 RESERVED (35), PE6 PWR_MON (36), PE5 COOLER_MON (37), PE4 HOT-TOTAL (38),
  **PE3 BACK_OFF_COUNT (39)**, PE2 ERR_WARNERS (40), PE1 T.CLUSTER (41), PE0 SYS.CMD (42).
- **Relays:**
  - ALARM- on pin 27 → U30 → K3 (`FAULT_O`/`FAULT_NO`).
  - LNA_AMP_PWR on pin 30 → K1 (`LNA_SW_PWR` → J10 VDD-1..6).
  - RF_BYPASS on pin 31 → K2 (+27VIN → J11).
- Many duplicate or missing pin numbers; for example, all data pins are printed "62".
- Unlabelled parts: the ALIVE optos, the memory (PSD-type, `U5G_MEM`), the RS-232 chip (`U5G_232`, MAX232-like) and
  the fuse.
- `Probable_Part`: U22 = 68HC11K family, U21B "D61232" = DS1232, U30 = DS3658, UR1 = LM317 (~3.4 V).

### FIG 5H (PDF p19–21), 78 parts: sensor muxes and monitors
- V12 pins 6 and 7 are separate nets. The AD590 has a third (case) lead.
- V+ is printed as pin "0" (probably 8). R51/R48 are printed "1.000K .1v".
- Duplicates: R57, R59 ×3, R48, R43, C19, V13 (printed both LT1124 and LM06482).
- D6496 (= DG506A): pin 19 is labelled "A4", GND is "L2", and the D pin is printed "XX".
- `MM(8)` is probably `MM(2)` (kept as printed).
- Placeholder values XX.XK, XX.K and CNET are kept. The "XXX" flag is kept local.

### FIG 6A / 6B (PDF p22–25), 94 + 94 parts: daughter-board sensor amplifiers
- Every channel output is printed `CBY_1`, which is a drafting error. It is kept, so in KiCad all those outputs share
  one net.
- 6B joins the V17 and V18 outputs (`REF_3`/`REF_4` are one conductor, named `REF_4`).
- The J8 channel is wired differently from the others.
- The LTC1150 pin 5 stub is left out. The LT1007 output is printed as pin 8.
- Duplicates: C2 ×3, C19, R13, R25, C30 (6A); R43, C50, C49 (6B).

### FIG 6C (PDF p26), 22 parts
- No values printed for R63/69/73/74/80 or C71/74/77.
- U20 pins are assumed. There is a second, unlabelled op-amp stage (`6C_OPA2_AUX`).
- The J15 key is spelled "POLARIZATION KEY". J10 pins 17–20 are unnamed (`6C_J10_17..20`).
- R54 and J10 also appear on other figures, so they get suffixes.
