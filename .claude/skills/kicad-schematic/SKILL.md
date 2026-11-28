---
name: kicad-schematic
description: Regenerate the KiCad schematic, symbol library, footprints or BOM from the Python generators in hardware/kicad/tools, and run the schematic checks (ERC, netlist, datasheet rules, GPIO map, symbol checks, sine-chain sim). Use when changing a part, value, connection or sheet, adding a symbol or footprint, refreshing the BOM, or verifying the schematic after any hardware change.
---

# Schematic: regenerate and check

The `.kicad_sch` files, `lib/cryocooler.kicad_sym` and `lib/cryocooler.pretty` are
generated. Edit the Python and re-run; never hand-edit the outputs. How a sheet should be drawn
is in the `kicad-schematic-design` skill and `.claude/rules/schematic-drawing.md` (this project's profile: `hardware/kicad/README.md`, "Schematic profile"); the helpers in `gen_schematic.py` are in
`hardware/kicad/README.md` ("Drawing conventions", "Regenerating"). Layout rules are in `.claude/rules/hardware-pcb.md`. Current
board state: the handoff named in the board profile (`hardware/kicad/README.md`).

These scripts don't need `pcbnew`, so the system `python3` works. Run from
`hardware/kicad/`:

```bash
cd hardware/kicad
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli    # KiCad 10.0.6
OUT=<session scratchpad>                                     # not the repo
```

## Regenerate

```bash
python3 tools/make_lib.py          # lib/cryocooler.kicad_sym
python3 tools/make_footprints.py   # lib/cryocooler.pretty (only when a vendor footprint changed)
python3 tools/gen_schematic.py     # root + sheets/*.kicad_sch; in cryocooler.kicad_pro the sheet list, SPI bus alias and net-class colours
```

`gen_schematic.py` exits 1 on any text overlap, wire drawn across a label,
duplicate reference, 4-way junction, or part or net label without a description
in `tools/part_descriptions.py` (what the part does, what the net carries). Add
the entry when you add the symbol or label. It also fails on wire geometry
(`check_geometry`): a pin or label within 0.05 mm of a wire but not on it, a
pin in the middle of a wire with no junction or wire end, a diagonal wire, a
wire under 1 mm, and a net whose hierarchical or global labels differ in shape
on one sheet. It prints the count for each check, so read the output, not just
the exit code. Unit tests for these checks:
`python3 -m unittest discover -s tools/tests` from `hardware/kicad/`.

- Every sheet is rewritten. UUIDs reshuffle after an inserted part (diff noise).
  The handoff notes the D13 Product link in `sheets/indicators.kicad_sch` also
  changes on the next regeneration.
- Part and datasheet links come from `tools/part_links.py`. Orderable part numbers
  come from the tables in `tools/gen_bom.py`.
- Every new part must be checked against its datasheet first (`.claude/rules/hardware-schematic.md`).
  Encode critical connections as a rule in `tools/datasheet_rules.py`.

## Check (run all after every schematic change)

```bash
$KC sch erc --severity-all --exit-code-violations --format json -o $OUT/erc.json cryocooler.kicad_sch
$KC sch export netlist --format kicadsexpr -o $OUT/new.net cryocooler.kicad_sch
python3 tools/datasheet_rules.py $OUT/new.net     # exits 1 on any failed rule
python3 tools/verify_netlist.py $OUT/new.net      # GPIO map vs pin_config.h, footprints, single-pin nets
python3 tools/check_symbols.py cryocooler.kicad_sch
python3 tools/check_sheet_structure.py            # label scope, label pairs, sheet size, copied sheets (schematic_checks.json)
python3 sim/run_ngspice.py sim/sine_chain_ideal.cir   # only when the signal chain changed
```

Expected counts (ERC, `datasheet_rules` rules passed, parts and nets in
`verify_netlist`, `check_symbols`, the sine-chain levels) are in the "Checks" section
of the current handoff. If the counts change, make sure the change was intended and
update the handoff. `make sch-checks` runs the checks that need no extra setup.
`gen_schematic.py` also runs geometry self-checks (near miss, pin mid-wire, diagonal
wire, stub, label shape) and fails on any.

- Run ERC on the root. Sub-sheets can't be checked on their own. ERC JSON positions
  are in 1/100 mm.
- **Layout-only change** (moved symbols or wires): export a baseline netlist before
  editing, then `python3 tools/compare_netlists.py $OUT/base.net $OUT/new.net`.
  Connectivity must match. Two-pin passives may be flipped.
- **Drawing-only change with the board frozen:** add `--strict`. It compares every
  reference's value and footprint and every net's exact name and pins, and lists each
  difference. It must report 0, or the routed board no longer matches.
- **Look at it:** `$KC sch export pdf -o $OUT/sch.pdf cryocooler.kicad_sch`, then
  `gs -sDEVICE=png16m -r150 -o $OUT/page%02d.png $OUT/sch.pdf` (there's no pdftoppm).
  Check the page you changed.

## BOM and CPL

```bash
python3 tools/gen_bom.py   # bom/cryocooler_bom_digikey.csv, _mouser.csv, _full.csv (JLCPCB), cryocooler_cpl.csv
```

The netlist sets quantities and designators. The CPL is read from
`cryocooler.kicad_pcb`, so re-run this after the board changes too. See
`bom/README.md` for the `MPN basis` column, `LCSC_PARTS` and `ROTATION_OFFSETS`.

## IMU board (`imu/`)

The IMU board is its own project with its own generator and rule set (see
`README.md`, "IMU board"):

```bash
python3 tools/gen_imu_schematic.py                 # imu/imu.kicad_sch and imu.kicad_pro
$KC sch erc --severity-all imu/imu.kicad_sch       # 0
$KC sch export netlist -o $OUT/imu.net imu/imu.kicad_sch
python3 tools/datasheet_rules.py --imu $OUT/imu.net   # RULES_IMU, 25 of 25
python3 tools/verify_netlist.py $OUT/imu.net       # skips the GPIO map (no ESP32)
python3 tools/check_sheet_structure.py --project imu/imu.kicad_pro   # 0 on every count
python3 tools/gen_bom.py --imu                     # imu/bom/imu_*.csv
```

## KiCad gotchas the generator already handles (don't break them in kicadgen.py)

- A pin or junction in the middle of a wire isn't connected. Wires are split at pins.
- `(justify center)` is invalid: KiCad silently drops every later part from the
  netlist. Leave out justify for centred text.
- Field text angle stays 0 on 0/180-degree parts. 180 renders upside down.
- The "automatically fixed" dialog on load means the output differs from KiCad's
  canonical form. To diagnose, run `$KC sch upgrade --force` on a copy and diff it
  against the generator output.

## References

R, C and D were renumbered once (`tools/renumber_refs.py`, `tools/ref_map.py`). Older
notes, commits and the older `tools/*_board.py` scripts use the old numbers. Translate
them with the `ref_map*.py` tools.

## Next

A connection or footprint change has to reach the board too: see the
`kicad-pcb-edit` skill (`gen_pcb.py link`, then DRC with schematic parity and
`board_checks.py`).
