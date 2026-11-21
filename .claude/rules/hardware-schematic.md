---
paths:
  - "hardware/**"
  - "include/config/pin_config.h"
---

# Schematic and part selection

The KiCad project is `hardware/kicad/`. Before changing a circuit, read the relevant
sections of its `README.md` (sheets, GPIO map, regeneration) and `DESIGN_REVIEW.md`
(see `hardware-overview.md` for how to read the long docs). Use the
`kicad-schematic` skill to regenerate and check the schematic, library and BOM.

## The schematic is generated

Edit the Python and re-run it. Don't hand-edit the `.kicad_sch` files.

```bash
python3 hardware/kicad/tools/make_lib.py        # lib/cryocooler.kicad_sym
python3 hardware/kicad/tools/gen_schematic.py   # root + sheets/
```

`gen_schematic.py` exits non-zero on a text-overlap failure. Treat that as a failed
build, not a warning.

## Verify every connection against the datasheet

- Check every IC connection against the manufacturer datasheet, not memory, the
  user's draft, or search snippets: pin table, required external parts, unused-pin
  handling, absolute maximums, supply/IO voltages. ERC and netlist comparison can't
  catch a wrong circuit.
- Confirm the exact part number, package, and footprint. Don't rely on naming or a
  similar part's library footprint.
- For leadless packages, check the land-pattern drawing's orientation against the
  pin-configuration figure and the package outline. Vendor drawings are sometimes
  rotated 90°.
- Encode each finding as a rule in `tools/datasheet_rules.py` and record it in
  `DESIGN_REVIEW.md`. Report anything you couldn't verify. Don't assume it's right.
- Every symbol's properties carry a link to the part (supplier or manufacturer
  product page) and a link to its datasheet.
- **Whenever you add a symbol or a net label, write its description in the same
  change.** Every symbol's Description says what the part does in this circuit, not
  what kind of part it is: "Pull-up resistor for the INA239 ALERT output", not
  "Resistor". Name the IC or net it serves, and the network it belongs to (divider, LC
  filter, compensation). An IC's description states its role. Every net label and
  global label carries a Description of what the net carries: source, destination,
  GPIO and active level ("LTC2954 INT# to GPIO1: pulses low when the button asks for
  a shutdown"). The fields stay hidden. The text lives in
  `tools/part_descriptions.py` (`DESCRIPTIONS` by reference, `NET_DESCRIPTIONS` by
  label name); `gen_schematic.py` fails on a part or label without one, and on an
  entry for one that is gone. Update the text when a part's or net's role changes.

## Part selection

- Prefer leadless packages: QFN/VQFN for ICs, and small DFN / XSON / X2SON for logic
  and protection parts. Still check whether the leadless version differs
  electrically, and that a boxed-in centre pad can be escaped.
- Don't reverse a part the user chose (connectors, switches, LEDs, protection parts)
  without flagging it as a reversal (`general.md`). An indicator
  that shows two states (green good / red bad) uses a bi-directional LED: two leads,
  dies anti-parallel. A single-state indicator uses a plain LED. Never fit a
  bi-colour part and leave one die unused.
- Put the reference designator(s) in the customer-reference field when ordering.

## Drawing conventions

Load the `kicad-schematic-design` skill before drawing or tidying a sheet. The rules
that are never bent: supplies point up and grounds point down; no text, wire or symbol
overlaps another; a reference, value or label sits beside its own part; no 4-way
junctions; resistors are US zig-zag (`Device:R_US`); every part and label has a
description of its job. Project-specific detail (helpers, buses, net-class colours)
is in `hardware/kicad/README.md`, "Drawing conventions".

Wires and trunks keep clear of parts:

- **Nothing touches a part it isn't connected to.** A wire, bus or bus entry reaches
  a part only at the end of one of its pins. It never runs along a body outline, ends
  on a body corner, or passes within two grid steps (2.54 mm) of a body it does not
  connect to. A trunk beside an IC reads as going into it. Move the trunk or the
  part. `tools/check_sheet_structure.py` counts these as `wire_near_body`.

Each label type has one scope, and the narrowest one that works is the right one:

- **Wire** inside a block, and between any two points on a sheet closer than 85 mm.
  On the root and on a parent sheet that includes two block pins closer than 85 mm.
- **Net (local) label** to name a net, and for a long run on the same sheet: a plain
  net label on a short wire at each end. This is how blocks more than 85 mm apart are
  joined on the root and on a parent sheet. Don't draw a wire across the sheet, and
  don't use a global label for it.
- **Hierarchical label + sheet pin** for every signal between a sheet and its
  parent. The parent joins the pins: by wire when they are close, by a net label at
  each pin when they are not.
- **Bus** only for a communication bus (SPI, I2C and the like). Chip selects,
  interrupts, address and control lines are single labelled nets, however many of
  them run side by side.
- **Global label** only for nets in `ALLOWED_GLOBALS` in
  `tools/check_sheet_structure.py`: the `{SPI}` bus, and the `{I2C}` bus if one is
  added. Each is drawn as a bus with one global label, like `spi_bus()`. Never on a sheet that
  is placed more than once: a global label shorts every instance into one net. A
  net label must not share its name with a global label anywhere in the project
  (ERC `same_local_global_label`).

Active-low signals:

- **An active-low net label or symbol pin has an overbar** (`~{NAME}`), and no `_N`,
  `#`, `B` or `n` suffix: `~{ADS1220_CS}`, not `ADS1220_CS` or `IO_EXP_INT_N`. A
  symbol pin follows the datasheet's name. A pin whose polarity is programmable
  (MCP23S17 INTA/INTB) keeps its plain name, and its net takes the bar. An enable
  that is high when on stays unbarred (`ESP_EN`, `IO1_SENS_EN`). C++ names can't
  hold a bar, so firmware and the generator keep `_N`: list the net in
  `ACTIVE_LOW` in `tools/active_low.py`, which adds the bar when the label is
  drawn. `_N` meaning the negative side of a pair (`PREC_A_N`) is not active-low.
  `tools/verify_netlist.py` fails on an unbarred active-low net. Barred text is
  drawn at 1.0 mm so the bar clears a row 2.54 mm above; notes write the barred
  name too (`~{KILL}`, not `KILL#`).

Net names and the routed board:

- A net label on the root names the net `/NAME`; on a sheet, `/Sheet/NAME`. Changing
  a net's label type, or moving its sheet under a parent, renames it.
- When a drawing change renames nets, rename them on the board in the same step with
  `tools/rename_board_nets.py`, and after moving a sheet run
  `tools/relink_board_sheets.py`. Both change names in the board file and nothing
  else, and refuse to write otherwise. No pad, track, via or zone may move.
  `tools/compare_netlists.py --strict --renamed` must then show 0 differences.

Pull resistors:

- A pull-up or pull-down is drawn on the line it serves, the pull-up standing above
  the line and the pull-down hanging below it. No separate "bias" block joined by
  labels. (Decoupling capacitors are the one group that does sit apart.)

Sheets can nest:

- A sheet that holds several related functions can be a parent with child
  sheets (any depth). Keep it to what a reader can follow, usually two or
  three levels.
- A signal that crosses more than one level goes up through each one: a
  hierarchical label on the child, a sheet pin on its block in the parent,
  and so on up to where it is used. Net labels never cross a sheet boundary,
  and a deep connection is not a reason for a global label.
- Moving a sheet under a new parent renames its local nets (the sheet path is
  part of the name). Treat it as a connectivity change: it reaches the PCB.

Symbol pins:

- **Arrange a symbol's pins for the circuit it's drawn in, not the package.**
  In order of preference:
  1. **Keep pins grouped by function**: inputs and control together, outputs
     together, a bus's pins together and in order (D0 to D7, Q0 to Q9).
     Default sides: inputs and control on the left, outputs on the right.
  2. **Move a whole group to another side** when that makes the sheet read
     better, for example when the outputs feed a block to the left, or a
     control group faces the part that drives it.
  3. **Move a single pin out of its group** only when it removes a crossing,
     a long detour or a label: put the pin where its net already is. Most
     pins should still sit in their group.
  Supply pins are always on the top edge, pointing up, and ground pins on the
  bottom edge, pointing down. No exception for any of the three options.
  Keep the pin numbers; only the drawing moves (`from_stock` in
  `tools/make_lib.py`).

No shortcuts. If the generator can't draw something the right way, extend the
generator. Never add a global label, a label pair or a `GLOBAL_NETS` entry to avoid
routing a wire, and never raise a limit or the baseline in
`tools/sheet_structure_baseline.json` to make a check pass. The baseline only goes
down. A rule that seems wrong for a case is a question for the user, not a reason to
skip it.

## Keep hardware and firmware in sync

The GPIO map must agree across `include/config/pin_config.h`, the schematic, and the
`README.md` hardware table. Change them together, then run
`tools/verify_netlist.py` on a `kicad-cli sch export netlist` output.
`tools/compare_netlists.py` confirms that a layout-only change didn't change
connectivity.
