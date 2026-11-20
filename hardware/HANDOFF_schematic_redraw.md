# Schematic redraw handoff (branch `rev6-schematic-redraw`)

Drawing-only redraw of the rev 6 schematic to the rules in
`.claude/rules/hardware-schematic.md` and the `kicad-schematic-design` skill.
Worktree `.claude/worktrees/rev6-schematic-redraw`, off `rev6-schematic` (f86f43b).
Nothing is committed; the user reviews first. Sessions 1-4 (how the generator came to
work as it does, every earlier decision) are in
`hardware/archive/HANDOFF_schematic_redraw_history.md`; read its "Session 4" before
changing the root, the Universal IO parent or the board-rename tools.

## Hard limits

- Every net keeps its pins, references, values and footprints (`compare_netlists.py
  --strict --renamed`: 0 differences).
- The routed board may change in net names and footprint sheet links only ("as long
  as I don't need to re-route the board"). Copper and `cryocooler.kicad_dru` are
  frozen. Proof: the board equals `git show rev6-schematic:hardware/kicad/cryocooler.kicad_pcb`
  once every `(net "...")`, `(path "...")` and `(sheetname "...")` string is blanked.
- After **every** regeneration: `tools/rename_board_nets.py $B/base.net $OUT/new.net`,
  then `tools/relink_board_sheets.py $OUT/new.net`.

## User decisions that stand

- Plain net labels (never global) for a connection whose ends are over 85 mm apart;
  wires when closer. Buses only for communication buses (`{SPI}`).
- Pull resistors on the line they serve. Decoupling in its titled block.
- The four I/O channel sheets stay copies. Cold Head's ESD clamp keeps its four label
  pairs. io_core stays one sheet. The ten I/O sheets sit under `sheets/io.kicad_sch`.

## Gate (from `hardware/kicad`)

`$B/base.net`: netlist exported from a clean copy of `rev6-schematic`
(`git archive rev6-schematic hardware/kicad | tar -x -C <scratch>/clean`, then
`kicad-cli sch export netlist --format kicadsexpr`).

```bash
python3 tools/make_lib.py && python3 tools/gen_schematic.py     # every check line 0
$KC sch export netlist --format kicadsexpr -o $OUT/new.net cryocooler.kicad_sch
python3 tools/compare_netlists.py --strict --renamed $B/base.net $OUT/new.net   # 0 differences
python3 tools/rename_board_nets.py $B/base.net $OUT/new.net
python3 tools/relink_board_sheets.py $OUT/new.net
$KC pcb drc --schematic-parity --severity-all --format json -o $OUT/drc.json cryocooler.kicad_pcb
$KC sch erc --severity-all --format json -o $OUT/erc.json cryocooler.kicad_sch
python3 tools/datasheet_rules.py $OUT/new.net; python3 tools/verify_netlist.py $OUT/new.net
python3 tools/check_symbols.py cryocooler.kicad_sch; python3 tools/check_sheet_structure.py
python3 tools/count_crossings.py
```

Copy `cryocooler.kicad_sch` and `sheets/*.kicad_sch` aside before regenerating and
`cmp` afterwards to see which sheets changed. A sheet whose drawing changes order
needs an `OWN_UUID_SEQUENCE` entry (`tools/kicadgen.py`, value = ids it used at
`rev6-schematic`) or every later sheet's ids shift. Then the `schematic-reviewer`
subagent on the changed sheets.

Things that bit before: `--strict` catches resistor pins swapped after a part is
turned (keep pin 1 on the same net); a `FIELD_SIDES` side often lands on a neighbour,
so spread parts first; a part moved too close joins nets (session 5: the io_drivers
switch moved left shorted IO3_DRV to IO3_OUT_EN, caught by strict and ERC);
renaming a symbol's pins renames the unnamed nets on them (`Net-(J14-Pin_1)`).

## State (2026-11-20, end of session 5)

34 sheets. Strict with `--renamed` 0 differences (139 nets renamed with pins
unchanged); DRC with parity 0 / 0 / 0 and the 12 known warnings; ERC 0;
`datasheet_rules` 609/609; `verify_netlist` 497 parts / 379 nets; `check_symbols` 0;
generator check lines 0; structure counts global_label 0, close_label_pair 7,
unmatched_sheet_pin 0, too_many_parts 0, copied_sheet 2, wire_near_body 0;
`count_crossings` 1 (amp_current, accepted). Board equal to `rev6-schematic` with net,
path and sheetname strings blanked. Not opened in the KiCad GUI; "Update PCB from
Schematic" not tried; renders and fab files not regenerated (no net names in them).

### Session 5 (2026-11-20): what changed

- rails_logic: page in power-flow order (5 V buck, +5V/USB mux, 3.3 V buck), headings
  on all three, 3.3 V output caps spread so C3 / C5 / C30 / C87 text sits by its own
  part, the FB return runs under the output caps (the 23 mm detour is gone).
  `RAILS_MUX_ROW`, `RAILS_3V3_ROW`; rails_logic added to `OWN_UUID_SEQUENCE` (157).
- cold_head: U14's four right-side fan-out wires 2.54 mm apart (were 1.27 mm), C26
  moved right so C70's text sits on its right, clamp heading off U35.
- cooling: J3 / J4 moved 30 cells left (PWM runs about 83 mm, were 135 mm); +12V feed
  and C76 / C77 between the connector and the tach resistor; pump group 6 rows lower
  for white space; R15 / R16 text left of the resistor.
- power_button: R7 horizontal in the KILL line (was hanging like a pull-down), R56
  above the node; "12 V LOAD SWITCH" heading moved off the PWR_KILL label.
- gpio_expander: MCP23S08 symbol regrouped (GP0-GP7 left; SCK, SI, SO, CS together on
  the right, then INT and the RESET / A0 / A1 straps); one `{SPI}` stub (was two).
- imu: J14 has its own symbol `Conn_02x04_IMU_Cable` (pins named SCK, MOSI, MISO, ~CS,
  INT1, INT2, +3V3 on top, GND below; numbers unchanged) and stands level with the
  filter, so the six wires are straight. Six unnamed nets renamed on the board
  (`Net-(J14-Pin_1)` to `Net-(J14-SCK)` and so on). The IMU board's own schematic
  (`gen_imu_schematic.py`) still uses `Conn_02x04_Rails_At_Ends`.
- display: J15 text below the connector (was running into the Waveshare outline),
  DS1 text outside the outline, VIN feed an L instead of a U-turn, clamp heading
  "BESIDE J15 ON THE BOARD" (D101 is 0.5 mm from J15 on the PCB).
- io_precision / io_pressure: each signal runs straight on from its header pin (the
  5 mm jog is gone; precision IN- still steps down so the 100 nF fits across the pair),
  surge clamps moved to the connector end of the line, pressure filter caps spread,
  precision port PREC_EXC labels are plain net labels (one sheet pin at the switch).
- Text only: io_ch1-4 (input cap left of the 1M, R653 / R666 above, U116 / U119 left
  of the VCC riser), io_precision C423, io_pressure R637 / R639, indicators D13,
  rails_15v (C61 moved right of C62's text), supply_switches (bead headings higher),
  system_current (three headings), root (USB CC1 steps up 5 rows so R24's text sits
  above R24, off the D- wire).
- `tools/count_crossings.py` added to `hardware/kicad/README.md`.
- Opus `schematic-reviewer` pass on the 18 changed sheets, then its fixes: rails_logic
  FB climbs straight into the divider node; cooling PWM riser 2 cells right (RN1A /
  RN1C text clear), flow / NTC groups 8 rows lower; power_button R7 text below, R56
  left; gpio_expander dot on the A0 / A1 ground tie; precision ports A and B up 5 / 8
  rows (D106 off the border, PREC_EXC pair still 88 mm); io_ch1/2 U116 / U119 text
  left, R653 / R666 below; text moves on root C63, display R517 / R518, imu and
  system_current headings, indicators D13, supply_switches FB3 / FB4. Not re-reviewed
  after the fixes; the gate passes and the fixed spots were checked on renders.
  Reviewer notes not acted on: cold_head J10 flow (already open below); D6 on
  system_current is a two-colour LED with GA / GK unconnected (part-selection rule,
  a question for the user); rails_logic FB first drop beside U16's NC pins.

## Open

Ask the user (each reverses a decision or needs one):

1. ESD clamps as multi-unit symbols (one I/O unit on each line, ground on its own
   unit), so Cold Head's and Cooling's clamps can be wired with no labels and no
   crossings. Would replace "keep the labels".
2. rails_15v: U20's PVIN pins are on the symbol's left edge (the rule says supply pins
   on top); that is what removed seven crossings.
3. debug: D10 uses one die of a two-die LED (part-selection rule), and the rail LED is
   a second function on the test-point sheet.
4. io_switches' title names two functions; rails_logic holds three (5 V buck, mux,
   3.3 V buck).
5. Delete `sheets/aux_io.kicad_sch` (unreferenced) and the empty loop in
   `mcu_and_usb` (`for pin in ('A12', 'B1', 'B12'): pass`)?
6. display: wire CAN_H / CAN_L from U52 to J15 with D101 on the wires. Needs the
   TCAN3414 symbol's CANL above CANH (to match J15) and the 12 V feed and F2 moved
   off J15's pin rows. Today they are label pairs, legal at 99 mm.

Layout work still open (each needs its own layout change):

- Long wired runs (ends over 85 mm): io_drivers IO1_DRV / IO4_DRV (output switch too
  far right of the driver stages; moving it left onto the select lines shorted nets,
  so it needs the select lines re-planned), amp_current SPI_MOSI and ACS_CS, expansion
  EXP_MISO (about 115 mm), root SIG_SINE and CS_ADDR_D, Cold Head RTD_4 return.
- root: the chip-select chain runs right to left (decoder and buffer left of the
  ESP32); outputs on the left edge of IMU, Power Good and Power Button blocks; the
  PG_15V_N stub ends above the PGP_15V riser; U32's outputs grouped by function, not
  Y0-Y15; U51's ground under its NC pin.
- cold_head: J10 on the right of the ADC, so the measurement reads right to left.
- cooling: flow sensor and NTC blocks read right to left; spare RN2D sits in the NTC
  area; the +12V symbols sit below pin 2 (the tach wire holds the row above, a
  connector-order limit).
- expansion: three `{SPI}` stubs, two functions (RS-485 and the SPI header).
- compressor_relay / amp_control: LED GA / RK runs back under the LED body; J9's
  no-connect 1 mm from the sleeve ground.
- power_good: guard note below its circuit. Universal IO: PREC_EXC riser name rotated.
- Smaller notes from the reviewers: supply_switches' two bead blocks put the input
  rail name left of the symbol, the others above; ldo_15v PGN_15V drawn bidirectional
  while PGP_15V is an output; io_pressure pin-4 no-connect 2 mm from the pin-3 ground.
- For later, if tokens matter: the reference / value text items above are cosmetic and
  can be dropped from scope (the user's option, not taken yet).

Stale figures in other docs (the user fixes them separately):
`.claude/skills/kicad-schematic/SKILL.md` (rev 3 counts), `.claude/skills/kicad-pcb-edit/SKILL.md`
(DRC baseline 215), `hardware/kicad/README.md` "Review status" (634 connections).
