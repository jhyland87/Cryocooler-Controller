# Brief: transcribe patent schematic figures into KiCad spec files

You are transcribing hand-drawn circuit schematics from patent US6098409 (Superconductor Technologies, 1998; cryocooler temperature controller: FIGS 5A-5H = mother board, 6A-6C = daughter board) into Python "spec" files that a generator turns into KiCad 10 schematic pages. The user is reverse-engineering this OEM controller, so **electrical accuracy is everything**: every part, value, pin number and connection exactly as drawn. Never invent or "fix" circuitry. Never guess silently.

## Files
- Project: /Users/justinhyland/Documents/PlatformIO/Projects/260216-211115-esp32dev/docs/oem-controller/kicad
- Generator + helpers: `tools/oemsch.py` (read it: `P()` signature, KINDS table, POWER table, box_symbol/opamp_symbol), `tools/gen_oem_schematic.py`, `tools/verify_netlist.py`, `tools/check.sh`.
- **Worked example:** `specs/fig5h.py` (partial FIG 5H-2 ambient channel). Copy its style.
- Source PDF: `docs/oem-controller/US6098409/US6098409.pdf`. PDF page N = drawing sheet N-1. Low-res copies: `docs/oem-controller/US6098409/source-pages/p-NN.png`. For reading, render high-res crops yourself, e.g. `pdftoppm -r 400 -gray -png -f N -l N <pdf> $W/pN` then crop/rotate with `python3 -I` + PIL (many sheets are drawn rotated 90°) and Read the crops. Zoom until every ref/value/pin number is certain.
- Your scratch dir: `$W` (given in your task). Write nothing outside `$W` except your own spec files `specs/<fig>.py`.

## Spec format (`specs/<fig>.py`)
```python
from oemsch import P
TITLE = 'FIG 5B - <short functional description>'
SOURCE = 'US6098409 sheet 5 of 25 (PDF p6)'
PAPER = 'A2'            # A2 (594x420 mm = ~467x330 cells) or A1 for very dense figures
SYMBOLS = {...}          # custom IC symbols (see below)
PARTS = [P(...), ...]
WIRES = [('R1.2', 'U3.5'), ('U3.7', 'R9.1', 'vh'), ...]   # optional direct wires
NOTES = [('text', col, row), ...]                          # text on the page
```
- Coordinates are grid cells (1 cell = 1.27 mm). Leave margins: keep everything within cols 12..(width-12), rows 25..(height-12) (title occupies the top-left).
- **Layout should mirror the patent drawing** (same relative placement and signal flow), upright even if the scan is rotated. Spread parts out: labels need room (≥ 12 cells between facing pins that are labelled, more for long net names).
- Every connected pin gets a 2-cell stub. Then: power nets (keys of POWER in oemsch.py: GND, +5V, +5VA, +15V, -15V, +12V, -12V, -5V, +10V, -10V, ...) get a power symbol; other nets get a net label; nets used on several pages automatically become global labels.
- `WIRES` draws an L-shaped wire between two pins' stub ends (`'hv'` = horizontal first, default; `'vh'` = vertical first) and suppresses redundant labels. Use wires for short, obvious local connections (feedback networks, series chains) to keep the page readable; use labels for longer runs. **A wire must not pass over any other pin/stub end** (it would short nets) — the netlist check catches this; reposition or fall back to labels.
- **Net names:** use the printed signal names exactly for named nets (e.g. `BWT_1P`, `NSP_CLK`, `CS_CTRL`, `CST_1`, `RAW_SHUTO_T-`, `OF_SET`). Pages share nets by identical name, so be exact and consistent with other figures (signal names printed on several figures must be spelled identically everywhere). Unnamed local nodes: descriptive names prefixed with the figure, e.g. `5B_U42_OUT`, `5D1_FB1`.
- Supply names exactly as printed: `+5V`, `+5VA`, `+15V`, `-15V`, `+12V`, `-12V`, `-5V`, `10V` (printed "10V" → use net `+10V` and add a NOTE), `-10V`. A printed supply not in POWER (e.g. `+5VREF`, `+27VRET`) is just a named net (label).
- **Refs:** use the printed ref. If a ref is printed more than once (patent drafting errors, e.g. R229 x3, C90 x2, R78 x4, C19 x2), keep the first and suffix later ones `B`, `C`… with `printed='R229'`. Multi-section parts (op-amp halves, DG413 switches, gate packages) get one P() per drawn section with suffix A/B/C… and `printed='U26'`. Refs printed with a V prefix (V10, V12…) stay as printed.
- **Values:** exactly as printed (`'10K'`, `'.1uF'`, `'2.2uF/25V'`, `'1N4148'`, `'49.9K(RM)'`). Illegible → `'?'` plus `note=`. Printed placeholders like `XXX`/`XX.K` kept verbatim.
- **Kinds:** R, C, CP (polarized: pin1 = +), D (1=K, 2=A), DZ, LED, L, POT (1,2=wiper,3), THERM, FUSE, NPN (pins 'B','C','E'), NMOS (pins 'G','D','S'), TP (pin '1'), `'CONN_<n>'` (pins '1'..'n', single row), `'OPAMP'` (with `pinmap={'-':'2','+':'3','out':'1','v+':'8','v-':'4'}` using the printed pin numbers; omit supply keys if supply pins aren't drawn for that section), or the name of a custom symbol in SYMBOLS.
- **Custom symbols** (ICs, analog switches, relays, gates, regulators, references, optocouplers): `SYMBOLS = {'F5B_MC2030': {'left': [('15','PROG'), ('14','READ'), None, ...], 'right': [...], 'top': [('16','VDD')], 'bottom': [('6','GND')], 'prefix': 'U'}}`. `None` = blank row. **Prefix every custom symbol name with your figure id** (`F5B_`, `F5G_`…) so agents never collide. Pin numbers and names exactly as printed; pins drawn but unconnected → `'NC'` in the part's pins only if drawn with an X / "N/C", otherwise just omit. For logic gates, relay coils/contacts, DG413 switch sections etc. make small box symbols with the printed pin numbers and functional names (e.g. relay contact: COM/NO/NC).
- Rotations: discrete R/C/L are vertical at rot=0 (pin1 top); rot=90 makes them horizontal (pin1 on the right? — check the rendered PDF). Op-amp at rot=0: inputs left (- top, + bottom), output right. You may set `mirror=True`.
- `probable='DS1267'` etc. for an identification guess (state it as a guess in your report; never replaces value). `datasheet=` only when certain.
- Tables printed on a figure (e.g. FIG 5A rack/tower option table) → reproduce as NOTES text (monospace-ish lines).
- Scale annotations like `[F(U) = 25/102+2.5]` → NOTES.

## Check loop (run after every substantial edit)
```
cd /Users/justinhyland/Documents/PlatformIO/Projects/260216-211115-esp32dev/docs/oem-controller/kicad
./tools/check.sh $W/build <your spec names>        # e.g. ./tools/check.sh $W/build fig5b fig5c
```
It must end with `netlist check: N pins, 0 problems`. ERC lines printed individually are real problems (fix them); counts of label_dangling / power_pin_not_driven / pin_not_driven are expected. Then render your pages and LOOK at them next to the source:
`pdftoppm -r 90 -png $W/build/schematic.pdf $W/view` (page 1 root, 2 patent sheet, 3+ your figures in the order of the args as listed in PATENTS) and Read the PNGs (crop to zoom). Fix overlapping text/labels, crossing wires, parts off-page. Also re-verify part-by-part against the source crops at the end: walk every component on the figure and tick it off.

## Report back (final message)
- figures done, part count, net count per figure
- every uncertainty (ref, what's unclear) and every printed anomaly (duplicate refs, missing values, impossible connections)
- probable part identifications with reasoning
- the signal names that leave your page (off-page connectors) — list them
