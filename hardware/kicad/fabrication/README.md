# Fabrication files

`cryocooler_jlcpcb.zip` is the upload for JLCPCB: Gerbers (Protel extensions, X2
attributes) and Excellon drill files (PTH and NPTH separate, mm, absolute origin)
made from `cryocooler.kicad_pcb` (4 layers, 130 x 110 mm). `gerbers/` holds the same
files plus the drill maps and report; nothing in it is hand-edited.

These files, the zip and the front / back renders (`circuit-board-render-front.png`,
`circuit-board-render-back.png`) are regenerated automatically by `tools/export_fab.py`,
which `gen_pcb.py` (every mode) and `link_usb_vbus.py` run after they write the board. After a
manual edit of `cryocooler.kicad_pcb` (for example a hand-routed fix), run it yourself:

```bash
python3 hardware/kicad/tools/export_fab.py     # needs kicad-cli; about 30 s
SKIP_FAB_EXPORT=1 ...                          # set this to skip the export while iterating
```

Zones must already be filled (the generators leave them filled). The Gerber headers carry a
creation date, so the files differ in git after every export even if the board did not change.

## Order settings to check

* 4 layers, 130 x 110 mm, 1.6 mm, 1 oz copper, no impedance control.
* Design minimums: 0.15 mm track / clearance, 0.2 mm smallest drill, 0.3 mm board
  edge clearance.
* **Via-in-pad:** the INA239 (U23) and AD9833 (U4) ground pads use 0.35 mm
  pads with 0.2 mm drills (0.075 mm ring), placed inside 0.5 mm pitch pads. Check
  JLCPCB's current via and ring limits and its via-filling option before paying; if
  they are too small the vias need enlarging and the pad connections reworking.
* Back silkscreen carries the cryocooler logo and title; check the viewer shows it
  mirrored correctly from the back.

The drill report lists every hole size: 0.2 mm (19), 0.3 mm (394 vias), 0.35 mm (7),
component holes 0.6 to 1.3 mm, and 3.2 mm mounting holes.
