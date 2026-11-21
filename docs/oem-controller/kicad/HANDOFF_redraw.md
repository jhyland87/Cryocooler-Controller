# Handoff: redrawing the OEM controller schematic

Branch `oem-schematic-redraw` (worktree `.claude/worktrees/oem-schematic-redraw`), cut from `rev6-schematic`
at e2792a6. Nothing committed. Rules: `.claude/rules/schematic-drawing.md`, the `kicad-schematic-design` skill
and the "Schematic profile" in `README.md`.

## Status

| Figure | State |
|--------|-------|
| 5F | **Pilot redrawn**, reviewer fixes applied; waiting for the user's review |
| 5C | **Redrawn** (session 2), seven child sheets; user: "pretty good" (2026-11-21); U28 pin order and heading changed since |
| 5A | **Redrawn** (session 2), three child sheets; reviewed by the user 2026-11-21 ("looks good") |
| 5B | **Redrawn** (session 3), five child sheets; waiting for the user's review |
| 5D, 5E, 5G, 5H, 6A, 6B, 6C | Not started (old drawing: labels on pins, global labels). Next: 5D or 5E |

Stop after the pilot until the user has looked at it. Then one figure at a time, at most three per session.

## Baseline (step 0)

- Baseline netlist: export it from commit e2792a6 when needed (it is not kept in the repo):
  `git worktree add /tmp/oem-base e2792a6` then
  `kicad-cli sch export netlist --format kicadsexpr -o base.net /tmp/oem-base/docs/oem-controller/kicad/oem-controller.kicad_sch`.
  831 parts, 598 nets.
- Before the redraw: `check.sh` ERC counts `isolated_pin_label` 104, `power_pin_not_driven` 10,
  `pin_not_connected` 31 (the 31 are printed one per line; they are drawn unconnected pins on 5A, 5F J12-9, 5G,
  5H, all pre-existing); netlist check 2362 pins, 0 problems; text overlap 0.
- `check_symbols.py`: 0 overlaps, 0 turned, 15 power symbols touching a wire (3 on 5A, 12 on 5G), 0 crossed.
- `check_sheet_structure.py`: global_label 303, close_label_pair 732, too_many_parts 10, wire_near_body 2
  (5B R199, 5E TPX2), others 0.

## Gate after each figure

1. `tools/check.sh <scratch>`: netlist check 0 problems, text overlap 0, ERC only the expected classes.
2. `python3 -I tools/gen_oem_schematic.py` (writes the project).
3. `kicad-cli sch export netlist ...` then `hardware/kicad/tools/compare_netlists.py --strict --renamed base.net new.net`:
   0 differences; renames only by sheet path (`--list` to see them).
4. `hardware/kicad/tools/check_symbols.py oem-controller.kicad_sch` and
   `hardware/kicad/tools/check_sheet_structure.py --project docs/oem-controller/kicad/oem-controller.kicad_pro`:
   no count above baseline; `--update-baseline` when one drops.
5. `schematic-reviewer` subagent with the `.kicad_pro` and the changed sheets, until it passes.

Run the repo tools without `-I` (they import their siblings); the project's own tools with `-I`.

## FIG 5F (pilot)

Child sheets (block name in brackets; it is part of every net's path):

| Sheet | Parts | Ports |
|-------|-------|-------|
| `ref10` [10V REF] 10 V reference U47/U50 | 6 | REF_1 out |
| `ref5va` [+5VA] U55 + QX1 buffer, R168 | 14 | REF_1 in (+SUREF is a net label on the sheet) |
| `ref10v` [10V OUT] U45 output stage, +10V caps | 13 | REF_1 in |
| `dcdc` [INPUT] power input: J12, fuse, C161, UR3 | 4 | FAULT_O, FAULT_NO, 5F_VIN_P, 5F_VIN_RTN |
| `monitor` [MONITOR] U45 (second) -> PWR_MON | 11 | 5F_VIN_P, 5F_VIN_RTN in, PWR_MON out |
| `regs` [REGULATORS] UX1-UX3 | 9 | none (power nets only) |
| `digital` [+5V] UX4, L0, L7, A/D ground split, TPX1-4 | 15 | none |

Counts after 5F: global_label 297, close_label_pair 681, too_many_parts 9, wire_near_body 2; ERC as the
baseline; compare: 0 differences, 12 nets renamed by sheet path only.

### Decisions (pilot; the user may overrule)

- **Interim bridge:** the four figure-level ports (REF_1, FAULT_O, FAULT_NO, PWR_MON) reach the other figures
  through a global label on each FIG 5F sheet pin on the patent sheet (`bridge_to_globals()` in the generator).
  These go when the figures on the other end are redrawn; the parent then wires or labels the sheet pins.
- **Patent sheet** is now A3 with blocks on a grid (was A4); a block with pins is taller.
- **+SUREF** is printed as an off-page flag but nothing uses it: it ends in a net label on the `ref5va` sheet
  (`long_nets`), not a port.
- **Net names kept:** every named local net still gets one net label (names may change only by sheet path).
  The two nets that were unnamed before (QX1 base, U55 +input) stay unnamed (`names={...: None}`).
- **Symbols re-laid by function** (pin numbers unchanged): UR3 inputs left, +15V/-15V right, common bottom;
  the regulators are one symbol `F5F_REG` with IN left, OUT right, COM bottom (was OUT left, IN right, and COM on
  top for the negative ones).
- **Input pins on the left:** reference VDD and regulator IN stay on the left edge, not the top. Question for the
  user: does "supply pins on the top edge" apply to a regulator's or reference's input?
- **J12** is mirrored so its pins face right (input on the left). FAULT_NO (pins 2 and 10) crosses the two
  power wires once each; the pin order makes a crossing unavoidable without a long detour.
- **Supply symbol on a downward stub** (op-amp V- to -15V): the stock -15V symbol points up, so the generator
  puts it at the end of a short jog to the right (`_power_symbol()`).
- **Decoupling:** each op-amp's +15V/-15V caps are in a titled block at the bottom left of its sheet.
- Descriptions: the patent text says nothing about FIG 5F's circuits, so descriptions cite only what the figure
  prints ("Patent: FIG 5F-2 ...") and otherwise say "Inferred from the circuit".

### Generator changes

- `oemsch.py`: `P(desc=)`; `_place_parts()` shared by both builders; `child()`, `port()`, `tap()`,
  `build_node()`, `sheet_block_pins()`, `block_geometry()`, `_route()` (corner lists), `_power_symbol()`,
  `LABEL_SHAPES` (hierarchical label direction per sheet).
- `gen_oem_schematic.py`: `REDRAWN` specs go through `build_redrawn()` (child sheets, figure page,
  description checks) and `bridge_to_globals()`; `spec.PARTS` of a redrawn spec is all its parts, for the tools.
- Old figures are built exactly as before by `build_sheet()`. When the last figure is redrawn, `build_sheet()`,
  `_wired_groups()`, `_clear_neighbours()`, `_centre_fields()`, `bridge_to_globals()` and the global-label code
  in `oemsch.py` and `gen_oem_schematic.py` become dead: list them for the user and delete on their OK.

### Review renders

`redraw_review/*.png` (not for committing): `US6098409_parent.png`, `fig5f.png` and one per child sheet.

### Skipped / open

- See "Questions for the user" at the end.

## FIG 5C (session 2)

Child sheets (block name in brackets):

| Sheet | Function | Ports |
|-------|----------|-------|
| `sum` [SUM] | U34 set-point summing amp, OF_SET input | OF_SET in, 5C_U34_OUT out |
| `cmt` [CMT] | U26A ceiling from CMTO_T | 5C_U26B_NI out |
| `hog` [HOG] | U53A/U53B overstroke sensor front end (HOG_T, RT1 compensation) | 5C_U53B_OUT out |
| `trip` [TRIP] | U48 LT1011A trip comparator | 5C_U53B_OUT in, 5C_U48_OUT out |
| `clamp` [CLAMP] | Set-point ceiling clamp U26B, U33 -> NOT_TOTAL | 5C_U34_OUT, 5C_U26B_NI in, NOT_TOTAL out |
| `counter` [COUNT] | U28 HC123 one-shots, Q1-Q5, C71 back-off store | 5C_U48_OUT in, 5C_COUNT_CAP out |
| `buffer` [BKOFF] | Back-off count stage: U27A -> BACK_OFF_COUNT, U27B ceiling drive | 5C_COUNT_CAP in, BACK_OFF_COUNT, 5C_U26B_NI out |

Counts after 5C: ERC as the baseline; netlist 2362 pins, 0 problems; text overlap 0; compare 0 differences,
67 nets renamed by sheet path only; check_symbols 0/0/15/0; check_sheet_structure global_label 279,
close_label_pair 557, too_many_parts 8, wire_near_body 2 (baseline updated).

### Decisions (5C)

- No `GLOBALS` in the spec: only OF_SET, NOT_TOTAL and BACK_OFF_COUNT leave the figure (figure-page ports,
  bridged on the patent sheet like 5F's). `global_nets()` ignores a redrawn spec's own nets.
- 5C_U26B_NI (CMT and BKOFF both drive the ceiling node) is wired CMT -> CLAMP and labelled at BKOFF
  (`PAGE_LONG_NETS`).
- Symbols re-laid by function (pin numbers unchanged): `F5C_LT1011A` inputs left, OUT/BAL right, V+ top,
  GND/V- bottom; `F5C_HC123_S2` left pins ordered so U28B's lines nest without crossing.
- Descriptions cite analysis/OVERSTROKE.md 2.3 as "Inferred from the circuit" or the printed figure as "Patent:".
- Short block names (COUNT, BKOFF) keep the title-block sheet path inside the frame.

### Generator changes (session 2)

- `P(text=(dcol, drow))`: pinned reference/value position.
- `check_junctions()` in `build_node()`: fails on four or more connections at a point and adds the junction dot
  where exactly three meet, counting power-symbol pins (kicadgen leaves those out).
- Redrawn sheets set `wire_margin = 0.6` (text kept clear of wires); `textlayout.py` reads it with `getattr`,
  so other projects are unchanged. Plain GND names stay hidden (user, 2026-11-21); other grounds are named.
- `_route()` drops zero-length segments (a stray junction otherwise).

## FIG 5A (session 2)

| Sheet | Function | Ports |
|-------|----------|-------|
| `conn` [CONN] | J5A1 (34-pin) and J5A2 (16-pin) through 1K resistors, J5A3 (26-pin) | 20 passive: BWT_*, AMB_TEMP, DEWAR_TEMP, CS_CTRL, CST_1/2, CFT_T1/T2, REF_1 |
| `reset` [RESET] | U56 LT1011A 80_RESET comparator | none (80_RESET is a printed off-page flag, a net label) |
| `spares` [SPARES] | Unused U44/U29/U19 gates, U11/U33/U14/U46/U54 op-amps, U43 switches, U17 mux | none |

Counts after 5A: ERC power_pin_not_driven 11 (+1: DGND is now a power net, like the other rails); netlist
2362 pins, 0 problems; text overlap 0; compare 0 differences, 117 renamed by sheet path only; check_symbols
0/0/12/0; check_sheet_structure global_label 259, close_label_pair 547, too_many_parts 7, wire_near_body 2.

### Decisions (5A)

- **DGND is a power symbol** (`power:GNDD`, value DGND) on every figure, not a global label; the net name is
  unchanged (user, 2026-11-21).
- A net that leaves the CONN sheet and also runs from the J5A1/J5A2 resistors to J5A3 (more than 85 mm) has a
  hierarchical label at both ends, not a local label: a local label of a global net's name raises ERC
  `same_local_global_label` while the interim bridge exists.
- Pin-tie grounds hang from the lowest tied pin (connector even pins, tied gate inputs), so no wire runs into a
  ground symbol.
- Spare op-amps are mirrored (+ on top) so the fed-back + input takes the loop over the top and the grounded
  input hangs its GND below.
- CS_CNTRL is used as CS_CTRL directly (the alias); the CONN sheet note says so.
- The patent sheet stacks blocks down each column by their height (5A's block has 20 pins).
- CONN reads left to right: J5A1/J5A2 first (odd pins on the right via `_two_row(odd='right')`), the 1K
  resistors, then the ports. J5A3 stays at x 250: closer puts its CST_2 label within 85 mm of J5A2's.
- U56 (LT1011A): V- on the top edge beside pin 4, so -15V points up with no jog; GND (?b, DGND) on the bottom.
- **U17 (74HC153) uses the datasheet pin names** (A, B, ~{2G}, 2C0-2C3, 2Y) on the printed numbers (user,
  2026-11-21); README profile exception 3 lists it. ~{2G} is tied into the grounded data chain. The net
  `5A_U17_V_open` keeps its name.
- Only the 5A port directions another figure states are set (CS_CTRL, REF_1 input); the rest are passive.

### Generator changes (5A)

- `DGND` in `POWER` (symbol `GNDD`) and `DOWN_SYMBOLS`.
- Part fields: **Description** = what the part is (`PART_INFO` by printed value, "Assumed part: ..." from
  `probable=`, or kind and value); **Function** = its job here (`desc=`). User request, 2026-11-21.
- A long net's label follows `names=`; a long net that also has a port gets hierarchical labels at its far ends.
- `gate_symbol()`: NAND (true semicircle), OR with bubbled inputs, inverter; an output pin with a long number
  (11#2) is 5.08 mm so the number clears the bubble.
- `check_junctions()` adds junction dots where exactly three connections meet (power-symbol pins counted).
- FIG 5F: `probable=` added for UX1-UX4 (78xx/79xx-type) and UR3.

## FIG 5B (session 3)

| Sheet | Function | Ports |
|-------|----------|-------|
| `switch` [SWITCH] | U43 DG413 switches CST_2 (R201) / CST_1 (R200) on CST_DEL, C94 | CST_2, CST_DEL, CST_1 in; 5B_SW_OUT out |
| `sum` [SUM] | U42 LT1012 summing amp (+10V R211, OF_SET R213, switch R212; R296 feedback) | OF_SET, 5B_SW_OUT in; 5B_U42_OUT out |
| `integ` [INTEG] | U35 LMC6001 integrator (R205/R203/C109 in, C108+R199 and C98 feedback) | 5B_U42_OUT in; CS_CTRL out |
| `pot` [POT] | U36 MC2030 serial pot; U54 follower -> OF_SET; OF_OFFSET, NSP_SER9 net labels | NSP_PROG/READ/SER0/CLK in; OF_SET out |
| `latch` [LATCH] | U29 MC2001 serial latch -> CST_DEL, RAW_SHUTO_T-, NSP_SERI | NSP_CLK/SER0/READ/PROG in; RAW_SHUTO_T-, CST_DEL, NSP_SERI out |

Counts after 5B: ERC as the baseline (isolated_pin_label 104, power_pin_not_driven 11, pin_not_connected 30);
netlist 2362 pins, 0 problems; text overlap 0; compare 0 differences except J12/UR3 values, 123 renamed;
check_symbols 0/0/12/0; check_sheet_structure global_label 253, close_label_pair 544, too_many_parts 6,
wire_near_body 1 (baseline updated; R199's is gone).

### Decisions (5B)

- **OF_SET joined by a wire on the patent sheet**, 5B's first right pin to 5C's first left pin (same row): its
  only figures (5B, 5C) are both redrawn, so its global bridge is gone. `redrawn_only()` and `join_figures()` in
  the generator do this for any net whose figures are all redrawn: a wire for two facing pins on one row,
  otherwise a net label at each pin. CST_1, CST_2, CS_CTRL (5A and 5B redrawn, but 5H/6C not) stay bridged.
- Figure page (A4): LATCH takes the four NSP lines in the reverse order of POT, so the lines nest with no
  crossing; each figure-level label sits on its own line in the gap between the blocks. SUM sits right of POT
  (OF_SET a straight ~53 mm wire), SWITCH in the gap right of the nest (CST_DEL up from LATCH).
- Nets unnamed before stay unnamed (`names=None`): U43 S nodes, C94 node, U42 +, U35 +/-, R205/R203 node,
  C108/R199 node, U54 +/-. **5B_U42_OUT** (was `Net-(R205-Pad1)`) now has a name: it crosses from SUM to INTEG
  through a hierarchical label (the only unnamed-to-named change).
- Symbols re-laid by function (numbers and names unchanged): both U43 switches S above IN, D right, the same
  box size (switch 2 has empty top/bottom slots); switch 1's "V-" supplies top (+15V one left), GND bottom.
  CST_DEL reaches both IN pins from a trunk left of the CST_2/CST_1 inputs (no crossing); U36 pot ends spaced so
  +5VA and GND symbols stay apart; U29 inputs reordered for the nest, the tied-off bubble input (pin 9) on the
  bottom edge beside GND, both on one DGND symbol.
- R199 now sits on its own row in the U35 feedback (C108 + R199 above, C98 above that), clear of every wire.
- U42/U35/U54 V- use the jog to the negative rail (user answer 1); ground symbols hang from their own stubs.

### Generator changes (5B)

- `gen_oem_schematic.py`: `redrawn_only()`, `join_figures()`; `bridge_to_globals()` collects those nets.
- `oemsch.box_symbol()`: a top/bottom list of only gaps now sizes the box like one with pins (no other symbol
  has such a list); `'vlength'` in a SYMBOLS entry sets the top/bottom pin length (U43A, for "V-#2").
- Reviewer round 1 (fixed): OF_SET route over 85 mm, output and input labels facing each other, switch channels
  drawn differently, text crowding on SUM/INTEG/POT/SWITCH. Off-page-flag net labels (OF_OFFSET, NSP_SER9)
  kept as on 5A/5C/5F; the README profile's "Net names" row now says so. Round 2: U35 reference moved.
  Round 3: every FIG 5B sheet and the patent sheet PASS.

## User review notes for figures not yet redrawn (2026-11-21)

Seen in the old 5A/5B drawing; the redraw of those figures must fix each one (5A and 5B done):

- Ground and negative-rail symbols sit on top of their own pin stub (5A U44B/U29 gates, U17 C0; 5B U42/U35 -15V/-5V).
- A -15V symbol doubles back on its own wire (5A LT1011A, beside the DGND label).
- J5A3 (5A) has a global label on almost every pin: use hierarchical labels and sheet pins.
- 5B R199: the wire runs along the resistor body (the `wire_near_body` count).
- **DGND becomes a power symbol**, not a global label (it behaves the same and keeps the net name).
- Plain GND symbols show no name; other grounds (DGND) are named.

## Questions for the user (answers 2026-11-21)

1. Op-amp V- to a negative supply on a short jog right of the stub: **accepted**.
2. Regulator/reference input drawn on the left with the supply symbol up on its wire: **accepted**.
3. Global-label bridge on the patent sheet: **temporary exception**, README profile exception 6. Remove each
   global as its partner figure is redrawn.
4. **Done:** J12 and UR3 values are "?" (compare shows these two value changes only).
5. Vertical net labels on 5F: **accepted**.
6. 5C U27B open-loop and U48/R254 latch: **kept as read from the patent**. There is no hardware to check
   against; the job is transcribing and tidying the patent, not verifying the circuit.
7. **Done:** J12 pin 9 has a no-connect flag (ERC pin_not_connected 30).
8. **Done:** pins may be moved and reordered by function, as on the main board. U28A/U28B now share one left
   order; ~{CLR} faces the shared SHUTO_T line (bottom of U28A, top of U28B), no crossings.
