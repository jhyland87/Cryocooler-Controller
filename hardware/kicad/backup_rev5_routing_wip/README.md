# Rev 5 routing, work in progress (2026-11-16)

Snapshot taken so the routing survives a cleared scratchpad. Not a finished board:
`../cryocooler.kicad_pcb` is still the old through-hole draft.

| File | State |
|---|---|
| `0_placement_input.kicad_pcb` | Board that `rev5_board.py place` starts from |
| `1_placement_approved.kicad_pcb` | Approved placement, 491 parts, no copper |
| `2_autorouted_128_open.kicad_pcb` | After one Freerouting round (12 passes) |
| `3_repaired_67_open.kicad_pcb` | After grid repair, plane ties and a second round: 67 open (43 on +3V3, 6 on +12V, 2 GND, 16 signals), 5 track-width errors |

To DRC one, copy `../cryocooler.kicad_pro` and `../cryocooler.kicad_dru` beside it
under the same basename. The `.py` files are the session's helper scripts
(`unstick.py` clears copper round stuck pads; the others draw floorplans and
close-ups). Method: `.claude/skills/kicad-pcb-autoroute/SKILL.md`.

Delete this folder once the routed board is in `cryocooler.kicad_pcb`.

## 2026-11-16 afternoon: wider placement

- `4_wide_placement`: re-placed board (0.7 mm fanout ring, J35 on the back at 97,30), not routed.
- `5_wide_routed_23_open`: Freerouting (14 passes) + gridroute + power nets wired at 0.3 mm. 23 open.
- `6_wide_ripup_best`: best board from `unstick_loop.py` at the time of saving (18 open), with its DRC report.
- `unstick_loop.py` + `ripone.py`: one stuck signal at a time, clear its neighbours, route it first,
  put the neighbours back, keep the trial only if the open count falls. `reach.py`: boxed-in pin report.
- Do not use gridroute `FINE=1` here: it routes at 0.1 mm clearance and the board rule is 0.15 mm.
- `7_merged_5_open` (+ its .kicad_pro/.kicad_dru with the 0.1 mm rules for the last nets): hand fixes g1-g3, g5 merged. 5 signals open (U107.18/.19, U104.5, U108.21, U105.12).

## 2026-11-17

- `12_connected_169_tight.*`: first board with 0 open and 0 errors (committed in 0772da0).
- `15_vias_clear_12v_widened.*`: current best. 0 open, 0 errors. 214 track-segment
  pairs under 0.15 mm (none under 0.1, none at a via), counted with
  `--all-track-errors` and the `tight_*` rules removed (`tight_list.py`). Thin +12V
  segments widened in place (`widen.py`); channel 1 DIRECT is on U108 GPB5.
- `localfix.py` re-routes the track at each tight spot at 0.15 mm; `fix12.py` and
  `nudge.py` are one-off moves; `bottleneck.py` gives the narrowest track feeding
  each pad of a net.
