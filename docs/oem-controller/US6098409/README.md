# US6098409: Temperature control of high-temperature superconducting thin-film filter subsystems

Superconductor Technologies (inventor David Chase), filed Dec 3, 1998, issued Aug 8, 2000. Copy of the source:
[US6098409.pdf](US6098409.pdf) (original file name: `Patent US6098409 - TEMPERATURE CONTROL OF HIGH TEMPERATURE
SUPERCONDUCTING FILTER SUBSYSTEMS.pdf`). US6256999 is a continuation with the same drawings; see
[../US6256999/README.md](../US6256999/README.md).

This is the analog generation of the controller: a two-loop analog temperature controller supervised by a
microcontroller. According to col. 3, FIGS 5(A)-(H) are the **mother board** and FIGS 6(A)-(C) the **daughter board**.

## Contents of this folder

| Sheet (PDF page) | Figure | Transcription |
|---|---|---|
| 1 (p2) | FIG 1: heat-sink | not transcribed (mechanical, out of scope) |
| 1 (p2) | FIG 2: two-loop controller 30 | [diagrams/fig2_two_loop_controller.drawio](diagrams/fig2_two_loop_controller.drawio) |
| 2 (p3) | FIG 3: control system 50 (inner PD and outer PID loops, limiter, knock/thermistor, µC) | [diagrams/fig3_system_block.drawio](diagrams/fig3_system_block.drawio) |
| 3 (p4) | FIG 4: filter loop 100 (per-carrier heater) | [diagrams/fig4_filter_loop.drawio](diagrams/fig4_filter_loop.drawio) |
| 4-20 (p5-21) | FIG 5A-5H: mother board schematics | KiCad, one page per figure: [../kicad/](../kicad/README.md) |
| 21-25 (p22-26) | FIG 6A-6C: daughter board schematics | KiCad, one page per figure: [../kicad/](../kicad/README.md) |

`source-pages/` holds 150 dpi renders of PDF pages 2-26 (`p-NN.png` = PDF page NN).

## Notes

- The text (col. 4-6) was used to label the diagrams correctly. Element 68 is a **limiter circuit**, not a switch.
  The **knock sensor 64** ("a PZT crystal based sensor (or microphone), a back EMF sensor circuit or current analyzer
  circuit that may be used to detect overstrokes") works with limiter 68 so the cooler "is not overdriven, for
  example, at start-up". Thermistor 60 and processor 62 limit drive when the cooler is too hot. Multiplier 70
  amplitude-modulates the 60 Hz drive. The PD inner loop takes outer-loop output 36, reference 74 and cold-finger
  signal 33. In FIG 4, element 92 is glass isolation pads, element 96 is thick-film heater resistors, and element 100
  is a PID controller.
- The FIG 2 diagram adds arrowheads to show signal direction; the patent draws plain lines.
