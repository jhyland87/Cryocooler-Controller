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

The drawing rules for every schematic are in `schematic-drawing.md` and the
`kicad-schematic-design` skill. This project's schematic profile (generator, checks,
helpers) is in `hardware/kicad/README.md`, "Schematic profile". What is specific to
this project:

- **Allowed global labels:** the `{SPI}` bus, and the `{I2C}` bus if one is added
  (`allowed_globals` in `hardware/kicad/schematic_checks.json`). Each is drawn as a
  bus with one global label, like `spi_bus()`. A net label must not share its name
  with a global label anywhere in the project (ERC `same_local_global_label`).
- **Active-low nets:** C++ names can't hold a bar, so firmware and the generator
  keep `_N`. List the net in `ACTIVE_LOW` in `tools/active_low.py`, which adds the
  bar when the label is drawn. A symbol pin follows the datasheet's name; a pin
  whose polarity is programmable (MCP23S17 INTA/INTB) keeps its plain name and its
  net takes the bar. An enable that is high when on stays unbarred (`ESP_EN`).
  `_N` meaning the negative side of a pair (`PREC_A_N`) is not active-low.
  `tools/verify_netlist.py` fails on an unbarred active-low net. Barred text is
  drawn at 1.0 mm so the bar clears a row 2.54 mm above; notes write the barred
  name too (`~{KILL}`, not `KILL#`).
- **The board is routed, so net names matter.** When a drawing change renames nets,
  rename them on the board in the same step with `tools/rename_board_nets.py`, and
  after moving a sheet run `tools/relink_board_sheets.py`. Both change names in the
  board file and nothing else. No pad, track, via or zone may move.
  `tools/compare_netlists.py --strict --renamed` must then show 0 differences.
- **Symbol pins** are re-laid out by function with `from_stock` in
  `tools/make_lib.py`; pin numbers never change.
- **Descriptions** live in `tools/part_descriptions.py` (above).

## Keep hardware and firmware in sync

The GPIO map must agree across `include/config/pin_config.h`, the schematic, and the
`README.md` hardware table. Change them together, then run
`tools/verify_netlist.py` on a `kicad-cli sch export netlist` output.
`tools/compare_netlists.py` confirms that a layout-only change didn't change
connectivity.
