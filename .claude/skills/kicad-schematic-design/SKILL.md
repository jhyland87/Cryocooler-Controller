---
name: kicad-schematic-design
description: How to draw and lay out a readable schematic sheet in this project (wires versus labels, label and text placement, junctions, power and ground symbols, resistor symbols, page and block layout, symbol pin order, decoupling blocks, part and label descriptions). Use when adding or moving a part, wire, label or sheet, when designing a new circuit page, when asked to clean up or tidy a sheet or told it is hard to read, and when reviewing a schematic for readability. Applies to every board revision.
---

# Schematic design: drawing a readable sheet

A schematic is read by a person. A sheet that is electrically right but hard to follow
is not finished. These rules apply to every board revision and every sheet. They say
how a sheet should look; how to regenerate and run the checks is in
`hardware/kicad/README.md` ("Regenerating") and, where the branch has it, the
`kicad-schematic` skill.

The schematic is generated. Change `hardware/kicad/tools/gen_schematic.py` (symbols:
`tools/make_lib.py`) and re-run it. Never hand-edit a `.kicad_sch` file. Helper names
below are the ones to look for in the generator; `grep` for them, since not every
branch has every helper.

## Rules that have been broken before

These were each corrected more than once. No exceptions for tight spots.

1. **Supplies point up, grounds point down.** Never turn a power or ground symbol to
   dodge a neighbouring pin or wire. Instead put supply pins at the top and ground pins
   at the bottom of the symbol, step the wire sideways to the symbol, or tie several
   grounds to one bar (`gnd_bus`).
2. **Nothing overlaps.** No text over other text or over a symbol body. No wire or bus
   over a label's text. No symbol over another symbol, and no power or ground symbol
   touching or entering an IC body.
3. **Text sits by its own part.** A reference, value or label must be closer to the
   part or wire it belongs to than to anything else. If a reader could attach it to
   the neighbour, move it.
4. **No 4-way junctions.** At most three connections meet at a point (pins count).
   Offset one branch so a cross becomes two T's.
5. **Resistors use the US zig-zag symbol** (`Device:R_US`). Capacitors keep the
   standard symbols.
6. **Every power symbol shows its net name.**
7. **Signals between sheets use hierarchical labels and sheet pins, not global
   labels.** Global labels only for nets in `ALLOWED_GLOBALS`
   (`tools/check_sheet_structure.py`).
8. **No label pair where a wire fits.** Two labels of one net closer than 85 mm on a
   sheet are a wire.
9. **Don't work around a rule.** When the drawing helpers make the right thing hard,
   add or fix a helper. A shortcut that passes the checks is still a failure.

## Wires and labels

- Inside a block, connect parts with wires. A reader should see what an IC's support
  parts are tied to without hunting for a matching label.
- A label pair whose two ends sit close together becomes a wire. Use a label pair only
  when the wire would run more than 85 mm or cross a block.
- Pick the narrowest label scope that works:

  | Connection | Use |
  |------------|-----|
  | Two points on one sheet | Wire; a local label only to name the net or for a long run |
  | Sheet to its parent | Hierarchical label on the sheet, sheet pin on its block, wired on the parent |
  | Project-wide bus (listed in `ALLOWED_GLOBALS`) | One global label on a bus (`{SPI}`, `{I2C}`) |

- A signal that reaches several sheets still goes through sheet pins. The root sheet
  wires them together, which is what makes it show how the blocks connect.
- Never put a global label on a sheet that is placed more than once. It shorts every
  instance together into one net.
- A wire may still carry one label to give the net a useful name.
- Take the short route. No long detours, and straighten any wire that has no reason to jog.
- A label sits on the end of its own wire: never floating, never on top of another
  wire, and next to the pin or part it names.
- Hierarchical labels, sheet pins and global labels show direction (input, output,
  bidirectional) per net and sheet (`LABEL_DIRECTION` in `tools/kicadgen.py`). A new
  net that crosses sheets needs an entry.
- Signals shared by many parts on a sheet (a shared SPI bus, for example) are drawn as
  a KiCad bus where the generator has a bus helper. Use an unnamed group so the member
  nets keep their names.
- Name nets for what they do, in capitals, with no periods (`+3V3`, not `3.3V`). Use
  one name per rail everywhere.

## Page layout

- **One function per sheet** (power input, a rail pair, one sensor front end, one
  actuator driver). When a sheet gains a second function, or passes 30 parts (power
  symbols not counted), split it. Don't shrink symbols or the spacing to fit more.
  The root sheet shows how the sheets connect, through sheet pins.
- **A circuit used more than once is one sheet file placed several times**, not copied
  files. Anything that differs per instance (the channel's GPIO, its connector) comes
  in through sheet pins.
- Signal flows left to right: inputs and connectors feeding the sheet on the left,
  outputs on the right. Feedback may run right to left.
- Higher voltage toward the top. Pull-ups sit above the line they pull, pull-downs below.
- Group each sub-circuit, leave white space between groups, and give each a heading.
- **Repeated circuits are drawn the same way.** Channels, rails or indicator blocks that
  share a circuit get the same part positions, wire routes and spacing, built from one
  helper, so a difference on the page means a difference in the circuit.
- **Crowded? Spread the parts out first.** Only then use the small resistor and
  capacitor symbols (`Device:R_Small_US`, `Device:C_Small`) and shared ground bars.
- Wires run horizontally or vertically only. Line up pins so wires stay straight.
- Bring a short stub out of every pin before a bend, junction or label. Never run a
  wire through a pin, through a part body, or along a row of pins.
- Reduce crossings by where parts are placed, not by routing around them.
- Keep switching loops compact and drawn as loops.
- Protection parts (TVS, ESD, clamps) sit beside the connector or pin they protect.
  Test points sit on their net.
- Parts and all their text stay horizontal or vertical; text reads without turning the page.

## Symbols

- Group pins by function, not package order: supplies on the top edge, grounds on the
  bottom, inputs and control on the left, outputs on the right, bus pins together
  (`from_stock` in `tools/make_lib.py` re-lays-out a stock symbol).
- To face a part the other way, mirror it or make a custom symbol. Don't turn it 180
  degrees.
- Dual and quad parts (op-amps, gates) are multi-unit symbols drawn in their standard
  shapes, each unit placed where it is used.
- Every deliberately unused pin gets a no-connect flag.
- Every part shows its reference and its value.

## Decoupling capacitors

Each IC's bypass caps go in a titled block at the side of the same sheet: supply rail
on top, caps hanging from it, ground bus below, heading "<PART> DECOUPLING CAPACITORS"
(`place_blocks`, `decoupling_block`). The IC's supply pin keeps only its power symbol.
Capacitors that are part of the circuit stay in the circuit: regulator input and
output, compensation, reference and bulk caps.

## Descriptions and notes

- **Every part gets a description of its job in this circuit**, not its type:
  "Pull-up for the INA239 ALERT output", "LC filter inductor on the +15 V rail",
  never "Resistor, small US symbol". Each IC's description says what role it plays.
  Descriptions need not be visible.
- **Every label gets a description too:** source, destination, GPIO and active level.
- Writing the description is part of adding the part or label, not a later pass.
- Every symbol carries a link to the part and to its datasheet (`tools/part_links.py`).
- Add a note where the drawing can't say it: how a value was calculated, strapping and
  address settings, limits, sequencing.
- An off-board item (a display, a module) gets a simple outline drawing with its name,
  and its connectors placed roughly where they are on the real thing.

## Colours

Where the generator defines net-class colours, colour means power: supply rails are
coloured by class and signals keep the default colour. A legend sits on the root sheet.
Never rely on colour alone to tell two nets apart.

## Check before calling it done

`tools/check_sheet_structure.py` enforces the label-scope, label-pair, sheet-size and
copied-sheet rules. The sheets drawn before these rules have a baseline count of
violations (`tools/sheet_structure_baseline.json`). A change may not raise any count.
When a change lowers one, run it with `--update-baseline`.

1. Before a layout-only change, export a baseline netlist. Afterwards the netlist must
   be identical (`tools/compare_netlists.py`). Tidying must not change a connection.
2. Regenerate and read every check line the generator prints (text overlap, 4-way
   junctions, unlabeled power symbols, duplicate references, and whatever else this
   branch checks). Any failure is a failed build, not a warning.
3. Run ERC on the root sheet and any symbol checker the branch has.
4. Run `python3 tools/check_sheet_structure.py`. It must exit 0 with no count above
   its baseline.
5. Have the `schematic-reviewer` subagent review every changed sheet. Don't review
   your own drawing: the reviewer starts without your context and checks the rules
   above that no script checks (grouping, signal flow, one function per sheet,
   labels by their part). Fix everything it reports and run it again until it passes.
6. Say which checks ran, what the reviewer found and what was fixed.

## Where this project differs from common practice

These are deliberate. Don't "fix" them.

| Topic | Common advice | Here |
|-------|---------------|------|
| Decoupling caps | Beside the IC they serve | In a titled block at the side of the sheet |
| 4-way junctions | Often accepted with a dot | Never |
| Colour | Often monochrome only | Net-class colours for power |
| Pin order | Sometimes package order | By function |
