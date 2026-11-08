---
name: kicad-schematic
description: Regenerate the KiCad schematic, symbol library, footprints or BOM from the Python generators in hardware/kicad/tools, and run the schematic checks (ERC, netlist, datasheet rules, GPIO map, symbol checks, sine-chain sim). Use when changing a part, value, connection or sheet, adding a symbol or footprint, refreshing the BOM, or verifying the schematic after any hardware change.
---

# Schematic: regenerate and check

The `.kicad_sch` files, `lib/cryocooler.kicad_sym` and `lib/cryocooler.pretty` are
generated. Edit the Python and re-run; never hand-edit the outputs. Drawing rules
(upright power symbols, `R_US`, hand-laid sheets, the no-overlap text rule, the
helpers in `gen_schematic.py`) are in `hardware/kicad/README.md` ("Drawing
conventions", "Regenerating"). Layout rules are in `hardware/AGENTS.md`. Current
board state: `hardware/HANDOFF_rev3.md`.

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
python3 tools/gen_schematic.py     # root + sheets/*.kicad_sch, and the sheet list in cryocooler.kicad_pro
```

`gen_schematic.py` exits 1 on any text overlap, duplicate reference or 4-way
junction. It prints the count for each check, so read the output, not just the
exit code.

- Every sheet is rewritten. UUIDs reshuffle after an inserted part (diff noise).
  The handoff notes the D13 Product link in `sheets/indicators.kicad_sch` also
  changes on the next regeneration.
- Part and datasheet links come from `tools/part_links.py`. Orderable part numbers
  come from the tables in `tools/gen_bom.py`.
- Every new part must be checked against its datasheet first (`hardware/AGENTS.md`).
  Encode critical connections as a rule in `tools/datasheet_rules.py`.

## Check (run all after every schematic change)

```bash
$KC sch erc --severity-all --exit-code-violations --format json -o $OUT/erc.json cryocooler.kicad_sch
$KC sch export netlist --format kicadsexpr -o $OUT/new.net cryocooler.kicad_sch
python3 tools/datasheet_rules.py $OUT/new.net     # exits 1 on any failed rule
python3 tools/verify_netlist.py $OUT/new.net      # GPIO map vs pin_config.h, footprints, single-pin nets
python3 tools/check_symbols.py cryocooler.kicad_sch
python3 sim/run_ngspice.py sim/sine_chain_ideal.cir   # only when the signal chain changed
```

Expected (from `HANDOFF_rev3.md` "Checks", 2026-11-06): ERC 0, `datasheet_rules`
319 of 319, `verify_netlist` no mismatches with 306 parts and 211 nets,
`check_symbols` 0 in all four checks. Sine chain: 0, 2.49, 4.98, 7.47 and 9.96 Vpp
at codes 0, 4096, 8192, 12288 and 16383. If the counts change, make sure the change
was intended and update the handoff.

- Run ERC on the root. Sub-sheets can't be checked on their own. ERC JSON positions
  are in 1/100 mm.
- **Layout-only change** (moved symbols or wires): export a baseline netlist before
  editing, then `python3 tools/compare_netlists.py $OUT/base.net $OUT/new.net`.
  Connectivity must match. Two-pin passives may be flipped.
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

## KiCad gotchas the generator already handles (don't break them in kicadgen.py)

- A pin or junction in the middle of a wire isn't connected. Wires are split at pins.
- `(justify center)` is invalid: KiCad silently drops every later part from the
  netlist. Leave out justify for centred text.
- Field text angle stays 0 on 0/180-degree parts. 180 renders upside down.
- The "automatically fixed" dialog on load means the output differs from KiCad's
  canonical form. To diagnose, run `$KC sch upgrade --force` on a copy and diff it
  against the generator output.

## References

R, C and D were renumbered on 2026-11-06 (`tools/renumber_refs.py`, `tools/ref_map.py`).
Older notes, commits, `tools/rev3_board.py` and `tools/rev3_placement.json` use the
old numbers. Translate them with `tools/ref_map_rev3.py`.

## Next

A connection or footprint change has to reach the board too: see the
`kicad-pcb-edit` skill (`gen_pcb.py link`, then DRC with schematic parity).
