# Fabrication files

`cryocooler_jlcpcb.zip` is the upload for JLCPCB: Gerbers (Protel extensions, X2
attributes) and Excellon drill files (PTH and NPTH separate, mm, absolute origin)
made from `cryocooler.kicad_pcb` (4 layers, 130 x 100 mm). `gerbers/` holds the same
files plus the drill maps and report; nothing in it is hand-edited.

Regenerate after any board change (zones must already be filled; the generator and
`link_usb_vbus.py` leave them filled, so do not use `--check-zones`, which refills
and rewrites the board):

```bash
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts \
   --subtract-soldermask -o fabrication/gerbers/ cryocooler.kicad_pcb
$K pcb export drill --format excellon --excellon-separate-th --excellon-units mm \
   --excellon-zeros-format decimal --drill-origin absolute --generate-map --map-format pdf \
   --generate-report --report-path fabrication/gerbers/drill_report.txt \
   -o fabrication/gerbers/ cryocooler.kicad_pcb
```

## Order settings to check

* 4 layers, 130 x 100 mm, 1.6 mm, 1 oz copper, no impedance control.
* Design minimums: 0.15 mm track / clearance, 0.2 mm smallest drill, 0.3 mm board
  edge clearance.
* **Via-in-pad:** the IMU (U19), INA239 (U23) and AD9833 (U4) ground pads use 0.35 mm
  pads with 0.2 mm drills (0.075 mm ring), placed inside 0.5 mm pitch pads. Check
  JLCPCB's current via and ring limits and its via-filling option before paying; if
  they are too small the vias need enlarging and the pad connections reworking.
* Back silkscreen carries the cryocooler logo and title; check the viewer shows it
  mirrored correctly from the back.

The drill report lists every hole size: 0.2 mm (24), 0.3 mm (332 vias), 0.35 mm (10),
component holes 0.6 to 1.3 mm, and 3.2 mm mounting holes.
