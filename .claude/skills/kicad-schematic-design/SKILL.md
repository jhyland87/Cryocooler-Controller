---
name: kicad-schematic-design
description: How to draw and organize a readable KiCad schematic in any project in this repo (hierarchical sheets, wires versus net, hierarchical and global labels, label and text placement, junctions, power and ground symbols, page and block layout, symbol pin order, decoupling blocks, part and label descriptions). Use when adding or moving a part, wire, label or sheet, designing a new page, redrawing or tidying a sheet or a whole schematic, applying the drawing rules to another schematic, or reviewing one for readability. Covers hardware/kicad, docs/oem-controller/kicad and any new schematic.
---

# Schematic design: drawing a readable schematic

A schematic is read by a person. A sheet that is electrically right but hard to follow
is not finished. These rules apply to every schematic project in this repo, every
board revision and every sheet. The short version is `.claude/rules/schematic-drawing.md`.

## Start with the project's schematic profile

Each project's `README.md` has a "Schematic profile" section: how the schematic is
made and regenerated, where descriptions live, the check config
(`schematic_checks.json`), the checks and expected results, the connectivity gate,
whether a board depends on net names, the project's helpers, and its deliberate
exceptions. Read it before changing anything.

- Generated schematics are changed in the generator and re-generated. Never hand-edit
  a generated `.kicad_sch`.
- Helper names in the profile (bus helpers, ground bars, decoupling blocks) are how
  that project carries out the rules below. When a project lacks the helper a rule
  needs, add it to the generator rather than bend the rule.
- An exception counts only if the profile lists it. A project without a profile gets
  one first; ask the user about anything that would be an exception.

## Rules that have been broken before

These were each corrected more than once. No exceptions for tight spots.

1. **Supplies point up, grounds point down.** Never turn a power or ground symbol to
   dodge a neighbouring pin or wire. Put supply pins at the top and ground pins at the
   bottom of the symbol, step the wire sideways, or tie several grounds to one bar.
2. **Nothing overlaps.** No text over other text or a symbol body. No wire or bus
   over a label's text. No symbol over another, and no power or ground symbol
   touching or entering an IC body.
3. **Text sits by its own part.** A reference, value or label must be closer to the
   part or wire it belongs to than to anything else.
4. **No 4-way junctions.** At most three connections meet at a point (pins count).
   Offset one branch so a cross becomes two T's.
5. **Resistors use the US zig-zag symbol** (`Device:R_US`). Capacitors keep the
   standard symbols.
6. **Every power symbol shows its net name**, except plain `GND`, whose symbol says it.
   Other grounds are named (`DGND`, `ISOGND`), and each is a power symbol, not a global label.
7. **Signals between sheets use hierarchical labels and sheet pins, not global
   labels.** Global labels only for the communication buses in the project's
   `allowed_globals`.
8. **No label pair where a wire fits.** Two labels of one net closer than 85 mm on a
   sheet are a wire.
9. **A bus is for a communication bus** (SPI, I2C). Chip selects, interrupts and
   control lines are single labelled nets, never bundled into a bus or a trunk.
10. **Pull resistors sit on the line they serve**, pull-ups above it and pull-downs
    below. No "bias" block joined to its pins by labels.
11. **Don't work around a rule.** When the drawing helpers make the right thing hard,
    add or fix a helper. A shortcut that passes the checks is still a failure.

## Hierarchy

- **One function per sheet** (power input, a rail pair, one sensor front end, one
  actuator driver). Split a sheet when it gains a second function or passes the
  profile's part limit (30 by default, power symbols not counted). Don't shrink
  symbols or spacing to fit more.
- **Parents and children.** A sheet holding several related functions can be a
  parent with child sheets, at any depth. Keep it to what a reader can follow,
  usually two or three levels. The root, and every parent, shows how its blocks
  connect.
- **A circuit used more than once is one sheet file placed several times**, not
  copied files. What differs per instance (the channel's GPIO, its connector) comes
  in through sheet pins. Never put a global label on such a sheet: it shorts every
  instance into one net.
- **A signal that crosses several levels goes through each one:** a hierarchical
  label on the child, a sheet pin on its block in the parent, and so on up to where
  it is used. Net labels never cross a sheet boundary, and depth is not a reason for
  a global label.
- **Sheet paths are part of net names.** A net label names its net `/NAME` on the
  root and `/Sheet/NAME` below; a global label gives plain `NAME`. Changing a label's
  type, or moving a sheet under another parent, renames nets. Where a routed board
  depends on the names, follow the profile's rename procedure in the same step.

## Wires and labels

- Inside a block, connect parts with wires. A reader should see what an IC's support
  parts are tied to without hunting for a matching label.
- Pick the narrowest connection that works:

  | Connection | Use |
  |------------|-----|
  | Two points on one sheet, closer than 85 mm | Wire; a net label only to name the net |
  | Two points on one sheet, further apart | A net label on a short wire at each end, not a wire across the sheet |
  | Sheet to its parent | Hierarchical label on the sheet, sheet pin on its block; on the parent a wire to a close pin, a net label at each pin otherwise |
  | Project-wide communication bus (in `allowed_globals`) | One global label on a bus |

- A wire may carry one label to give the net a useful name.
- Take the short route. No long detours; straighten any wire that jogs for no reason.
- A label sits on the end of its own wire: never floating, never on another wire,
  and next to the pin or part it names.
- Hierarchical labels, sheet pins and global labels show direction (input, output,
  bidirectional) per net and sheet.
- A communication bus shared by many parts is drawn as a KiCad bus. Use an unnamed
  group (`{SPI}`) so the member nets keep their own names.
- Name nets for what they do, in capitals, with no periods (`+3V3`, not `3.3V`). One
  name per rail everywhere. Where the profile says names come from a source document
  (a patent, a datasheet), keep them exactly as printed.
- An active-low net or pin gets an overbar, `~{NAME}`, never a `_N` or `#` suffix,
  unless the profile says names are kept as printed.

## Page layout

- Signal flows left to right: inputs and connectors on the left, outputs on the
  right. Feedback may run right to left.
- Higher voltage toward the top. Pull-ups above the line they pull, pull-downs below,
  each on its own line rather than in a block of its own.
- Group each sub-circuit, leave white space between groups, and give each a heading.
- **Repeated circuits are drawn the same way:** the same part positions, wire routes
  and spacing, built from one helper, so a difference on the page means a difference
  in the circuit.
- **Crowded? Spread the parts out first.** Only then use the small resistor and
  capacitor symbols (`Device:R_Small_US`, `Device:C_Small`) and shared ground bars.
- Wires run horizontally or vertically only. Line up pins so wires stay straight.
- Bring a short stub out of every pin before a bend, junction or label. Never run a
  wire through a pin, through a part body, or along a row of pins.
- **Nothing touches a part it isn't connected to.** A wire, bus or bus entry reaches
  a part only at the end of one of its pins. It never runs along a body outline, ends
  on a body corner, or passes within 2.54 mm of a body it does not connect to. Move
  the wire or the part. `check_sheet_structure.py` counts these as `wire_near_body`.
- Reduce crossings by where parts are placed, not by routing around them.
- Keep switching loops compact and drawn as loops.
- Protection parts (TVS, ESD, clamps) sit beside the connector or pin they protect.
  Test points sit on their net.
- Parts and their text stay horizontal or vertical; text reads without turning the page.

## Symbols

- **Arrange a symbol's pins for the circuit it's drawn in, not the package.** In
  order of preference:
  1. **Keep pins grouped by function**: inputs and control together, outputs
     together, a bus's pins together and in order (D0 to D7, Q0 to Q9). Default
     sides: inputs and control on the left, outputs on the right.
  2. **Move a whole group to another side** when that makes the sheet read better.
  3. **Move a single pin out of its group** only when it removes a crossing, a long
     detour or a label. Most pins should still sit in their group.
  Supply pins always on the top edge, ground pins on the bottom edge. Pin numbers
  never change; only the drawing moves. A symbol is shared by every instance, so lay
  it out to suit all of them.
- To face a part the other way, mirror it or make a custom symbol. Don't turn it 180
  degrees.
- Dual and quad parts (op-amps, gates) are multi-unit symbols drawn in their standard
  shapes, each unit placed where it is used.
- Every deliberately unused pin gets a no-connect flag.
- Every part shows its reference and its value.

## Decoupling capacitors

Each IC's bypass caps go in a titled block at the side of the same sheet: supply rail
on top, caps hanging from it, ground bus below, heading "<PART> DECOUPLING
CAPACITORS". The IC's supply pin keeps only its power symbol. Capacitors that are part
of the circuit stay in the circuit: regulator input and output, compensation,
reference and bulk caps.

## Descriptions and notes

- **Every part gets a description of its job in this circuit**, not its type:
  "Pull-up for the INA239 ALERT output", "LC filter inductor on the +15 V rail",
  never "Resistor". Name the IC or net it serves and the network it belongs to
  (divider, LC filter, compensation). An IC's description states its role.
- **Every label gets a description too:** what the net carries, its source and
  destination, and its active level (and GPIO, where there is one).
- **Never state a guess as fact.** Where the role comes from the design (datasheet,
  design notes, the source document), say so plainly. Where it is worked out from the
  circuit, say it is inferred ("Inferred from the circuit: ..."). Where it isn't
  known, write "Role unknown". The profile says where descriptions are stored.
- Writing the description is part of adding the part or label, not a later pass.
- Add a note where the drawing can't say it: how a value was calculated, strapping and
  address settings, limits, sequencing.
- An off-board item (a display, a module) gets a simple outline drawing with its name,
  and its connectors placed roughly where they are on the real thing.

## Colours

Where the generator defines net-class colours, colour means power: supply rails are
coloured by class and signals keep the default colour. A legend sits on the root sheet.
Never rely on colour alone to tell two nets apart.

## Redrawing an existing schematic

1. Before changing the drawing, export a baseline netlist and record the current
   check counts.
2. Do a pilot on one small sheet and have the user look at the render before going
   further.
3. Then one sheet at a time. After each, the connectivity gate from the profile must
   pass: same parts, the same pins on the same nets, values unchanged. Net names may
   change only as the profile allows.
4. Keep a handoff file next to the project listing sheets done and left, decisions,
   and check counts, so a fresh session can continue.

## Check before calling it done

`check_sheet_structure.py` (in `hardware/kicad/tools/`, run with `--project` for the
project's `.kicad_pro`) enforces the label-scope, label-pair, sheet-size,
copied-sheet and wire-near-body rules. A project drawn before these rules has a
baseline count of violations. A change may not raise any count; when one drops, run
it with `--update-baseline`.

1. Run the connectivity gate from the profile. Tidying must not change a connection.
2. Regenerate and read every check line the generator prints. Any failure is a failed
   build, not a warning.
3. Run ERC on the root sheet, `check_symbols.py` on the root, and the profile's other
   checks.
4. Run `check_sheet_structure.py --project <path>.kicad_pro`. It must exit 0.
5. Have the `schematic-reviewer` subagent review every changed sheet (give it the
   project's `.kicad_pro` and the sheet files). Don't review your own drawing. Fix
   everything it reports and run it again until it passes.
6. Say which checks ran, what the reviewer found and what was fixed.

## House style that differs from common practice

These are deliberate in every project here. Don't "fix" them.

| Topic | Common advice | Here |
|-------|---------------|------|
| Decoupling caps | Beside the IC they serve | In a titled block at the side of the sheet |
| 4-way junctions | Often accepted with a dot | Never |
| Colour | Often monochrome only | Net-class colours for power |
| Pin order | Sometimes package order | By function |
