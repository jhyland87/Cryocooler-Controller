# Rev 5 handoff: UCS 145-125 board with universal I/O

Branch `rev5-schematic`. Written 2026-11-17. Not fabricated, not bench tested.
Circuit decisions are in `kicad/DESIGN_REVIEW.md` (the five "Rev 5" sections);
this file covers the board and what is left.

## Where it stands

| Item | State |
|---|---|
| Schematic | Generated, ERC 0, 606 of 606 datasheet rules, `verify_netlist.py` clean (491 parts, 377 nets) |
| Firmware | `pin_config.h` synced, `pio run` builds. No drivers yet for the universal I/O, RS-485 or CAN |
| Board | Routed on 4 layers. DRC with schematic parity: 0 errors, 0 unconnected, 0 parity |
| Part labels | 375 of 491 parts (`rev5_board.py labels`) |
| Section lines and names | Applied (`rev5_board.py sections`) |
| Connector pin names | J2, J11, J12, J15, J21, J35 (`rev5_board.py pins`); no room at the other 18 |
| Revision mark | `REV5` on the back silk at the board ID spot (`rev5_board.py revmark`). The owner chose this over the board ID block for now (2026-11-17) |
| Gerbers, JLCPCB zip, renders | Exported from commit 69ca347 (`export_fab.py`). `fabrication/pcb-layer-stack.gif` is still the older board (captured by hand in KiCad) |
| BOM and CPL | Regenerated (`gen_bom.py`): 142 BOM lines, 476 placements |

Accepted DRC warnings (13): 6 `silk_edge_clearance`, 4 `silk_over_copper` (U32 outline
on the back), 2 `lib_footprint_mismatch`, 1 `silk_overlap` (C65 and D1 outlines).

## Board rules

- 4 layers only. In1 is the GND plane and carries no tracks; In2 carries signals and
  the +3V3 pour; GND and +3V3 pads reach their planes through a stub and a via.
- Clearance 0.15 mm, with 0.1 mm for the nets in the `tight_*` rules of
  `kicad/cryocooler.kicad_dru` (see "Rev 5 board" in `DESIGN_REVIEW.md` for the
  count and the fab limits). Order with filled and capped vias.
- Channel 1 DIRECT is on expander 1 GPB5 (U108 pin 2), not expander 0 GPA1.

## Tools

- `kicad/tools/rev5_board.py`: `place`, `preroute`, `route`, `reroute`, `finish`,
  `pins`, `labels`, `sections` (run in that order: pin names take the spots beside
  the pads first). `gen_pcb.py` placement tables are stale for rev 5; only its
  `link` mode is used (it now carries the do-not-populate flag).
- Routing notes: `.claude/skills/kicad-pcb-autoroute/SKILL.md`.
- `kicad/backup_rev5_routing_wip/`: routing snapshots and the one-off repair scripts.
  Delete it once the board is reviewed.
- The `kicad-pcb-edit` and `kicad-part-labels` skills describe the rev 3 / rev 4
  boards (mask labels in `mask_labels.json`); rev 5 uses silk labels from
  `rev5_board.py` instead.

## Open items

- Connector pin names: parts sit right behind J3-J6, J8-J10, J13, J30-J34 and
  J36-J39, so their names do not fit. Their pin order is in `PORTS` in
  `tools/render_callouts.py` (printed on the fab renders) and in each connector's
  schematic value. J1 and J14 are too fine to name.
- J2 (Mini-Fit Jr) has no 3D model: KiCad ships none and the Molex drawing could not
  be fetched for the housing height. The F1 model is printed "5A"; the BOM part is the
  10 A 0453010.MR.
- 116 parts without a label and 27 parts outside their floorplan section (accepted,
  see `DESIGN_REVIEW.md`).
- Not verified: JLCPCB's 0.2 mm via-to-track figure; TMUX7412F supply current; the
  pressure sensors and the OOM202 cell (no datasheet read); ADC input range at 4.5 V.
- Firmware: `SHUNT_OHMS` is still 0.015 (the rev 5 shunt is 10 mOhm).
- Unused items waiting for the owner's OK to delete: `sheets/aux_io.kicad_sch`, the
  ISOW7741 symbol and `ti_dfm0020a` footprint, the OPA593DNT and OPA4990IRUC symbols
  and the OPA4990 BOM entry, the LT3097 symbol / DFN-22 footprint / 3D envelope, the
  BLM15EX331SN1D and WSL2512 BOM entries, the Tensility jack footprint and
  `POWER_JACK`. `tools/softroute.py` is broken (it calls a missing
  `gridroute.apply_iso`).
- `tight_last_nets` lists more nets than still need 0.1 mm; prune it against a DRC
  run before ordering.
