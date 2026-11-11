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

## Part selection

- Prefer leadless packages: QFN/VQFN for ICs, and small DFN / XSON / X2SON for logic
  and protection parts. Still check whether the leadless version differs
  electrically, and that a boxed-in centre pad can be escaped.
- Don't reverse a part the user chose (connectors, switches, LEDs, protection parts)
  without flagging it as a reversal (`general.md`). The user prefers bi-colour LEDs
  (green good / red bad in one part) where they fit.
- Put the reference designator(s) in the customer-reference field when ordering.

## Drawing conventions

Power symbols upright (supplies up, grounds down), US zig-zag resistors
(`Device:R_US`), and signal flow left to right. Supplies are shared rails with
decoupling hanging off them. Use wires rather than net labels except for global
signals. Each IC's bypass caps sit in a labelled block at the side of the sheet. No
text may overlap other text or a symbol body. The full description is in
`hardware/kicad/README.md`, "Drawing conventions".

## Keep hardware and firmware in sync

The GPIO map must agree across `include/config/pin_config.h`, the schematic, and the
`README.md` hardware table. Change them together, then run
`tools/verify_netlist.py` on a `kicad-cli sch export netlist` output.
`tools/compare_netlists.py` confirms that a layout-only change didn't change
connectivity.
