# Handoff: where this work stopped (2026-11-01)

Branch `oem-controller-reference`, nothing committed. All work lives in `docs/oem-controller/`. The plan is
in `~/.claude/plans/users-justinhyland-documents-chem-cryoc-keen-shell.md`.

## Done
- PDFs copied: 3 patents and 2 manuals. Source pages rendered to `*/source-pages/`.
- **Firmware:** all 92 appendix pages transcribed, in `US6446444/code/` (18 modules plus INDEX, PAGE_MAP and TRANSCRIPTION_NOTES).
  - `tools/check_code.py`: all 119 NCP.MAP symbols are found and agree, and the asm mnemonics are valid. All C files compile
    except MAIN.C, which fails only on the TI string-initializer idiom.
- **draw.io diagrams:** 8 patent figures, 3 manual figures and 3 state machines. All were viewed and laid out cleanly.
  The generators are `tools/gen_drawio_*.py`, built on `tools/drawio.py`.
- **Docs:** `manuals/superlink_states.md`, `manuals/superfilter_states.md`, `analysis/STATE_MACHINE.md`, all READMEs,
  `US6256999/README.md` (sheet-by-sheet match), and a draft of `analysis/OVERSTROKE.md`.
- **KiCad:** generator `kicad/tools/` (oemsch.py, gen_oem_schematic.py, verify_netlist.py, check.sh, erc_summary.py).
  All 11 specs are in `kicad/specs/`. Each one passed `check.sh` on its own with 0 netlist problems, except
  fig5c/fig5e, whose agent had not reported when the session paused (the files exist; re-check them).
- `analysis/_work/evidence_dossier.md`: the research agent's full cited dossier, with the MAX_IMOT OCR error corrected.
  `kicad/AGENT_BRIEF.md`: the brief the schematic agents followed.

## Still to do
1. **fig5c/fig5e:** the agent's run passed (404 pins, 0 problems). Re-run once in the combined build. Its overstroke
   topology is summarised below; copy it into OVERSTROKE.md §2.3.
2. **Build all specs together.** Run `check.sh /tmp/oem-all`. Cross-page issues to resolve:
   - **Net aliases** (planned: an alias table in `gen_oem_schematic.py` that joins obvious misprints at build time and
     records each in the notes):
     - `COOLER_MON` (5G) = `COOLER.MON` (5H)
     - `ERR_WARNERS` (5G) = `ERR.WARMERS` (5H)
     - `CS_CNTRL` (5A) = `CS_CTRL` (5B, 5H)
     - `DEWAR_TEMP` (5A) = `DEMAR_TEMP` (5H)
     - `HOT-TOTAL` (5G) vs the 5E name: check the spelling
   - **Ask the user:** should `HSP_CLK/PROG/READ` (5G) join `NSP_*`? Joining would also tie U22 pin 1.
   - **Ground naming is inconsistent:** `DGND` (5A/5B, filled-arrow ground), `GND` (5G maps both styles to GND),
     `5F_GND_D` (5F). Pick one rule and apply it everywhere.
   - **`MM(8)`** on 5H is probably `MM(2)`. **`REF_3`/`REF_4`** on 6B are one conductor (named REF_4).
   - **CBY_1:** every daughter-board channel output is printed CBY_1. That is a drafting error, kept as printed.
   - **Refs containing `?`** (`6C_R?1` etc.) may trip KiCad annotation; rename them if ERC complains.
   - **Driven but unconnected pins:** 5G has 28 pin_not_connected, plus V2 pins 21/22 and J12 pin 9 on 5F/5H.
3. **Write the real project:** `python3 -I kicad/tools/gen_oem_schematic.py`. Render the PDF and look at every page.
4. **Write `kicad/TRANSCRIPTION_NOTES.md`** from the agent findings below.
5. **Finish `analysis/OVERSTROKE.md` §2.3** (5C circuit, plus BACK_OFF_COUNT → U22 PE3/AN3 pin 39). Then write
   `tools/gen_drawio_overstroke.py` → `analysis/diagrams/overstroke_signal_path.drawio`. It is referenced in the README
   but does not exist yet.
6. **Final checks:** every .drawio parses; `git status` shows only `docs/oem-controller/`. Then ask before committing.

## Agent findings, per figure (for TRANSCRIPTION_NOTES)
- **5A** (46 parts):
  - The three connectors have no printed refs; they are J5A1/J5A2/J5A3.
  - BWT_4P is printed on J5A3 pins 9 and 11 (shorted as drawn).
  - Repeated pin numbers on U44B, U29 and U17 (pin 10 printed three times).
  - U56 supply pins are unnumbered; R276 has no value.
  - Spare op-amp "+" signs are drawn on the fed-back input.
  - Rack/tower option table is reproduced as NOTES.
  - Guesses: MC93 = MC14093B, MC04 = 74HC04/MC14069, LMC6-482 = LMC6482.
- **5B** (35 parts):
  - U43A has two pins labelled V-.
  - R296, C109 and C98 have no value; C108 is printed "10K".
  - C90 appears twice. R2-48 and R2-49 have hyphenated refs.
  - Repeated pins on U36 (13, 6) and U29 (6).
  - U29 O3 has an N/C mark but the line continues; it is connected.
  - NSP_SERO is read as NSP_SER0.
  - U29 is MC93 on 5A but MC2001 on 5B.
- **5D** (162 parts):
  - Six identical-topology heater drivers.
  - Serial chains: NSP_SERI→V9→V7→V22→NSP_SER5 and NSP_SERI→V24→V39→V51→NSP_SER8.
  - Circuit #1's output is printed BWT_1P (same as its input) and #4's input is printed BWH_4P; both are shorts as
    printed. #5's output is BWK_5P.
  - Duplicate refs: R78 ×3, R16, R3, R6, R176, R179. CR13/17/19 are printed 1N4140.
  - The MC2030 GND pin is unnumbered. MC2030 is unidentified (a dual 1K serial digital pot).
- **5F** (72 parts):
  - Duplicates: C112, C130 ×3, C149, C159, U45, R229 ×3.
  - The two input flags print the same "+27VINK(RM)/+48VINK(TM)"; the return side is named 5F_VIN_RTN.
  - "+SUREF" is probably +5VREF.
  - Regulators, NPN, fuse and test points have no refs (UX1-4, QX1, FX1, TPX1-4).
  - L0/L7 are both printed +5V.
  - R230's connection to +15V across the sheet edge is assumed. LT1007 V- is assumed to be pin 4.
  - Guess: URE319 = VRE310 (paralleled with AD2710).
- **5G** (81 parts):
  - U22 is split into U22A and U22B.
  - ADC inputs: PE7 RESERVED, PE6 PWR_MON, PE5 COOLER_MON, PE4 HOT-TOTAL, **PE3 BACK_OFF_COUNT (pin 39)**,
    PE2 ERR_WARNERS, PE1 T.CLUSTER, PE0 SYS.CMD.
  - Relays: ALARM- on pin 27 → U30 → K3 (FAULT_O/FAULT_NO). LNA_AMP_PWR on pin 30 → K1 (LNA_SW_PWR → J10 VDD-1..6).
    RF_BYPASS on pin 31 → K2 (+27VIN → J11).
  - Many duplicate or missing pin numbers (data pins all printed "62", etc.).
  - Unlabelled parts: the optos, the memory (PSD-type), the RS-232 chip (MAX232) and the fuse.
  - Guesses: U22 = 68HC11K family, U21B = DS1232, U30 = DS3658, UR1 = LM317 (~3.4 V).
  - The quadrant line matching is documented in its report.
- **5H** (78 parts):
  - Fixed errors in the original example: V12 pins 6 and 7 are separate nets, and the AD590 has a third (case) lead.
  - V+ is printed as pin "0" (probably 8). R51/R48 are printed "1.000K .1v".
  - Duplicates: R57, R59 ×3, R48, R43, C19, V13 (LT1124 and LM06482).
  - D6496 (= DG506A): pin 19 is labelled "A4", GND is "L2", and the D pin is printed "XX".
  - MM(8) is probably MM(2). Placeholder values XX.XK, XX.K and CNET. The "XXX" flag is kept local.
- **5C** (109 parts; 5C-1 and 5C-2 joined by matching 8 edge lines in order). **OVERSTROKE BACK-OFF CIRCUIT:**
  1. **Trip.** U48 LT1011A compares HOG_T against the R255/R256/R285 pot. The U48 output, pulled up by R233, is the
     trip. **[assumption]** HOG_T is the knock/overstroke sensor channel.
  2. **One-shots.** The trip feeds the "O" (+edge) input of both U28 HC123 sections. CLR = SHUTO_T.
     - Short section: R144 10K / C53 2.2uF ≈ 10 ms. Q̄ → Q5 INLD110 off → R167 64.8K → Q4 (2N4220 used as a JFET diode)
       adds a fixed step of charge to C71 10uF. This is the counter.
     - Long section: R145 640K / C72 100uF ≈ 30 s. While it keeps being retriggered it holds Q1 off. After about 30 s
       with no trips, Q1 bleeds C71 through R130 1M.
  3. **Reset.** SHUTO_T low clears both one-shots, turns Q2 off and precharges C71 to about 2.5 V via R190/R142 and Q3.
  4. **Output.** C71 → R143 → U27 follower → **BACK_OFF_COUNT** (→ U22 PE3, the µC ADC).
  5. **Into the drive.** BACK_OFF_COUNT → R141 → U27 (offset from -10V via R165/R197) → R163 ("XXX") → U26 pin-3 node,
     together with the CMT rectifier (R140). U26 acts as an ideal-diode clamp on the U34 sum. The signal is taken from
     the U26 pin-2 node → R162 → U33 → NOT_TOTAL (TP1).

  Other 5C items:
  - Duplicates: R199, C155, C141, R285 (resistor and pot), C76, R194, R162.
  - U26 is drawn as both an LT1124 and a single op-amp pinout, so it is split into U26A and U26B.
  - On the U28 second section, Q is printed as pin 3 and Cext as "OK".
  - U33 V- goes to the R162/R187 node.
  - R266 is printed "221K(RM)/49.0K", R283 has no value, C49 is ".001SUF", CR10/CR11 are 1N4140.
  - Unlabelled arrows: 5C_R126_ARROW and 5C_R191_ARROW.
  - Names are printed with dots: WP.SHOSET, WP.SHTR.
- **5E** (38 parts):
  - Unref'd parts: RX1/RX2 (RX2 is probably R135), CX1-6, UX1 (an MC2030-family part), UX2 (SPI), UG1 (OR gate,
    with pin 4 printed on both an input and the output).
  - No values on R35/R134/R136/R132/R270. There is no L3.
  - "HOT TOTAL" is used as `HOT_TOTAL`; it may equal 5C's NOT_TOTAL and/or 5G's HOT-TOTAL. **Decide.**
  - "NSP_PROG-"/"NSP_READ-" are mapped to NSP_PROG/NSP_READ.
  - `+27URET` (probably +27VRET) and `99-` are kept as printed.
  - Unlabelled down-arrows are kept as separate nets. U46 pin 4 and U10 V- are assumed to be -15V.
- **6A/6B/6C** (94+94+22 parts):
  - All outputs are printed CBY_1. 6B joins the V17 and V18 outputs (REF_3/REF_4).
  - The J8 channel is wired differently.
  - The LTC1150 pin 5 stub is left out; LT1007 output is printed as pin 8.
  - 6C: no values printed for R63/69/73/74/80 or C71/74/77. U20 pins are assumed. A second, unlabelled op-amp stage.
    J15 key is spelled "POLARIZATION KEY". J10 pins 17-20 are unnamed.
  - Duplicates: C2 ×3, C19, R13, R25, C30 (6A); R43, C50, C49 (6B). R54 and J10 also appear on other figures.
