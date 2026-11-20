# Schematic redraw: history (sessions 1-4, to 2026-11-20)

Moved out of `hardware/HANDOFF_schematic_redraw.md` on 2026-11-20 (session 5) so the
handoff stays short. Newest first. Decisions recorded here still stand unless the
handoff says otherwise; figures here are as they were at the time.

## Pick up here, as written at the end of session 4

Everything below this section is history, newest first. Read this section, then
"Session 4" for how the generator works now. Nothing is committed; the user decides
when.

**Rules in force** (the user's, also in `.claude/rules/hardware-schematic.md` and
the design skill, both rewritten on 2026-11-20):

- Plain net labels, never global, for a connection whose ends are more than 85 mm
  apart; a wire when they are closer. No bus except a communication bus (`{SPI}`).
- Pull resistors on the line they serve. Decoupling in its titled block.
- The board may change in net names and footprint sheet links only. After **every**
  regeneration: `python3 tools/rename_board_nets.py $B/base.net $OUT/new.net` then
  `python3 tools/relink_board_sheets.py $OUT/new.net`.
- User decisions that stand: channel sheets stay copies; Cold Head's ESD clamp keeps
  its four label pairs; io_core stays one sheet; the block grid order.

**State:** 34 sheets, all gated: strict with `--renamed` 0 differences (133 nets
renamed with pins unchanged), DRC parity 0 / 0 / 0 with the 12 warnings, ERC 0,
609/609, 497 / 379, check_symbols 0, generator check lines 0, structure counts
global_label 0, close_label_pair 7, wire_near_body 0, too_many_parts 0,
copied_sheet 2. `python3 tools/count_crossings.py`: 1 (amp_current, accepted).

**Gate** (from `hardware/kicad`; `$B/base.net` is the netlist exported from a clean
copy of `rev6-schematic`, see "Baseline and gate"; the board itself is no longer
compared with `git diff`, see the board proof in "Session 4"):

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

Before regenerating, copy `cryocooler.kicad_sch` and `sheets/*.kicad_sch` aside and
`cmp` afterwards, to see that only the intended sheets changed. Then the
`schematic-reviewer` subagent on the changed sheets.

**Where the last pass stopped.** Two reviewers went over the fourteen sheets not
reviewed before and over the last round. No crossings, 4-way points or wire-near-body
faults anywhere. Applied from their reports, gated, **not re-reviewed**: cold_head
(note corrected, headings, C70 / R62 text, REFP0 turn moved a cell), imu and
indicators and cooling and power_button headings, cooling's clamp labels made plain
net labels, debug (empty heading gone, rail test points start under their heading),
display (both button lines drawn alike, decoupling block lower), precision and
pressure clamps two cells higher, rails_15v (notes cut to the converter, rail symbols
at the output end, C61 moved), ldo_15v (LT3094 bottom pins moved off SET),
system_current (bulk cap moved right), `FIELD_SIDES` entries for about 60 parts.

**Still open from those two reports** (do these next; each is small unless marked):

- Text beside the wrong part where setting a side collided with a neighbour, so the
  parts need spreading first: rails_logic C3 / C5 / C30 / R94 / R34 (move C30, the
  R94 / R34 divider and C87 two cells right); io_pressure R636 to R639 and
  io_precision R630 / R632 (the TVS ground still crowds the series resistor: move
  the clamp to the connector end of the line); the channel sheets' R656 / C440 pair
  and io_precision's R626 / C423 pair (cap two cells further from the 1M); rails_15v
  C62; cooling R15 / R16 (reference touches the "+3V3" name); display R517 / R518
  (R517 below, R518 above); io_ch U116 reference.
- rails_logic: U16's FB wire detours 23 mm under R34; three sub-circuits without
  headings; the power mux drawn below the stage it feeds.
- display: D101's heading says "at the connector" but it is joined by labels 109 mm
  away. Wiring it at J15 needs the feed wire to the fuse rerouted first (the CAN
  risers would cross it). J15's value text runs into the Waveshare outline.
- gpio_expander: SO is on the right of U25, away from CS / SCK / SI, so the sheet
  has two `{SPI}` stubs; and the seven GP inputs leave on the right. Regroup the
  MCP23S08 symbol (SPI pins together, GP inputs on the left).
- io_pressure: PRESSn_PIN has a 5 mm jog; put the filter row at the header pin's
  height. io_drivers: IO1_DRV and IO4_DRV wires are about 99 and 91 mm end to end
  (tighten the stage pitch or move U104).
- amp_current: SPI_MOSI is one 94 mm wire. expansion: EXP_MISO about 115 mm; three
  `{SPI}` stubs; two functions.
- imu: J14's pins are named `Pin_n` and drawn out of order.
- **Ask the user** (each reverses or needs a decision):
  1. ESD clamps as multi-unit symbols (one I/O unit on each line, ground on its own
     unit): the reviewer's way to wire Cold Head's and Cooling's clamps with no
     labels and no crossings. Pin numbers stay. It would replace "keep the labels".
  2. rails_15v: U20's PVIN pins are on the symbol's left edge, where the rule says
     supply pins go on top; that is what removed the seven crossings.
  3. debug: D10 uses one die of a two-die LED, which the part-selection rule
     forbids; and the rail LED is a second function on the test-point sheet.
  4. io_switches' title names two functions; rails_logic holds three.
  5. `sheets/aux_io.kicad_sch` (unreferenced) and the empty loop in `mcu_and_usb`:
     delete?
- The older "for later" list under "Final state of this session" below.

## State (2026-11-19)

### Session 4 (2026-11-19): net labels instead of trunks on the root, 38 nets renamed on the board

Baseline re-exported from `rev6-schematic` (f86f43b), equal to `HANDOFF_rev6.md`.
Nothing committed.

**The user changed three standing decisions this session. Each reverses something
written further down; the older sections are history.**

1. After a first version with buses and long wires: "You can use net labels for
   connections instead of going across the full sheet. The BUS is for communication
   busses such as SPI, I2C, etc."
2. Asked whether the trunks from sessions 2 and 3 should follow: "Yes, labels too".
3. After a version with global labels at both ends: "I said NET labels, not global
   labels". Told that net labels on the root rename the nets on the board, the user
   chose **"Rename nets on the board"**, "as long as i dont need to re-route the
   board". **So `cryocooler.kicad_pcb` is no longer frozen for net names.** It is
   still frozen for everything else: pins, references, values, footprints, copper.

What the root looks like now:

- The only bus is `{SPI}`. No trunks.
- Ends more than 85 mm apart: a net label on the wire at the ESP32 or 74HC154 pin
  and one at the block's sheet pin (`LABEL_LINKED`, `end_label()`, `pin_tag()`).
  The wire runs the length of the name and the label closes its far end (a loose
  wire end fails ERC). Covers the 14 chip selects, IMU_INT1 / IMU_INT2, PG_15V_N,
  PWR_INT, PWR_KILL, COMP_RELAY_EN, STATUS_RGB, CAN_TX, CAN_RX, the six cooling
  nets, and CS_ADDR_A / B / C and CS_EN_N between the ESP32 and the decoder.
- Ends within 85 mm are wires with one net label: AMP_REM_EN, CS_ADDR_D_1V8 (ESP32
  to the bit-D buffer, R514 on it), CS_ADDR_D (buffer to the decoder), DDS_SINE and
  SIG_SINE (Signal Generator to Debug; SIG_SINE runs on under Debug to Amp Control).
- 74HC154 symbol: right side is E0, gap, A0 to A3, gap, E1, so the enable pull-up
  R18 and the strap resistors R17 (A0, up) and R19 (A2, down) hang on the decoder's
  own wires without crossing. The STRAP AND IDLE BIAS group is gone.
- Water Cooling's block is 16 cells tall for six pins (`BOX_HEIGHT`). IMU's three
  pins are on its left edge.
- Still global on the root, not converted yet: AUX_IO5 / 7 / 11 / 13, ESP_EN,
  ESP_BOOT, USB_VBUS (`ROOT_LOCAL` lists what is local).
- Child sheets: signal_gen and imu lost their hierarchical buses (two labels each).
  Label kinds only on cooling, display, debug, power_good, power_button, indicators,
  amp_control. compressor_relay: enable is a sheet pin and the LED is wired like
  amp_control, so `rem_switch(redrawn=)` is gone (`rg_led(labels=)` stays); D14
  moved 2 cells left. On cooling the ESD clamp's four nets carry a second
  hierarchical label each (a label pair, as before); wire it at that sheet's redraw.
  The seven sheets first touched this session are in `OWN_UUID_SEQUENCE`.
- Removed as unused: `bus_entry`, `trunk_taps`, `trunk_entry`, `SIGNAL_CS_ROW`,
  `DECODER_RUN`, the bus aliases other than `SPI` with their directions and
  descriptions. `name_tag()` stays for ACS_SCK / ACS_MISO on amp_current.

**The board rename.** 38 nets went from `NAME` to `/NAME` (the full list is what
`compare_netlists.py --strict` prints against the `rev6-schematic` baseline). In
`cryocooler.kicad_pcb` every `(net "NAME")` of those 38 was replaced by text, 1223
occurrences, nothing else: putting the old names back gives the pre-rename file byte
for byte (checked), so no pad, track, via or zone moved. `cryocooler.kicad_dru` names
none of them and is unchanged. Net class patterns gained the `/NAME` forms
(`class_patterns()`). Not re-run and not checked: the board renders and fab files
(net names do not appear in them), and the older one-off board scripts that name
nets (`cs_decoder_board.py`, `cs_decoder_finish.py`, `connector_moves.py`,
`hand_route.py`, `rev3_board.py`, `wall_jacks.py`): they still use the old names.
The firmware does not use net names. Not opened in the KiCad GUI.

Rules that follow from KiCad (tested by export, KiCad 10):

- A net label on the root names the net `/NAME`; a global label names it `NAME`.
- A net label may not share its name with a global label anywhere in the project
  (ERC `same_local_global_label`), so convert a net on every sheet in one step and
  rename it on the board in the same step.
- A wire end that touches nothing fails ERC (`unconnected_wire_endpoint`): end a
  label's wire on the label.

**Gate from now on** (replaces step 2 of "Baseline and gate"; the rest is as before):

- `python3 tools/compare_netlists.py --strict --renamed $B/base.net $OUT/new.net`:
  0 differences. It also prints how many nets kept their pins under a new name
  (`--list` shows them); nothing else is accepted.
- Board file: `git diff` shows the net renames only until this is committed. After a
  further rename, prove it the same way (undo the names in a copy, compare with the
  file before).
- DRC with parity 0 / 0 / 0 and the 12 warnings; ERC 0; `datasheet_rules` 609/609;
  `verify_netlist` 497 / 379 with no mismatch; `check_symbols` 0; generator check
  lines 0. All pass now.
- `check_sheet_structure`: global_label 212 (was 255 at the start of the session),
  close_label_pair 45 (51), wire_near_body 10; baseline file updated to 212.

Not done:

- `.claude/rules/hardware-schematic.md` and the design skill still say "the root
  sheet wires the sheet pins together" and never mention the 85 mm label rule on
  the root or "buses only for communication buses". Not edited: the wording is the
  user's.
- PG_15V_N stays on the module's left side (with labels its side no longer matters).

Reviewer on the net-label root (third pass, 2026-11-19): the label conversion
passes (all labels on their own wires, no crossings, no 4-way points, pull-ups above
and pull-downs below). Fixed after it: CS_ADDR_D named on the A3 stub and
CS_ADDR_D_1V8 at the IO47 pin; EXPANDER_CS and IO_DAC_CS / IO_ADC_CS moved to the top
pin rows of their blocks; ESP_BOOT flag moved to the left end of the IO0 wire (SW2's
text had landed on it); U2's ground drops straight; headings for the buttons and the
USB group; buffer notes moved up. Tried and taken back: standing the USB CC
resistors R23 / R24 upright, which `--strict` caught swapping their pins and
shorting D+ / D- (the root's two `wire_near_body` hits stay for the root's own
redraw). Not re-reviewed after these fixes. Left: U51's ground symbol hangs under
its NC pin (`gnd_bus` drops from the last pin); U32's outputs are grouped by
function, not Y0 to Y15 (the reviewer would put them in order now that nothing is
wired: user's call); the decoder sits left of the module so its flow runs right to
left; the page has empty bands since the trunks went.

**Second step of session 4: the GPIO Expander's seven inputs.** Every source block
is a neighbour, so they are wires on the root, each with one net label (written
vertically on its riser): PGN_15V on the left of column 2 (Power Good, Rails +-15V,
GPIO Expander), PGP_15V on its right (the two would cross on one side),
AMBIENT_INT / AMBIENT_CT down the gap beside the sensor column, INA239_ALERT
straight across, IO_ADC_DRDY_N and IO_EXP_INT_N up from the row below. The GPIO
Expander block is 14 cells tall (`BOX_HEIGHT`). `link()` inside `root_links()` draws
them. On the seven child sheets only the label kind changed.

`net_label()` now turns any `is_global=True` label of a net that has a sheet pin into
a hierarchical label on a sheet and a net label on the root (`ROOT_LOCAL` is built
from `SHEET_PINS`), so converting a net is: add its pins to `SHEET_PINS`, draw its
root wire or add it to `LABEL_LINKED`, give it a shape in `PASSED_BETWEEN_SHEETS` or
`LABEL_DIRECTION`, regenerate, then `python3 tools/rename_board_nets.py $B/base.net
$OUT/new.net` (new tool: names only, refuses to write unless undoing the names gives
the board back).

After this step: 45 nets are `/NAME` on the board (38 + these 7); strict with
`--renamed` 0 differences; DRC 0 / 0 / 0 with the 12 warnings; ERC 0; 609/609;
497 / 379; check_symbols 0; global_label 187, close_label_pair 45, baseline updated.
The board still equals the pre-session board with the names undone (checked).

Reviewer on the GPIO Expander step: PASS, nothing to fix (no crossings, no 4-way
points, pin order right). For later it lists the repeated hierarchical labels on
power_good (PGN_15V x4, PGP_15V x3), ambient, system_current and io_expanders, and
the buffer notes sitting nearer R17 than U51.

**Third step of session 4: the ten I/O sheets are nested under one parent
(user, 2026-11-19: "One parent block", asked because IO Expanders alone needs about
33 pins).** This reverses "no re-parenting of sheets with locally named nets"; the
user accepted the board renames that follow.

- New sheet `sheets/io.kicad_sch`, "Universal IO" (`build_io`), in `SHEETS` ahead of
  its children; `NESTED_SHEETS` puts io_expanders, io_core, io_switches, io_drivers,
  io_ch1 to io_ch4, io_precision and io_pressure on it. `BLOCK_ORDER` takes `None`
  for an empty cell; the `io` block sits right of GPIO Expander, Expansion beside it.
- Stage A (done, gated): nesting only. The parent sheet shows the ten blocks in a
  plain grid and passes five nets up to the root through hierarchical labels
  (IO_DAC_CS, IO_ADC_CS, IO_EXP_CS by label from the decoder; IO_EXP_INT_N and
  IO_ADC_DRDY_N by straight wires to GPIO Expander). The nets between the I/O
  sheets are still global labels.
- A sheet added by the redraw has `OWN_UUID_SEQUENCE` value 0 and takes its ids from
  its name: `Sheet.__init__` used to draw two ids from the shared sequence, which
  shifted every later sheet's part ids (found with the `cmp` check).
- Board: 16 local nets renamed (`/IO Channel 1/IO1_BUF` to
  `/Universal IO/IO Channel 1/IO1_BUF`, and so on); 186 footprints' symbol paths
  and sheet names updated to the new parent with the new
  `tools/relink_board_sheets.py` (text only). The board equals the pre-session board
  once every `(net "...")`, `(path "...")` and `(sheetname "...")` string is blanked
  (checked). Not opened in the KiCad GUI; "Update PCB from Schematic" not tried.
- Gate is now `compare_netlists.py --strict --renamed` (accepts a net that kept
  exactly its pins under another name, `--list` prints them): 0 differences, 61
  nets renamed. `rename_board_nets.py` handles any such rename. DRC 0 / 0 / 0 with
  the 12 warnings, ERC 0, 609/609, 497 / 379, check_symbols 0, structure counts at
  baseline (187 / 45 / 10).
- Stage B (done, gated): the parent page is drawn from `IO_BLOCKS` (block, cell,
  nets on its left and right edges), which also sets the children's `SHEET_PINS`,
  `BOX_HEIGHT` and `NESTED_SHEETS`. Five columns: port expanders, range and pull-up
  switches, the four channels, drivers with the precision and pressure ports under
  them, DAC and ADC. Neighbouring columns are wired by `fan()` (pins in the same
  order on both sides, one riser per wire, so nothing crosses); IOn_PIN goes from
  the switches to its channel and on over the channel block to the drivers; a net
  between columns that are not neighbours is a net-label pair (`end_label()`).
  `net_label()` makes a net with a sheet pin a net label on any parent sheet
  (`PARENT_FILES`) and a hierarchical label on a leaf sheet. Shapes for these nets
  come from `IO_NET_SHAPES` in `kicadgen.py`.
- 56 more nets renamed on the board, `NAME` to `/Universal IO/NAME`. Totals now:
  117 nets renamed (45 `/NAME`, 16 moved under the parent, 56 named on the parent),
  186 footprints relinked. The board still equals the pre-session board once the
  `(net ...)`, `(path ...)` and `(sheetname ...)` strings are blanked, and no renamed
  net changed its net class (both checked by script).
- Gate after stage B: strict with `--renamed` 0 differences; DRC 0 / 0 / 0 with the
  12 warnings; ERC 0; 609/609; 497 / 379; check_symbols 0; global_label 31 (was 255
  at the start of the session), close_label_pair 45, wire_near_body 10, baseline
  updated. Reviewer on the Universal IO page: started, result not recorded here yet.
- Reviewer on the first Universal IO page: FAIL (8 crossings where `fan()` was
  called once per channel, label pins facing away from their partners, three wired
  runs over 85 mm). Fixed: one `fan()` call for the switches-to-channels wires;
  labelled pins moved to the edge that faces their partner (expanders' control
  lines on the right, above the wired pins; drivers' enables and the DAC / ADC
  block's channel lines on the left); blocks closed up so every wired run is under
  85 mm; IOn_PIN reaches the drivers by label; column headings. 0 crossings on the
  page and on the root by script. Not re-reviewed yet.

**Fourth step: the leftovers. No global label is left except `{SPI}`.**
ESP_EN (label at the module and at Display; a wire between Universal IO and
Expansion), AUX_IO5 / 7 / 11 / 13, RS485_IRQ_N and EXP_INT_N (wires, Universal IO to
Expansion), PG_15V (wire along the channel under Debug to Amp Control), PWR_BTN
(wire, Power Button to Display), USB_VBUS and ESP_BOOT (labels). ACS_SCK, ACS_MISO
and UART_CLK are plain net labels on their own sheets now (`name_tag()`), with
`*/ACS_*` added to the SPI net class so their class did not change.

Totals after this step: 131 nets renamed on the board, 186 footprints relinked;
strict with `--renamed` 0 differences; DRC 0 / 0 / 0 with the 12 warnings; ERC 0;
609/609; 497 / 379; check_symbols 0; **global_label 0**, close_label_pair 45,
too_many_parts 2, copied_sheet 2, wire_near_body 10 (baseline file updated).
`sheets/aux_io.kicad_sch` is an unreferenced old file; delete only if the user
confirms.

**Fifth step: sheet redraws (user, 2026-11-19: "Please continue until the schematic
is done").** Done and gated, each with strict 0 differences and ERC 0:

- power_good: one node line per rail, left to right past its divider (pull-up and
  pull-down six cells apart, so each meets the line in a T) and its LED driver to
  the BAT54AW; the -15 V line is the upper one so PG_15V leaves to the right with
  no crossing; the red driver FET is mirrored (`nfet(mirror=)`); 18 label pairs gone.
  `--strict` caught R88's pins swapped on the first attempt.
- power_button: status LED wired; KILL# network moved right so C41 stands clear of
  the EN# / INT# drops (4 wire-near-body hits gone); block pins moved to the right
  edge to match the sheet.
- system_current: ALERT line runs past its pull-up to the LED and its sheet pin.
- debug: rail LED anode wired.
- io_precision / io_pressure: each input is one line from header pin through its
  clamp tee, 2.2 k and filter to the ADC pin; the excitation runs on to its clamp
  and the reference network. The two ports stand more than 85 mm apart, so their
  PREC_EXC labels are a long-run pair.
- io_drivers: the output switch is mirrored, so the four driver outputs are wires
  (`fan()`), and the pins leave on the right.
- io_ch1 to io_ch4: burden FET mirrored (gate on the right); on the fast channels
  the pin line drops to the fast path instead of a second label.
- cooling: +12 V drop moved off R43. display: reset line spaced so the clamps
  stand clear.

Counts now: global_label 0, close_label_pair 7, wire_near_body 2, too_many_parts 2,
copied_sheet 2. Not reviewed yet: everything in this step.

Reviewer on that step (2026-11-19): io page PASS; the others failed mostly on
part text sitting by the wrong part, plus structural points, fixed since: root
(COMP_RELAY_EN stub read as a Power Button pin, so PWR_INT / PWR_KILL went back to
that block's left edge; PG_15V is a label pair again, its ends are 98 mm apart;
riser names moved onto horizontal runs, no rotated labels left on the root);
power_button (INT# pull-up above its run, status LED in line with its 13k, shunt
FET below the line); system_current (ALERT pull-up above the line); io_precision
(reference network in line); channel sheets (gate series resistor at the gate);
compressor_relay and amp_control (LED symbol variant `APGB0607G22R23C_AP`, RA and GK
on the left, so no loop); signal_gen (DDS_SINE label on a stub to the right).

**User decisions, 2026-11-20:**

1. Bias resistors move to the pins they serve ("Move to their pins"). Done on
   io_ch1 to io_ch4, io_precision, io_drivers, io_switches and ambient:
   `pull_up_at()` / `pull_down_at()`, with `taps(sh)` noting where each hangs so the
   parts are still created in the order the references follow. The two switch
   symbols have their selects eight cells apart so each carries a small pull-down;
   io_drivers uses a variant `TMUX7412FRRP_DRV` (drains and selects left, pins and
   fault flag right). No BIAS block is left.
2. The four channel sheets stay copies ("Keep the copies"): one file placed twice
   would need the connector and jumper values to lose their channel number.
   `copied_sheet` stays 2.
3. Cold Head's ESD clamp keeps its four label pairs ("Keep the labels").
   `close_label_pair` stays at least 4.
4. Rule file, design skill and reviewer agent rewritten to the decisions of this
   session ("Yes, update them"): net labels for long runs, buses only for
   communication buses, the board renamed by name only, pull resistors on their
   lines.

Root R23 / R24 fixed (CC1 steps up three rows before its pull-down): wire_near_body
is 0. Counts now: global_label 0, close_label_pair 7, wire_near_body 0,
too_many_parts 2, copied_sheet 2. Strict with `--renamed` 0 differences (131
renames), DRC 0 / 0 / 0 with the 12 warnings, ERC 0, 609/609, 497 / 379.

**The two oversized sheets are split (2026-11-20).** In both cases the group that
moved was the last thing its builder drew, so the new sheet is built straight after
the old one and every part keeps its reference:

- `sheets/aux_header.kicad_sch` "AUX Header" (`build_aux_header`): the AUX header
  group from Expansion, now 26 parts. AUX_IO11 / AUX_IO13 pins moved to its block.
- `sheets/ldo_15v.kicad_sch` "Regulators +-15V" (`build_ldo_15v`): the LT3045 /
  LT3094 post-regulators from Rails +-15V. PGP_15V / PGN_15V pins moved to its
  block, which took Rails +-15V's cell; Rails +-15V has no pins and sits beside it.

`tools/relink_board_sheets.py` now works from the netlist: every footprint takes
the symbol path and sheet name its reference has in the schematic. **Run it after
every regeneration, with `rename_board_nets.py`.** Its first run relinked 25
footprints whose symbol ids had drifted from the schematic: a part's id comes from
the order parts and power symbols are created in, and redraws had changed that order
(a pull-up drawn before its rail symbol instead of after, for example). DRC parity
does not notice, but "Update PCB from Schematic" matches by these ids.

Counts now: global_label 0, close_label_pair 7 (4 cold_head by decision, 3
expansion `{SPI}` stubs), wire_near_body 0, too_many_parts 0, copied_sheet 2 (by
decision). 34 sheets. Strict with `--renamed` 0 differences (133 renames), DRC
0 / 0 / 0 with the 12 warnings, ERC 0, 609/609, 497 / 379, check_symbols 0. The
board equals the pre-session board once net, path and sheetname strings are blanked.

**Last pass of 2026-11-20.** The reviewer (after the bias move and the splits)
found the structural faults cleared; what it failed sheets on was reference / value
text beside the wrong part, two pin names colliding inside symbols, and Rails
+-15V's missing heading. Fixed:

- `FIELD_SIDES` in `gen_schematic.py`: sheet -> side of the part -> references. The
  text position is computed from the part (`side_fields()`), so it follows a move;
  `'below>4'` shifts it 4 mm right. Used for about 40 parts the automatic placer put
  by a neighbour. A few parts were spread to make room (ldo_15v output capacitors,
  the channel sheets' divider leg and supply input capacitor, io_precision's input
  capacitor, the fault-flag risers).
- Symbols: LT3094 and TMUX7412F bodies a row or two taller so bottom pin names
  clear the last side pin.
- **Rails +-15V redrawn without crossings** (it had 7): the ADP5071 symbol's pins
  are regrouped (the five pins on the input rail together at the top left, COMP1
  and COMP2 ten cells apart, SW2 / FB2 / VREF in the order their wires nest), and
  `build_rails_15v` places everything from the pins' rows.
- A wire-crossing count over every sheet (script in the session scratchpad, not in
  the repo: horizontal against vertical wire segments): 0 on all sheets except
  amp_current's one known crossing (ACS_CS over the gated MISO).

**Final state of this session.** 34 sheets. global_label 0, close_label_pair 7,
wire_near_body 0, too_many_parts 0, copied_sheet 2, unmatched_sheet_pin 0. Strict
with `--renamed` 0 differences (133 nets renamed with pins unchanged). DRC with
parity 0 / 0 / 0 and the same 12 warnings. ERC 0. `datasheet_rules` 609/609.
`verify_netlist` 497 / 379, no mismatch. `check_symbols` 0. Generator check lines 0.
Board against the pre-session file: identical once `(net ...)`, `(path ...)` and
`(sheetname ...)` strings are blanked; 3742 net entries, 220 symbol paths and 207
sheet names changed. `cryocooler.kicad_dru` unchanged. Nothing committed. Not opened
in the KiCad GUI; "Update PCB from Schematic" not tried; renders and fab files not
regenerated (net names are not in them).

Not re-reviewed after this last pass. The reviewer's "for later" list, still open:

- compressor_relay / amp_control: the LED's GA / RK side runs back under the LED
  body to the output line; moving J13 / J8 three cells right would let it drop
  straight. R30 / R28 text differ between the twin circuits. amp_control: J9's
  no-connect sits 1 mm from the sleeve ground.
- power_good: the node lines into D15 are about 90 mm long (wires; they read well);
  the guard note sits below its circuit.
- power_button: PWR_KILL and PWR_BTN labels sit on the opposite side from their
  block pins; no heading on the LTC2954 group.
- io_switches: title names two functions.
- Universal IO: the PREC_EXC riser name is rotated.
- expansion: EXP_MISO wire is about 115 mm (a label pair by the 85 mm rule); the
  three `{SPI}` stubs; two functions on the sheet.
- root: U32's outputs grouped by function, not Y0 to Y15; R23 / R24 are drawn in
  line to the capacitor's ground leg rather than hanging from their own lines
  (giving each its own ground symbol adds power symbols, which renumbers every later
  sheet's #PWR); U51's ground hangs under its NC pin; empty bands on the page.
- Sheets not reviewed in this session at all: cold_head, imu, cooling, display,
  debug, indicators, gpio_expander, power_input, rails_logic, amp_current,
  supply_switches, io_core, io_expanders, io_pressure (the last two only in part).
- Unused, delete only if the user confirms: `sheets/aux_io.kicad_sch`; the empty
  loop in `mcu_and_usb`.

Left, with why:

- cold_head RTD_1 to RTD_4 (4 pairs): the ESD clamp has four pins on one side and
  the four lines run side by side, so a wired clamp crosses three lines however it
  is placed. Needs a clamp symbol with pins on two sides or the user's exception.
- expansion `{SPI}` (3 bus stubs within 75 mm): joining them puts the bus across a
  chip-select line. Do it with that sheet's split.
- Expansion still holds two functions (RS-485 and the SPI header). Splitting them
  needs the two groups' parts to keep their creation order across two sheets.

Reviewer notes kept for each sheet's own redraw: power_button: PWR_INT / PWR_KILL
labels face right mid-sheet while the block pins are on the left; C41 wires.
signal_gen: DDS_SINE label hangs downward mid-sheet. cooling: R43 has the +12 V wire
2.54 mm from its body, R15 / R16 text beside "+3V3", no stub at the RN junctions, no
group headings, tach labels not aligned with the PWM labels; the reviewer also
noticed (not verified) that the flow tach pull-up is on the GPIO side of R43 while
the fan and pump pull-ups are on the connector side. compressor_relay and
amp_control: the LED symbol's pin sides force a loop and a crossing (same finding as
the pilot); compressor_relay has no group headings and D14's text sits by the
COMP_RELAY label. imu: no headings. Block pins on the left whose child label faces
right: IO_ADC_CS (io_core), INA239_CS (system_current). Root: R23 / R24 as before;
pins low in their blocks (EXPANDER_CS, IO_DAC_CS / IO_ADC_CS); a lot of empty page
between the module and the block rows now that the trunks are gone (`ESP_ROOM`, the
gap under the module).

To check that a step changed only the sheets it meant to, copy
`cryocooler.kicad_sch` and `sheets/*.kicad_sch` aside before regenerating and `cmp`
afterwards: `git status` cannot show it, every earlier sheet is already modified.

### Session 3 (2026-11-19): signal_gen, amp_current, io_core, io_expanders, expansion, gpio_expander

Baseline re-exported from `rev6-schematic` (f86f43b) and equal to `HANDOFF_rev6.md`
(497 parts / 379 nets, DRC 0 / 0 / 0 with 12 warnings). Gate steps 1 to 5 pass after
each sheet. Nothing committed. See "Sheets redrawn in session 3" below for what each
sheet changed, the reviewer's verdicts and what was left.

**All 14 chip selects (Y0 to Y13; earlier notes say 15) are on four root trunks** (`{EXP_CS}` column 14, `{IO_CS}` 18,
`{SENSOR_CS}` 22, `{SIGNAL_CS}` 26); U32 has no flags left.

**Blocks reordered (user, 2026-11-19: "Yes, reorder").** `BLOCK_ORDER`, 6 x 5, rows
22 cells apart, grid 20 rows lower so there is room for runs under the ESP32:

| | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| 1 | cold_head | signal_gen | debug | amp_control | display | cooling |
| 2 | imu | power_good | supply_switches | power_button | compressor_relay | indicators |
| 3 | ambient | rails_15v | io_precision | io_pressure | power_input | rails_logic |
| 4 | system_current | gpio_expander | io_ch1 | io_ch2 | io_ch3 | io_ch4 |
| 5 | amp_current | io_core | io_expanders | io_switches | io_drivers | expansion |

This is not the grid first shown to the user: that one made the `{IO_CS}` branch to
GPIO Expander cross `{SENSOR_CS}`. The rule that fixes the order: a trunk's branches
must leave below the foot of every trunk inside it, so the deepest trunk is
outermost. From that: column 1 holds the five sensor blocks (straight entries from
`{SENSOR_CS}`, column 22); signal_gen heads column 2 (`{SIGNAL_CS}`, column 26, runs
above the grid); `{IO_CS}` (18) runs under the last row and rises beside column 2 to
gpio_expander and io_core, then on to io_expanders; `{EXP_CS}` (14) runs under that.
`{IMU_INT}` comes down the outer ESP32 riser and along the channel under row 1 to
the IMU's right edge; AMP_REM_EN drops straight to amp_control. No link crosses
another. Score on the 89 signals still to wire (grid cells spanned): 264.5 before,
226.5 now; block-to-block signals 4 or more cells apart: 19 before, 7 now.

Reviewer on the reordered root (2026-11-19): no crossings, every entry labelled, one
tag per trunk, junctions 3-way; FAIL on three bus runs 2.54 mm from blocks they do
not enter. Fixed (risers stand four cells off a block; `{IMU_INT}` steps right at
its name tag to clear Debug, because the flags still on the ESP32's lower-left pins
block a straight riser there). Not reviewed again after that fix.
`wire_near_body` does not test sheet blocks; worth adding.

Things the order leaves for the signal wiring:
- COMP_RELAY_EN (IO16) is on the ESP32 symbol's right side now, last in the CAN /
  status group (user, 2026-11-19: "Yes, move them"): compressor_relay is right of
  the module. The gap between AUX and the spare pins went so the side keeps 28 rows
  and the left-hand pins stay put.
- PG_15V_N was **not** moved, against that same answer: I had told the user it could
  not reach power_good (column 2) from the left without crossing `{IMU_INT}`, and
  that was wrong. Its riser sits inside the IMU bus's and turns west one row below
  the bus's run in the same channel, so they nest. From the right side it would have
  to come back under the module. Tell the user; move it if they still want it.
- The same nesting serves PWR_INT / PWR_KILL (power_button, column 4). The corridor
  for these risers is between Debug (ends column 192) and Amp Control (starts 210):
  `{IMU_INT}` is at 198 after its step, AMP_REM_EN at start - 7.
- Left-edge pins on gpio_expander above its chip select are reachable from ambient
  and system_current; io_core's and io_expanders' left edges are behind the riser.
- IO DAC and ADC's IO_ADC_CS pin is now on the block's left edge (its label is on
  the right of the sheet); the IMU's `{IMU_INT}` pin is on the right edge (label on
  the left of the sheet).

**Settled (user, 2026-11-19):** a sheet with no pins because it only has global
labels or only power and ground may stay on the root, so power_input and
supply_switches stay where they are.

**The generator handles more than one level of sheets (user asked for it,
2026-11-19).** `NESTED_SHEETS` in `tools/gen_schematic.py` maps a sheet's stem to
(parent stem, block cell on the parent's page); it is empty, so nothing is nested
and the output is unchanged. A nested sheet is left out of `BLOCK_ORDER` and must
follow its parent in `SHEETS`. `sheet_symbol()` writes the file name relative to the
parent and the parent's instance path, `main()` builds each path from its parent's,
and `check_sheet_structure.py` follows blocks on any sheet. One trial was run and
taken out again (supply_switches inside rails_logic): KiCad read it as
`/Rails 5V 3V3/Supply Switches/` with all 497 parts. Nesting a sheet that has nets
named by a local label renames them on the board (see "Net names"), and the root's
`root_links()` assumes the root grid in `BLOCK_ORDER`: taking a block off the root
shifts the others, so re-run the gate.

**Root rearranged (user, 2026-11-19: "Yes, rearrange first", then "ok, you can
continue") and gated. Waiting for the user's review of the new root render before
more trunks or sheets.** Done in the rearrangement:

- ESP32 symbol regrouped by function (`cryocooler:ESP32-S3-WROOM-2`, `from_stock` in
  `make_lib.py`, pin numbers kept): reset/boot, decoder control, IMU interrupts, power
  control, switched outputs on the left; USB, SPI, cooling, CAN/status, AUX, spares
  on the right.
- `{DECODER}` trunk: CS_ADDR_A/B/C and CS_EN_N from the ESP32, CS_ADDR_D from its
  buffer (now mirrored, on the CS_ADDR_D_1V8 wire), the three bias resistors on the
  trunk. These were same-sheet global label pairs. CS_ADDR_D_1V8 is a wire with one
  global name tag.
- `{IMU_INT}` straight down to the IMU block; `{SENSOR_CS}` down the left edge;
  AMP_REM_EN a single wire with no crossing.
- Blocks reordered by function (`BLOCK_ORDER`; page numbers still follow `SHEETS`).

Reviewer on the rearranged root (2026-11-19): FAIL on placement, trunks sound.
Fixed after it: `{SPI}` trunk moved off U2's body edge, the buffer's decoupling
heading moved clear of `{IMU_INT}`, the buffer's heading moved above U51, the bias
heading renamed, `{DECODER}` and CS_ADDR_D_1V8 drawn as outputs. A second review was
not run. Left as is, with reasons:

- U1's decoder group reads D, A, B, C, EN_N. D sits first because its wire to the
  buffer would otherwise cross the trunk at an entry.
- AMP_REM_EN makes a U-turn under U1 (IO6 could move to the right side once the
  switched-output group is settled).
- `{SENSOR_CS}` runs about 430 mm to IMU; block order is still open.

### USB stays on the root (user, 2026-11-19)

A separate USB sheet for U2, J1, C63, R23 and R24 was tried and taken back out at
the user's choice. What the trial showed, for any later "move parts to a new sheet":

- The board link survives: with the sheet filled in the same build order (so parts
  keep their ids), DRC parity and `--strict` were both 0.
- A net that has only KiCad's automatic name on the board (`Net-(U1-USB_D-)`) is
  renamed `/Sheet/LABEL` once it crosses a sheet pin. Keeping the name needs a new
  global label carrying the automatic name, which raises `global_label`. The user
  preferred to leave the parts on the root over adding those two tags.

### Chip-select trunks (user, 2026-11-19: group "by function")

**Superseded in session 4: the user asked for labels instead of trunks. Kept as history.**

| Trunk | Members (decoder output) | Sheets |
|-------|--------------------------|--------|
| signal chain (`{SIGNAL_CS}`, drawn) | AD9833_FSYNC (Y0), AD5453_SYNC (Y1) | signal_gen done (bus pin) |
| sensors (`{SENSOR_CS}`, drawn with all 5) | IMU_CS (Y7), AMBIENT_CS (Y8), ADS1220_CS (Y6), INA239_CS (Y2), ACS_CS (Y5) | imu, ambient, amp_current done; cold_head, system_current have only the pin converted |
| I/O (`{IO_CS}`, drawn with all 4) | EXPANDER_CS (Y3), IO_DAC_CS (Y4), IO_ADC_CS (Y9), IO_EXP_CS (Y10) | io_core (two pins), io_expanders and gpio_expander done |
| expansion (`{EXP_CS}`, drawn) | RS485_CS (Y11), EXP_CS_A (Y12), EXP_CS_B (Y13) | expansion done (three pins) |

Decided (user, 2026-11-19): **regroup U32's outputs by trunk.** Done in `make_lib.py`:
top to bottom expansion (Y11 to Y13), I/O (Y3, Y4, Y9, Y10), sensors (Y2, Y5, Y6,
Y7, Y8), signal chain (Y0, Y1), spares. The top group takes the outermost
trunk, so no member wire crosses a trunk. Trunk columns on the left edge: expansion
14, I/O 18, sensors 22, signal chain 26.

Drawn: `{SENSOR_CS}` with INA239_CS, ADS1220_CS, IMU_CS, AMBIENT_CS (entries at
System Current, Cold Head Temp, IMU, Ambient Temp). Gate passed; reviewer not run on
this step. cold_head and system_current have only their chip-select pin converted.
On system_current the INA239_CS label points right while its block pin is on the
left; fix with that sheet's redraw.

Done in session 3: ACS_CS joined `{SENSOR_CS}` (Y5 moved up into the sensors group,
the trunk branches down to Amp Current at column 84, four cells right of Cold Head's
riser so the trunk has no 4-way meeting); `{SIGNAL_CS}` runs down column 26 and along
row 154 to a bus pin on Signal Generator.

Nothing is waiting at U32 any more:
- I/O: done. `{IO_CS}` runs down column 18 with its name tag at the foot, a branch
  along row 194 to GPIO Expander and one along row 214 to IO Expanders.
- Expansion: done. `{EXP_CS}` runs down column 14 and along row 254 under the last
  row of blocks to three pins on the Expansion block.

Sheets with several labels of one chip select (amp_current, io_expanders,
expansion) need their in-sheet label pairs redrawn in the same step as their pin.

Still to do on the root: propose the chip-select groups (15 selects, 2 to 8 per bus)
and ask the user; trunks for the remaining ESP32 groups as their sheets convert.

| Step | State |
|------|-------|
| Step 0: `compare_netlists.py --strict`, baseline, rule text | done |
| Pilot: `amp_control` + its pin on the root | done, gate passed, awaiting review |
| Root: A2, ESP32 moved right, blocks re-spaced, 2 trunks | done, gate passed, awaiting review |
| `imu` | done (IMU_CS pin, `{IMU_INT}` bus pin) |
| `ambient` | part done: AMBIENT_CS pin; AMBIENT_INT / AMBIENT_CT wait for gpio_expander |
| `signal_gen` | done: `{SIGNAL_CS}` bus pin; SIG_SINE / DDS_SINE wait for debug |
| `amp_current` | done: ACS_CS pin on `{SENSOR_CS}`; gates moved to the logic side |
| `io_core` | done (stays one sheet, user): IO_DAC_CS / IO_ADC_CS pins on `{IO_CS}`; the other 17 globals wait for the I/O sheets |
| `io_expanders` | done: IO_EXP_CS on `{IO_CS}`; port labels, IO_EXP_INT_N and ESP_EN wait for their sheets |
| `expansion` | done: three pins on `{EXP_CS}`, all in-sheet label pairs wired |
| `gpio_expander` | done: EXPANDER_CS on `{IO_CS}`; GP0 to GP6 labels wait for the root's signal wiring |
| Net-name decision | **decided 2026-11-19: keep one global label on the root wire** |

The user lifted the three-sheet limit on 2026-11-19 ("move onto doing the rest of
the sheets"). Sheets left, smallest first (redo `ls -S` if sizes change):
power_input, indicators, debug, supply_switches, io_pressure,
compressor_relay, system_current, cold_head, rails_logic, display, io_ch3, io_ch4,
io_switches, power_good, cooling, io_precision, power_button, io_drivers, io_ch1,
io_ch2, rails_15v, then the root's own circuits (ESP32, USB, chip-select decoder). At most three sheets per
session, then stop and ask for a fresh session.

`wire_near_body` is 12 after signal_gen (was 16): R36 and C86 are fixed; 10 after expansion (U123, U124).

## Sheets redrawn in session 3

Reviewer verdicts are the `schematic-reviewer` subagent's. Each sheet was reviewed,
fixed and reviewed again.

### signal_gen: reviewer PASS (third pass)

- `{SIGNAL_CS}` hierarchical bus along the top (`SIGNAL_CS_ROW`), one riser per chip
  select. AD5453_SYNC crosses the VREF wire once (the trunk is above, SYNC is below
  VREF on the symbol).
- Everything right of the clock is drawn, then moved 8 cells right
  (`SIGNAL_GEN_SHIFT`) so the FSYNC riser fits between the clock and the `{SPI}` tap.
  The user's hand-placed texts moved with it (TP47, U5A, U5B, R36: x + 10.16 mm in
  `PINNED_FIELDS`); U3's moved 5 mm right because its ground pin moved. R40's pin was
  dropped (the layout now centres it); U4, C15 and U6 gained pins.
- Group headings; the sheet note said R50, the part is R39 (`ref_map_rev3.py`).
- C15 raised and its flag moved; C43 / R25 moved right; C85 / R35 / R92 moved clear of
  R36; C86 moved clear of the RFB wire; R40 and C8 spaced; U5C moved down, its V- and
  pad share one -15V symbol; decoupling row moved down.
- ECS-2520MV symbol: Tri-State and VDD spaced from OUT (names overlapped). The UART
  clock on `expansion` uses the same symbol, so that file changed too (reviewed, PASS).
- Left: `SIG_SINE` and `DDS_SINE` are still global (they need debug, and SIG_SINE's
  end on amp_control, converted in the same step). Reviewer polish not done: the
  5 mm jog into U5A pin 3 (U5A's text is the user's), D16 drawn as a box, D16's text
  beside its ground symbol, the two `{SPI}` taps drawn differently.

### amp_current: reviewer PASS (second pass)

- The two SPI gates are left of the isolator, in the order of its inputs
  (`acs_bus_gates(sh, iso)`); the isolated side is drawn first and moved 52 cells
  right (`AMP_CURRENT_SHIFT`).
- ACS_CS: one hierarchical label, one spine to both gate enables and the isolator.
  It crosses the gated-MISO wire once: both gates share a symbol with the enable on
  the bottom, so one crossing cannot be avoided.
- ACS_SCK and ACS_MISO never leave the sheet but are named globally on the board, so
  each is a wire with one global name tag (the CS_ADDR_D_1V8 pattern).
- VSENSE divider redrawn hot end up. R64 to R67 keep their pins: the chain is numbered
  from the tap upward with pin 1 down. **`--strict` caught this**: the first attempt
  swapped R64 and R67's nets and gave 2 differences and 2 parity issues.
- ISO_GND's PWR_FLAG is on U17's ground stub; its own ISO_GND symbol is gone.
- ISOW7841A symbol: two blank rows so the signal names clear VCC / VISO / SEL.
  ACS37800 symbol: five blank rows between VINN and IP- for R63 and the grounds.
- `place_blocks(..., pitch=16)` for the block with the 22 uF, so its text sits beside it.
- Left (polish): J11's 5 mm jog, the gates' decoupling block sits apart from the others.

### io_core: reviewer PASS on the drawing (second pass); one point is the user's call

- IO_DAC_CS and IO_ADC_CS are hierarchical labels. The ADC's pin is on the block's
  right edge because the ADC's SPI pins are on its right; on the root its wire runs
  under the block.
- Notes split so they stay on the page; headings beside their ICs; DAC reference
  capacitors spaced; ADC ground bar drops from its end (it met four ways); AINCOM is
  the last pin on the ADS124S08's left side with a straight stub to ground.
- **Decided (user, 2026-11-19): io_core stays one sheet.** The reviewer fails it for
  holding two functions (output DAC, input ADC; they share only the SPI bus).
  Splitting would move U100 or U101 to a new sheet path on the frozen board. Tell the
  reviewer this is settled when the sheet is reviewed again.
- Left: 17 global labels to sheets not converted yet (IOn_DAC, IOn_ADC, PRESSn_ADC,
  PREC_*, IO_ADC_DRDY_N).

### io_expanders

- IO_EXP_CS is a hierarchical label with one entry at each MCP23S17 (they are 89 mm
  apart, over the wire limit, and U107's port flags fill the gap).
- The shared interrupt's pull-up R625 hangs on U107's IO_EXP_INT_N wire (was a
  separate BIAS group, a close label pair).
- MCP23S17 symbol: blank rows above A0, so a high address bit stands in the same
  column as the grounded ones (U108's A0 had a long stub into U107's group).
- U107 / U108 text pinned clear of the +3V3 wire; notes split.
- Left: about 30 port labels, IO_EXP_INT_N x2 and ESP_EN x2 are still global.
  Reviewer: give them real directions when they convert (`*_EN`, `*_DIRECT`,
  `*_BURDEN`, `*_PULLUP`, `*_OE_N` out; `*_FLT_N`, `RS485_IRQ_N`, `EXP_INT_N` in).

### expansion

- RS-485: bridge moved 12 cells right for the left-hand stubs; UART clock wired into
  XTAL1 (UART_CLK keeps one global name tag); IRQ pull-up R647 on the IRQ wire.
- SPI expansion header: header on the right (`EXP_HEADER_ROW`), lines fanned out so
  none crosses; the four series resistors and both MISO buffers wired; EXP_MISO runs
  over the top and down the left to both buffers, pull-down R649 at its foot; the
  EXP_INT_N pull-up R648 on its wire. Each local net (EXP_SCK, EXP_MOSI, EXP_MISO,
  EXP_CSA, EXP_CSB) keeps one local label.
- AUX header: moved under the RS-485 group, both lines wired to the header; clamps
  lowered (clears `wire_near_body` for U123 and U124: 12 to 10).
- BIAS group gone: each pull is on its own wire, created in the same order so the
  references hold.
- Left: ESP_EN, RS485_IRQ_N, EXP_INT_N, AUX_IO11, AUX_IO13 are still global; the
  sheet still holds three functions and 31 parts (split is not in this pass).

### gpio_expander

- EXPANDER_CS is a hierarchical label. RESET's +3V3 stands on a short stub in the
  column of the address straps (MCP23S08 symbol: blank rows above RESET); it was a
  40 mm stub. Notes split, decoupling block moved under the IC, U25's text pinned.
- Left: PGP_15V, PGN_15V, AMBIENT_INT, AMBIENT_CT, IO_EXP_INT_N, IO_ADC_DRDY_N and
  INA239_ALERT are still global (see "Stopped here").

### Root

- `{SIGNAL_CS}`, the ACS_CS branch and `{IO_CS}` drawn; reviewer PASS on all three.
- `{EXP_CS}` and the `{IO_CS}` branches to IO Expanders and GPIO Expander drawn.
- 74HC154 decoupling block moved down and right: U32's ground symbol sat on its
  heading (left over from the rearrangement).
- Reviewer polish not done: IO_DAC_CS's label nearly touches the EXPANDER_CS flag
  (goes away when EXPANDER_CS joins the trunk); `{IO_CS}` and `{SENSOR_CS}` run 4 cells
  apart down the left edge.

### Found on the way

- **A removed power symbol shifts every later sheet's file.** Parts take their id
  from the shared sequence when they are drawn, so `OWN_UUID_SEQUENCE` alone does not
  protect the other files. `retire_power_symbol()` keeps the number and the id; use
  it whenever a redraw drops a power symbol (signal_gen and amp_current each did).
  After every sheet, `git status` must list only the redrawn sheets.
- **The generator's 4-way check missed a drop under an inner pin of a ground bar**
  (the bar is one unbroken wire, so the check saw a T). **Fixed (user, 2026-11-19:
  fix the check and every sheet now):** `four_way_junctions()` splits wires at other
  wires' ends, and `gnd_bus` always drops from the bar's last pin. The check then
  found 10, all from `gnd_bus`: cold_head, rails_15v, io_drivers, io_switches,
  io_precision, expansion, io_ch1 to io_ch4. Those sheets changed by that one ground
  symbol only (reviewer: all OK) and are in `OWN_UUID_SEQUENCE` ahead of their redraw.
- `tools/check_symbols.py` needs the root file as its argument
  (`python3 tools/check_symbols.py cryocooler.kicad_sch`).

## Net names (pilot result)

Tested on `AMP_REM_EN` (board name: `AMP_REM_EN`), by netlist export:

| Root wire carries | Net name |
|-------------------|----------|
| hierarchical label + sheet pin only | `/Amp Control/AMP_REM_EN` |
| plus a local label on the root | `/AMP_REM_EN` |
| plus one global label on the root | `AMP_REM_EN` (unchanged) |

So with the board frozen, a converted net needs one global label left on its root
wire. The pilot does that (`ROOT_LINKS[...]['label']`). It breaks "global labels only
for `ALLOWED_GLOBALS`", so `global_label` can drop by the labels on the child sheets
but not to 0. The other way out is a later board step that renames nets without
moving copper (`rev6-sheet-pins` has `tools/rename_board_nets.py`).

**Decision (user, 2026-11-19): keep the root global label.** Every converted net
keeps exactly one global label, on its root wire, and none on a child sheet. Board
renaming is not part of this pass.

Also true of the board's 379 nets: 48 are named by a local label and carry the sheet
title (`/Amp Control/AMP_REM`), so one local label must stay on the same sheet and no
sheet may be re-parented; 125 are auto-named (`Net-(Q21-D)`) and must not gain a label.

## Root decisions (user, 2026-11-19)

**Superseded in session 4: the user asked for labels instead of trunks. Kept as history.**

The root is redrawn before the remaining sheets, and blocks are linked by bus trunks:

- A bus holds nets that do one job and run between the same blocks (the chip
  selects, one driver's control lines, the tach inputs). 2 to 8 members. No
  catch-all bus, no bundling unrelated nets to save wires.
- A net between only two blocks that belongs to no group stays a single wire.
- Every bus entry carries its member label.
- On a child sheet a bus arrives as a hierarchical bus label and leaves the block as
  a bus sheet pin; no global labels there.
- The one root global label per bus is a name tag only; `--strict` must prove every
  member keeps its board name.
- `check_sheet_structure` recognises bus member labels per sheet, for any group
  (done: `bus_members()`), so the count does not rise.
- Do two or three trunks, send the root render, then wait.

Proved by export: a hierarchical bus pin keeps the members' names only while the root
bus carries a global label (without it `SPI_SCK` became `/IMU/SPI_SCK`).

Drawn so far: `{IMU_INT}` (IMU_INT1, IMU_INT2; bus pin on IMU), `{SENSOR_CS}`
(IMU_CS, AMBIENT_CS; labelled entries at IMU and Ambient Temp; more chip selects
join as their sheets convert, split into further groups past 8), and `AMP_REM_EN`
as a single wire. Next trunk candidates: fan/pump PWM and tach lines to Water
Cooling; AMBIENT_INT / AMBIENT_CT from Ambient Temp to GPIO Expander.

### Reviewer on the root sample (2026-11-19): root FAIL, imu FAIL (small), ambient PASS

Gate steps 1 to 5 pass. The reviewer's points are layout choices to settle with the
user before more trunks are drawn; none is fixed yet:

1. IMU_INT2 leaves the right of the ESP32 and runs back under it (4 crossings). Fix:
   move IO39 to the left of the U1 symbol beside IO2 (pin rule, option 3), and more
   generally arrange U1's pins by trunk.
2. Block order: the 6 x 5 grid is in `SHEETS` order, not by function or by which
   trunk feeds a block. Reorder before wiring the other 27 blocks (IMU and Ambient
   Temp in the column beside the chip-select trunk, Amp Control under the left
   channel).
3. `{IMU_INT}` trunk has a jog at its name tag; run it at one column to the pin.
4. Chip-select grouping and names: 15 selects, 2 to 8 per bus. `SENSOR_CS` will not
   describe the group once ADS1220_CS, INA239_CS and ACS_CS join. Decide the groups.
5. `{SENSOR_CS}` name tag sits between two blocks' captions; move it to the top of
   the trunk by U32.
6. imu: the `{IMU_INT}` hierarchical label is on the left of the sheet, its block
   pin on the right. Make them agree.

## Baseline and gate

The baseline is exported from `rev6-schematic` and must equal `HANDOFF_rev6.md`. If
any figure differs, stop and show the user; don't adopt it. The session scratchpad
does not survive, so re-export at the start of a session from a clean checkout of
`rev6-schematic` (the worktree with its changes set aside, or the main checkout with
`-o` pointing at the scratchpad):

```bash
cd hardware/kicad
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KC sch export netlist --format kicadsexpr -o $B/base.net cryocooler.kicad_sch
$KC pcb drc --schematic-parity --severity-all --format json -o $B/drc_base.json cryocooler.kicad_pcb
```

Gate, after every sheet (all passed for the pilot):

1. `git diff --quiet -- hardware/kicad/cryocooler.kicad_pcb hardware/kicad/cryocooler.kicad_dru`
2. `python3 tools/compare_netlists.py --strict $B/base.net $OUT/new.net`: 0 differences
   (497 parts, 379 nets)
3. DRC with `--schematic-parity`: 0 errors, 0 unconnected, 0 parity, 12 warnings
   (6 `silk_edge_clearance`, 4 `silk_over_copper`, 2 `lib_footprint_mismatch`)
4. `gen_schematic.py` check lines all 0; ERC 0; `datasheet_rules` 609/609;
   `verify_netlist` 497 parts / 379 nets; `check_symbols` 0 / 0 / 0
5. `check_sheet_structure.py`: nothing above baseline, `--update-baseline` on a drop
6. `schematic-reviewer` subagent on the changed sheet and the root: PASS

`check_sheet_structure` counts:

| Check | rev6-schematic | after pilot | after root + imu + ambient |
|-------|----------------|-------------|----------------------------|
| global_label | 307 | 306 | 300 |  (287 after the root rearrangement, 283 after the sensor chip selects, 280 after signal_gen, 274 after amp_current, 271 after io_core, 267 after io_expanders, 257 after expansion, 255 after gpio_expander)
| close_label_pair | 69 | 63 | 63 |  (59 after the root rearrangement, 58 after amp_current, 57 after io_expanders, 51 after expansion)
| unmatched_sheet_pin | 0 | 0 | 0 |
| too_many_parts | 2 | 2 | 2 |
| copied_sheet | 2 | 2 | 2 |

## What the pilot changed

- `amp_control`: `AMP_REM` / `AMP_REM_LED` label pairs at D2 are wires, one local
  label each; `AMP_REM_EN` is a hierarchical label; three group headings; R28's text
  pinned beside R28; +12V symbols level; note names Q21 (was Q9, stale).
- Root: `AMP_REM_EN` sheet pin on the Amp Control block, wired to ESP32 IO6; sheet
  blocks snapped to the 1.27 mm grid (rows start 2.5 mm higher so the captions clear
  the frame).
- No other sheet file changed (checked with `git status`).

## Helpers added

- `tools/compare_netlists.py --strict`.
- `tools/kicadgen.py`: renders `hierarchical_label`; `OWN_UUID_SEQUENCE` gives a
  redrawn sheet its own id sequence so the other files stay byte-identical. **Add
  each sheet when it is redrawn**, with the number of ids it used at `rev6-schematic`:
  root 374, power_input 36, signal_gen 255, cooling 214, power_button 179,
  amp_control 72, cold_head 161, rails_logic 157, amp_current 213, imu 69,
  rails_15v 278, power_good 167, system_current 110, indicators 50,
  compressor_relay 62, gpio_expander 76, debug 43, supply_switches 59, display 196,
  ambient 61, io_core 235, io_drivers 302, io_switches 187, io_expanders 229,
  io_precision 240, io_pressure 86, expansion 383, io_ch1 242, io_ch2 242,
  io_ch3 155, io_ch4 155.
- `tools/gen_schematic.py`: `net_label(..., to_parent=True)`; `SHEET_PINS`,
  `ROOT_LINKED`, `BOX_ORIGIN/PITCH/SIZE`, `box_cell`, `sheet_pin_cell`; `root_links()`
  (hand-laid wires and trunks), `bus_entry`, `name_tag`, `bus_taps` (general form of
  `spi_bus`), `BUS_ALIASES`, `ESP_ROOM`; `sheet_symbol` draws pins.
- `tools/check_sheet_structure.py`: `bus_members()` per sheet, any group.
- New rule from the user (2026-11-19) after the `{SPI}` trunk touched U2: nothing
  touches a part it isn't connected to. Written into `hardware-schematic.md` and the
  design skill, and checked as `wire_near_body` (`wires_near_bodies()` in
  `tools/check_symbols.py`: wires, buses and bus entries within 1.9 mm of a body,
  unless they end on that part's pin). Baseline 16, all there before this branch:
  power_button C41 (4), signal_gen R36 and C86 (2 each), cooling R43 (2), expansion
  U123 and U124, display U53 and U54, root R23 and R24 (USB CC resistors). Fix each
  with its sheet; the root pair with the root's own circuits.
- Root rearrangement: `BLOCK_ORDER`, `DECODER_RUN`, the USB group is drawn then
  moved level with the module's USB pins (`shift_since`), ESP32 pin -> net table
  `signals` in `mcu_and_usb`.
- The strict compare caught a real slip here: the redrawn pull-down R19 had its pins
  swapped (same nets, other pin numbers). Fixed; keep running `--strict` every time.
- Temporary, remove when `compressor_relay` is redrawn: `rem_switch(redrawn=...)` and
  `rg_led(labels=...)`. They exist only because the two sheets share the helpers.
- `tools/textlayout.py`: a hierarchical label's text box is sized like a global one.
- Session 3: `retire_power_symbol()`; `gnd_bus(at_end=)`; `place_blocks(pitch=)` and
  `decoupling_block(pitch=)`; `io_label(to_parent=)`; `acs_bus_gates(sh, iso)`;
  `SIGNAL_CS_ROW`, `SIGNAL_GEN_SHIFT`, `AMP_CURRENT_SHIFT`, `ACS_SCK_TURN`. A sheet
  that needs room on its left is drawn, then moved with `shift_since`.

## Skipped or left, and why

- **D2's wiring still has two loops and one crossing.** The LED symbol
  (`APGB0607G22R23C`) has both anodes left and both cathodes right, and the dies are
  anti-parallel. The fix is the pin rule's option 2 (GA+RK on one side, RA+GK on the
  other), but the symbol is used on four other sheets (indicators, power_good, debug,
  one more via `rg_led`), which the pilot may not touch. Needs the user's go.
- `PG_15V` and `SIG_SINE` on amp_control are still global: they need power_good,
  signal_gen and debug converted in the same step.
- Reviewer notes not acted on: J8 sits under D2 and reads as part of the LED group
  (move J8 right); J9's ground symbol is about 1 mm from the no-connect on pin 10
  (lengthen the SLEEVE stub); the root wire IO6 to Amp Control is about 150 mm
  (block order should follow the ESP32 pin sides once more pins are wired).
- Already wrong before this branch, not fixed: four sheet blocks sit under the
  root's title block (the block grid needs a new arrangement, and blocks will have
  to grow as pins are added); amp_control holds two functions (REM switch and the
  signal jack).
- `check_symbols` does not catch a wire drawn along a symbol's body edge (found by
  the reviewer on a first attempt, fixed by hand). Worth adding to the check.
- `gen_schematic.py` rewrites `cryocooler.kicad_pro` with `rgba(...)` colours where
  the committed file has `rgb(...)` (KiCad re-saved it). Same colours. The file now
  has a real change too (the `IMU_INT` and `SENSOR_CS` bus aliases), so it is no
  longer restored and its diff includes the colour-format lines.

## Not in this pass: listed for later

- `io_ch1` / `io_ch2` and `io_ch3` / `io_ch4` are copied sheets (`copied_sheet` 2).
  Making each pair one file placed twice changes the sheet paths, so their
  local nets are renamed (3 each on IO Channel 1 and 2): a board change.
- `rails_15v` and `expansion` are the two sheets over 30 parts. Splitting moves parts
  to a new sheet path, so their local nets are renamed (8 on Expansion): a board change.
- Grouping sheets under parents (power, io) renames every local net below them.
- `mcu_and_usb` has an empty loop (`for pin in ('A12', 'B1', 'B12'): pass`), there
  before this branch. Unused; delete only if the user confirms.
- `sheets/aux_io.kicad_sch` is not referenced by the root or the generator (last
  touched in the rev 5 WIP commit). Unused; delete only if the user confirms.

## Stale figures in other docs (not edited here; the user fixes them separately)

- `.claude/skills/kicad-schematic/SKILL.md`: datasheet_rules 319/319,
  verify_netlist 306 parts / 211 nets (rev 3 figures).
- `.claude/skills/kicad-pcb-edit/SKILL.md`: DRC baseline of 215 warnings (rev 3).
- `hardware/kicad/README.md`, "Review status": "634 datasheet-derived connections".
