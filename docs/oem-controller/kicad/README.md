# OEM controller schematics (KiCad 10)

These are transcriptions of the electrical schematics in **US6098409** (and its continuation US6256999, whose drawings
are identical). Open [oem-controller.kicad_pro](oem-controller.kicad_pro) in KiCad 10.

## Hierarchy

```
oem-controller.kicad_sch                  root: one sheet per patent PDF that contains schematics
└── sheets/US6098409.kicad_sch            US6098409 (= US6256999)
    ├── US6098409_fig5a.kicad_sch         FIG 5A    mother board (redrawn: three child sheets)
    │   └── US6098409_fig5a_<child>.kicad_sch   conn, reset, spares
    ├── US6098409_fig5b.kicad_sch         FIG 5B
    ├── US6098409_fig5c.kicad_sch         FIG 5C-1 + 5C-2 (redrawn: seven child sheets)
    │   └── US6098409_fig5c_<child>.kicad_sch   sum, cmt, hog, trip, clamp, counter, buffer
    ├── US6098409_fig5d.kicad_sch         FIG 5D-1..3  (six "butter warmer" heater drivers)
    ├── US6098409_fig5e.kicad_sch         FIG 5E
    ├── US6098409_fig5f.kicad_sch         FIG 5F-1 + 5F-2 (redrawn: seven child sheets)
    │   └── US6098409_fig5f_<child>.kicad_sch   ref10, ref5va, ref10v, dcdc, monitor, regs, digital
    ├── US6098409_fig5g.kicad_sch         FIG 5G-1..4  (microcontroller)
    ├── US6098409_fig5h.kicad_sch         FIG 5H-1..3
    ├── US6098409_fig6a.kicad_sch         FIG 6A-1 + 6A-2  daughter board
    ├── US6098409_fig6b.kicad_sch         FIG 6B-1 + 6B-2
    └── US6098409_fig6c.kicad_sch         FIG 6C
```

US6446444 has no circuit schematics (its FIG 6 is a block diagram), so it has no sheet here.
Each page carries its title and source sheet number in the top-left corner.

## How the pages are drawn

- **Electrically exact.** Each page keeps the patent figure's parts, values and connections, and its order of stages.
- **Drawing (being redrawn).** The pages were first drawn with a label on most pins and a global label for every
  signal that appears on more than one figure (e.g. `NSP_CLK`, `BWT_1P`, `CS_CTRL`). They are being redrawn to the
  repo-wide drawing rules: wires inside a block, hierarchical labels and sheet pins between figures, no global
  labels. See "Schematic profile" below; what is left is counted in `schematic_structure_baseline.json`.
  Progress is in [HANDOFF_redraw.md](HANDOFF_redraw.md). Until every figure is redrawn, the patent sheet joins a
  redrawn figure's sheet pins to the other figures with a global label on each pin.
- **Refs and values are exactly as printed.**
  - Where the patent prints the same ref twice on one figure, the later one gets a `B`/`C` suffix.
  - Where a ref appears on more than one figure (the patent reuses designators, and the daughter board restarts at
    R1/J1/V1), the generator adds the figure id (`R16_5D`).
  - In both cases the printed ref is kept in the `Printed_Ref` field.
  - Illegible or unprinted values are `?`. Other fields: `Note` (transcriber remarks) and `Probable_Part`
    (identification guesses, never replacing the printed value).
- Every IC uses a **transcription symbol** (`lib/oem_patent.kicad_sym`) with pins numbered and named as printed. These
  are not verified against datasheets. The patent drawings are the reference, including any errors in them.
- Op-amp supply pins show only their numbers; the power symbol on each stub names the rail.
- Unused pins carry the no-connect marker on a short stub, clear of the pin number. A local label
  next to a global-label flag or power symbol gets a longer stub, so the texts don't touch.
- No footprints and no PCB. This is a reading aid, not a design.

See [TRANSCRIPTION_NOTES.md](TRANSCRIPTION_NOTES.md) for every anomaly, uncertainty and identification guess, per figure.

## Schematic profile

How this project applies the repo-wide drawing rules (`.claude/rules/schematic-drawing.md`, the
`kicad-schematic-design` skill).

| | |
|---|---|
| Root sheet | `oem-controller.kicad_sch` (project `oem-controller.kicad_pro`) → `sheets/US6098409.kicad_sch` → one sheet per patent figure |
| Made by | `tools/gen_oem_schematic.py` from `specs/<figure>.py`, with `tools/oemsch.py`; never hand-edit the `.kicad_sch` files. See "Regenerating and checking" |
| Descriptions | A part's hidden **Description** says what it is: the printed part's own description (`PART_INFO` in `tools/oemsch.py`), "Assumed part: ..." from `probable=`, or its kind and value. Its hidden **Function** field is its job in this circuit, from `desc=` on `P()`. Labels get a Description from `NET_DESCRIPTIONS` in the figure spec. For a redrawn spec (`REDRAWN = True`) the generator fails on a part or label without one, and on an entry for a label that is gone. Figures not yet redrawn have none |
| Check config | `schematic_checks.json`: no global labels allowed, 30 parts per sheet, 85 mm, baseline `schematic_structure_baseline.json` |
| Checks | `tools/check.sh <out>` (ERC summary, `verify_netlist.py`, text overlap: 0 problems; ERC `label_dangling`, `pin_not_driven` and `power_pin_not_driven` counts are expected), `hardware/kicad/tools/check_symbols.py` on the root, `hardware/kicad/tools/check_sheet_structure.py --project docs/oem-controller/kicad/oem-controller.kicad_pro` |
| Connectivity gate | `verify_netlist.py` (netlist matches the specs) and `hardware/kicad/tools/compare_netlists.py --strict --renamed` against a baseline netlist: every printed ref, value and pin on the same net as before. A net may change name only by its sheet path |
| Routed board | None. Sheet-path prefixes on net names are free to change |
| Net names | The patent's printed signal names, exactly as printed, as the label text (`NSP_CLK`, `RAW_SHUTO_T-`); no renaming and no overbar added. Unnamed nodes keep the `<figure>_<part>_<pin>`-style names from the specs. A printed off-page flag that no transcribed figure uses (`+SUREF`, `80_RESET`, `OF_OFFSET`) is a net label on its own sheet: it names the net and connects to nothing elsewhere |
| Helpers | `P()` and the `KINDS`, `POWER` and `SYMBOLS` tables in `tools/oemsch.py`. Redrawn figures: `child()` (a child sheet and its block), `port()` (hierarchical label + sheet pin), `tap()` (a free wire end for a power symbol or label), `build_node()`; `WIRES` ends are `REF.PIN`, `CHILD:NET` or `@tap`, routed `'hv'`, `'vh'` or through listed corners; `names=` picks where a net's label or power symbol sits (`None` keeps a net unnamed). `P(text=(dcol, drow))` pins a part's reference and value where the automatic placer crowds them. A tap in the middle of a wire joins it only if routes run through it. `build_node()` fails on a point where four or more connections meet (`check_junctions()`). Gates are drawn in their standard shapes from a `SYMBOLS` entry with `gate:` (`nand`, `or_inv`, `inv`; `gate_symbol()`). Unredrawn figures still use `build_sheet()` and L-shaped `WIRES` |

**Exceptions** (deliberate; everything else follows the rules):

1. **One sheet per patent figure.** The sheet list mirrors the patent so each page can be checked against its figure.
   A figure that holds several functions gets child sheets for them (FIG 5D's six heater drivers are one child
   sheet placed six times). The 30-part limit applies to those child sheets, not to the figure page that holds them.
2. **Placement follows the figure's order of stages** (left to right as printed, turned upright) so a reader can
   hold the page next to the patent. Within that, the drawing rules win: wires, grouping, supplies up and grounds
   down.
3. **Refs, values, pin numbers, pin names and signal names stay exactly as printed**, including the patent's errors.
   Corrections go in `Note` and `TRANSCRIPTION_NOTES.md`, never in the drawing. One user-approved exception:
   FIG 5A U17 (74HC153) shows the datasheet pin names (A, B, ~{2G}, 2C0-2C3, 2Y) on its printed pin numbers,
   because the printed names were misleading; the printed names are in its `Note`.
4. **Symbols are transcription symbols** (pins as printed, not checked against datasheets). Their pins may still be
   arranged by function; numbers and names don't change.
5. **Descriptions say where they come from:** "Patent: ..." (with the column or figure), "Inferred from the circuit:
   ...", or "Role unknown". Electrical accuracy comes first: never invent or "fix" circuitry to make a description
   fit.
6. **Temporary: global-label bridge on the patent sheet** (`bridge_to_globals()`). A redrawn figure's sheet pins
   end on global labels there while the figures it connects to are still in the old drawing. Each one is
   replaced by a sheet pin with a wire or net label once all its partner figures are redrawn
   (`join_figures()`; FIG 5B-5C OF_SET is the first); the exception ends when the last figure is done
   (user, 2026-11-21).

## Regenerating and checking

Specs live in `specs/<figure>.py`: a parts list with positions and pin-to-net maps. The generator is in `tools/`.

```bash
docs/oem-controller/kicad/tools/check.sh /tmp/oem-build                 # build all into a scratch dir: ERC, netlist check, PDF
docs/oem-controller/kicad/tools/check.sh /tmp/oem-build fig5c fig5g     # only some figures
python3 -I docs/oem-controller/kicad/tools/gen_oem_schematic.py         # write the real project files here
```

`check_text_overlap.py` (run by `check.sh` on KiCad's SVG export) reports any text that overlaps
other text or is crossed by a line (wire, symbol outline, pin, label flag, frame), and any wire that
runs through a symbol body. All pages currently pass with 0 problems.

`verify_netlist.py` checks that KiCad's exported connectivity matches the specs exactly. Two pins share a KiCad net
if and only if they share a net in the spec, which catches wires that accidentally short or split nets. ERC reports
"isolated pin label" (a signal that appears on only one transcribed page) and "power pin not driven" (no PWR_FLAGs on
transcribed pages); both are expected.
