# US6446444 B1: DSP control of a Stirling-cycle cryocooler drive and HTSC filter temperature loop

Superconductor Technologies, filed May 31, 2001, issued Sep 10, 2002. Copy of the source: [US6446444.pdf](US6446444.pdf)
(original file name: `Patent US6446444 - DIGITAL SIGNAL PROCESS CONTROL OF STIRLING CYCLE CRYOGENIC COOLER DRIVE.pdf`).
This is the DSP generation of the controller: a TMS320F243 replaces the analog loops of US6098409.

## Contents of this folder

| Source (PDF page) | Figure | Transcription |
|---|---|---|
| p1 (cover) | same drawing as FIG 5A | [diagrams/fig5a_drive_current_loop.drawio](diagrams/fig5a_drive_current_loop.drawio) |
| p2-4 | FIG 1-4: heat-sink, cooler and enclosure mechanics | not transcribed (physical layout, out of scope) |
| p5 | FIG 5A: cryocooler drive (current) loop 20 | [diagrams/fig5a_drive_current_loop.drawio](diagrams/fig5a_drive_current_loop.drawio) |
| p6 | FIG 5B: temperature control loop 60 (operating vs cooldown) | [diagrams/fig5b_temperature_control_loop.drawio](diagrams/fig5b_temperature_control_loop.drawio) |
| p7 | FIG 6: DSP board block diagram | [diagrams/fig6_dsp_board_block.drawio](diagrams/fig6_dsp_board_block.drawio) |
| p8 (top) | FIG 7: software pace-loop kernel 150 | [diagrams/fig7_pace_loop_kernel.drawio](diagrams/fig7_pace_loop_kernel.drawio) |
| p8 (bottom) | FIG 8: interrupts and clock dividers | [diagrams/fig8_interrupts_and_clock.drawio](diagrams/fig8_interrupts_and_clock.drawio) |
| p13-104 | Source-code appendix | [code/](code/INDEX.md): 18 module files, verbatim |
| p9-12, 105 | Description and claims | quoted in [../analysis/](../analysis/) |

`source-pages/` holds 150 dpi renders of the drawing pages for side-by-side checks.

This patent contains **no electrical schematics**. FIG 6 is a block diagram, so there is no KiCad page for it.

## Notes

- The diagrams follow the drawings. Where the specification text adds detail (FIG 7 timing, FIG 8 interrupt
  priorities), it appears as a note box with its column reference.
- The cover drawing (p1) is the FIG 5A drawing, so one file covers both pages.
- **What the description says about overstroke** (col. 8): "the cryocooler 8 drive is preferably controlled for the
  purpose of producing maximum drive allowable without causing damage to the cryocooler 8 through overstroking, by
  using criteria either stored in a look-up table within DSP memory and/or by calculations made within the DSP."
  How the published code does this is in [../analysis/OVERSTROKE.md](../analysis/OVERSTROKE.md).
