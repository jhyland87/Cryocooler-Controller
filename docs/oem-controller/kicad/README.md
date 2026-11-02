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

- **Electrically exact, visually simplified.** Each page keeps the patent figure's placement and signal flow. To keep
  the netlist exact without hand-routing hundreds of wires, though, most connections are made by **net labels**:
  every pin gets a short wire stub that ends in a label, a power symbol or a global label. Short local connections
  are drawn as real wires.
- **Global labels** are signals that appear on more than one figure (e.g. `NSP_CLK`, `BWT_1P`, `CS_CTRL`). The daughter
  board connects to the mother board through those names.
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
