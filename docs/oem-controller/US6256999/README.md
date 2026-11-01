# US6256999 B1: Temperature control of HTSC filter subsystems

Copy of the source: [US6256999.pdf](US6256999.pdf) (original file name: `Patent US6256999 - TEMPERATURE CONTROL OF HIGH TEMPERATURE SUPERCONDUCTING FILTER SUBSYSTEMS.pdf`).

US6256999 (filed Aug 8, 2000; issued Jul 10, 2001) is a **continuation** of US6098409 (application
09/204,897, filed Dec 3, 1998), per the "Related U.S. Application Data" on its front page. It has the same 25
drawing sheets and the same description. **Nothing is transcribed again here.** Its diagrams and schematics live
under [../US6098409/](../US6098409/README.md), and its KiCad pages are in the
[shared project](../kicad/README.md).

## Sheet-by-sheet check against US6098409

I rendered all 25 drawing sheets of both PDFs (PDF pages 2-26) and compared them side by side.

| Sheet | Figure | Result |
|---|---|---|
| 1 | FIG 1, FIG 2 | Same drawing (different scan; header date and patent number differ) |
| 2 | FIG 3 | Same |
| 3 | FIG 4 | Same |
| 4 | FIG 5A | Same |
| 5 | FIG 5B | Same |
| 6-7 | FIG 5C-1, 5C-2 | Same |
| 8-10 | FIG 5D-1 … 5D-3 | Same |
| 11 | FIG 5E | Same |
| 12-13 | FIG 5F-1, 5F-2 | Same |
| 14-17 | FIG 5G-1 … 5G-4 | Same |
| 18-20 | FIG 5H-1 … 5H-3 | Same |
| 21-22 | FIG 6A-1, 6A-2 | Same |
| 23-24 | FIG 6B-1, 6B-2 | Same |
| 25 | FIG 6C | Same |

The comparison was visual, at sheet level. Every sheet carries the same figure with the same layout and
component placement. Scan noise means individual characters were not compared pixel by pixel. The US6098409
scans are the ones that were transcribed.

## What does differ (text only)

- **Claims.** US6256999 has 9 claims; US6098409 has 15. Claims 6-8 of '999 claim the knock sensor on its own:
  "a second signal from a knock sensor used to detect overstrokes of the cryocooler" (claim 6); "the
  knock sensor is a sensor selected from the group consisting of a PZT crystal based sensor, back EMF sensor
  circuit, and current analyzer circuit" (claim 8); and "the limiter circuit outputs a signal to a
  multiplier circuit used to drive the cryocooler" (claim 7). PDF p30, col. 8.
- **Certificate of Correction** (PDF p31): changes "sensor 66" to "sensor 64" at col. 5, lines 33 and 37. The knock
  *sensor* is 64; its *processor* is 66.
- The description is otherwise word-for-word the same apart from the continuation line in col. 1.

See [../analysis/OVERSTROKE.md](../analysis/OVERSTROKE.md) for how these fit together.
