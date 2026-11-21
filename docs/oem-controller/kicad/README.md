# OEM controller schematics (KiCad 10)

These are transcriptions of the electrical schematics in **US6098409** (and its continuation US6256999, whose drawings
are identical). Open [oem-controller.kicad_pro](oem-controller.kicad_pro) in KiCad 10.

## Hierarchy

```
oem-controller.kicad_sch                  root: one sheet per patent PDF that contains schematics
└── sheets/US6098409.kicad_sch            US6098409 (= US6256999)
    ├── US6098409_fig5a.kicad_sch         FIG 5A    mother board
    ├── US6098409_fig5b.kicad_sch         FIG 5B
    ├── US6098409_fig5c.kicad_sch         FIG 5C-1 + 5C-2
    ├── US6098409_fig5d.kicad_sch         FIG 5D-1..3  (six "butter warmer" heater drivers)
    ├── US6098409_fig5e.kicad_sch         FIG 5E
    ├── US6098409_fig5f.kicad_sch         FIG 5F-1 + 5F-2
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
| Descriptions | Not stored yet. To add: a `desc=` argument on `P()` and a per-spec `NET_DESCRIPTIONS` dict, written to each symbol's and label's Description field, and a generator failure on a part or label without one |
| Check config | `schematic_checks.json`: no global labels allowed, 30 parts per sheet, 85 mm, baseline `schematic_structure_baseline.json` |
| Checks | `tools/check.sh <out>` (ERC summary, `verify_netlist.py`, text overlap: 0 problems; ERC `label_dangling`, `pin_not_driven` and `power_pin_not_driven` counts are expected), `hardware/kicad/tools/check_symbols.py` on the root, `hardware/kicad/tools/check_sheet_structure.py --project docs/oem-controller/kicad/oem-controller.kicad_pro` |
| Connectivity gate | `verify_netlist.py` (netlist matches the specs) and `hardware/kicad/tools/compare_netlists.py --strict --renamed` against a baseline netlist: every printed ref, value and pin on the same net as before. A net may change name only by its sheet path |
| Routed board | None. Sheet-path prefixes on net names are free to change |
| Net names | The patent's printed signal names, exactly as printed, as the label text (`NSP_CLK`, `RAW_SHUTO_T-`); no renaming and no overbar added. Unnamed nodes keep the `<figure>_<part>_<pin>`-style names from the specs |
| Helpers | `WIRES` in a spec (L-shaped wire between two pins' stubs), `P()` and the `KINDS`, `POWER` and `SYMBOLS` tables in `tools/oemsch.py`. A helper for hierarchical labels, sheet pins and child sheets is still to be added |

**Exceptions** (deliberate; everything else follows the rules):

1. **One sheet per patent figure.** The sheet list mirrors the patent so each page can be checked against its figure.
   A figure that holds several functions gets child sheets for them (FIG 5D's six heater drivers are one child
   sheet placed six times). The 30-part limit applies to those child sheets, not to the figure page that holds them.
2. **Placement follows the figure's order of stages** (left to right as printed, turned upright) so a reader can
   hold the page next to the patent. Within that, the drawing rules win: wires, grouping, supplies up and grounds
   down.
3. **Refs, values, pin numbers, pin names and signal names stay exactly as printed**, including the patent's errors.
   Corrections go in `Note` and `TRANSCRIPTION_NOTES.md`, never in the drawing.
4. **Symbols are transcription symbols** (pins as printed, not checked against datasheets). Their pins may still be
   arranged by function; numbers and names don't change.
5. **Descriptions say where they come from:** "Patent: ..." (with the column or figure), "Inferred from the circuit:
   ...", or "Role unknown". Electrical accuracy comes first: never invent or "fix" circuitry to make a description
   fit.

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
