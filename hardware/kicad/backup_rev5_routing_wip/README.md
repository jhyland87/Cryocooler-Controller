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
