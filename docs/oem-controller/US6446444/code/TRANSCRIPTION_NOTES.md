# Transcription notes: US6446444 firmware appendix

**How it was made.** PDF pages 13–104 were rendered at 300 dpi, put through rough OCR with tesseract, then transcribed by reading the page images character by character. Page furniture was removed: headers, column numbers, "264/278", "OC-82240.2", gutter line numbers and the vertical scan stamp. `tools/assemble_code.py` then split the pages into modules at the printed `<NAME> MODULE` headings.

**Rules.**
- The code is verbatim, including original typos, odd spacing, commented-out code and code that won't compile.
- No character on the 92 pages was unreadable, so the code contains no `⟦?⟧` markers.
- Lines the printer wrapped (a long comment continuing at column 0, a lone `-` after a `// ----` rule, or `;` + `====` rules) were rejoined onto the original line. Every rejoin is listed below.
- Column alignment was estimated from pixel positions. Tokens are exact; whitespace may be off by a column.

**Independent checks** (`python3 -I tools/check_code.py`):
- The linker map NCP.MAP lists all 119 symbols twice, once sorted by name and once by address. Both listings agree, and every symbol appears in the sources, which confirms the identifier OCR. That includes the `l`-vs-`1` and `0`-vs-`O` cases: `_lPidSp`, `_lCdSp`, `_TcEk0`, `_TcUk0`, `_ImEk0`, `_ImUk0`, `_Ilna`, `_Vlna`.
- Every C module passes `gcc -fsyntax-only` except MAIN.C. Its 3 errors come from the original's length-prefixed string initialisers (`const char csVersion[] = { 18, "4.1.08,05.18.01X\r" };`), a TI C2000 idiom that gcc rejects. This is not an OCR error, since the pattern repeats consistently.
- Every assembly mnemonic is a valid TMS320C2xx/C2x instruction or directive. VECTORS.ASM uses the C2x-compatible forms LAC/ADDK/EINT.

**Things to know.**
- The heading prints `KERNAL.H MODULE`, but the file is named `KERNEL.H`. That matches its include guard `KERNEL_H` and the module list in the patent text (col. 8).
- NCP.MAK and MAKEFILE print `-e _C_int0`, but the symbol is `_c_int0`. Kept as printed.
- In GLOBALS.H, the 48 V build has `#define MAX_IMOT 90L`; the rough OCR had misread it as 390L.
- The patent text lists the modules as VECTORS.ASM, TASKS.H, NCP.MAP, NCP.MAK, NCP.CMD (LINKER), KERNEL.H, ISRS.ASM, GLOBAL.H, C_REGS.H, BOOT.ASM, AFUNCS.ASM, EEPROM.C, KERNEL.C, MAIN.C, MISC.C, PARSER.C, TASKS.C and MAKEFILE. All 18 are present. The printed heading is `GLOBALS.H`, and the sources `#include "globals.h"`.
- Code Composer 4.10.36 for TMS320C2XX is the stated build tool (col. 8). The target is the TMS320F243 (NCP.CMD).

## Per-page notes

### PDF p013

- Omitted the "APPENDIX" title above the first module heading (document heading, not code).
- Rejoined printer word-wrap: lone `;` line + 76-char `=` rule at column 0 -> `; ====...` (twice, header open/close rule).
- Rejoined printer word-wrap: `; ===== external declarations` + following 48-char `=` rule line.
- Rejoined printer word-wrap: `; ===== global declarations (defined here)` + following 35-char `=` rule line.
- `=` rule lengths measured from pixel extents (76/48/35); +/-1 char possible.

### PDF p014

- `.text` placed at column 28 as printed (likely tab-expanded in original).
- Rejoined printer word-wrap: lone `;` + 76-char `=` rule (twice, PHANTOM header).
- Omitted a 1-px short horizontal mark at column 0 two lines after `.end` (gutter line 30); looks like a stray scan mark or a lone `_` — could not tell.
- Rejoined printer wrap: `// ----...` rule followed by lone `-` (twice, TASKS.H header) -> `// ` + 75 dashes (dash count measured from pixels, +/-1).
- Rejoined printer wrap: `// ----- function prototypes ----...` + lone `-` (dash count measured, +/-1).

### PDF p015

- Rejoined printer wrap: 77-char `*` banner line + lone `*` on next line -> 78 `*` (twice; count measured from pixels, +/-1).
- Map column positions derived from pixel measurement of the scan.

### PDF p016

clean

### PDF p017

- `00000210 _lPidSp`: first letter after `_` read as lowercase `l` (Courier `l`/`1` similar).
- `_TcEk0`, `_TcUk0`, `_ImEk0`, `_ImUk0`: final char read as digit zero (not letter O).

### PDF p018

- `0000023b _lCdSp`: first letter after `_` read as lowercase `l` (Courier `l`/`1` similar).
- `_TcEk0`, `_TcUk0`: final char read as digit zero.

### PDF p019

- `0000023b _lCdSp`, `00000210 _lPidSp`: letter after `_` read as lowercase `l`.
- Linker options: `-e _C_int0` printed with capital `C` (verbatim, differs from `_c_int0` symbol).
- NCP.MAK banner: star counts (13 before, 20 after the text) measured from pixels, +/-1.

### PDF p020

- `-c -e _C_int0 ...`: capital `C` in `_C_int0` as printed (verbatim).
- Star counts in `/******** End of Project Data ... ********/` measured (8 each).

### PDF p021

- Page begins with one blank printed line (gutter numbering) before the `/****/` banner; kept as a leading blank line.
- Banner `/****...****/` star count (75) and box `*/` column (75) measured from pixels, +/-1.
- `#$(CC) ... -x1`: last char read as digit `1` (could be `l`).
- Rejoined printer wrap: `#$(LINK) = ... -stack 128 -` + next line `x` -> `-stack 128 -x`.
- `_C_int0` with capital `C` as printed.

### PDF p022

- Page begins with one blank printed line; kept.
- `TASKS.OBJ : TASKS.C` / `dspcl TASKS.C` makefile lines: column of `:` (16) and command (18) measured; original likely used tabs.
- Rejoined printer wrap: all `// -----...` rules followed by a lone `-` line (header x2, macro definitions, typedef's, external declarations); rules padded to 78 chars total (+/-1).
- Rejoined printer word-wrap: `EVENTS pends; // events on which the task is` + `blocking` -> `... the task is blocking`.
- `EVENTS · pends;`: a small dot between `EVENTS` and `pends` treated as a scan speck (omitted).

### PDF p023

- Rejoined printer wrap: `// ----- function prototypes ---` + lone `-` (padded to 78 chars).
- Rejoined printer word-wrap: lone `;` + 76-char `=` rule at col 0 (twice, ISRS.ASM header).
- Rejoined printer wrap: `; -----...` rule (after synopsis) + lone `-` -> `; ` + 76 dashes.
- Rejoined printer word-wrap: `; ===== external declarations` + 48 `=`; `; ===== global declarations (defined here)` + 35 `=`.
- Rejoined printer word-wrap: ` ; **** IMPORTANT` + following 60-star line at col 0 (twice); star count measured (+/-1).
- Comment block lines ` ; ...` placed at column 1 (measured, could be column 2).

### PDF p024

- Rejoined printer word-wrap: `   ;` + 73-char `=` rule at col 0 (twice, SELECTION FLAG block) -> `   ; ` + 73 `=`.
- Rejoined printer word-wrap: `;` + 76-char `=` rule (twice, GISR2 header).
- Rejoined printer word-wrap: `; ===== GP Timer 1 period interrupt` + 42 `=`.
- `T1PINT_SISR` label: read as digit `1` after `T` (table uses `TPINT1`); verbatim.
- Rule/dash counts measured from pixels (+/-1).

### PDF p025

- Rejoined printer word-wrap: `;` + 76-char `=` rule (twice, GISR3 header).
- Table dash-row widths assumed identical to the GISR2 table (8/25/7/8).

### PDF p026

- Rejoined printer word-wrap: `; ===== GP Timer 2 period interrupt` + 42 `=`.
- Rejoined printer word-wrap: `; setup Direct addressing for the ADC` + `regs`.
- Rejoined printer word-wrap: `; take the ckticks value and mod it` + `with 8`.
- Rejoined printer word-wrap: `; store on the stack (AR1) and point` + `to ADC`.

### PDF p027

- Rejoined printer word-wraps: `...count to use` + `as the`; `...for the ADC` + `regs`; `...has any data` + `ready`; `...so not sign` + `extended`; `...there and reset` + `SP to AR1`.
- Rejoined printer word-wrap: `;` + 76-char `=` rule (twice, GISR5 header).
- GISR5 table: PIVR values printed at col 59 (one right of the `PIVR` heading) with a single space before Handled value, as printed.

### PDF p028

- Rejoined printer word-wrap: `; ===== SCI receiver interrupt (low` + `priority)` + 33 `=` -> one line.
- Rejoined printer word-wrap: `   ;` + 73-char `=` rule at col 0 (4 times: around the 04/13/01 comment and UPCASE - BEGIN).
- Comment-text column after `;` in the "Received characters..." block read as col 3 (two spaces after `;`).

### PDF p029

- Rejoined printer word-wrap: `   ;` + 73-char `=` rule at col 0 (8 times; UPCASE - END, ECHO - BEGIN, ECHO - END banners).
- Rejoined printer word-wraps: `...to see if it's` + `empty`; `...tx buffer is empty` + `again`.

### PDF p030

- Rejoined printer word-wraps: `; SciRxTail = (++SciRxTail) %` + `SCIRXLEN` (twice).
- Rejoined printer word-wrap: ` ; ===== SCI transmitter interrupt (low` + `priority)` + 30 `=` (count measured, +/-1).
- Comment text columns after `;` (43/44/45) measured from pixels; may be off by one.

### PDF p031

- Rejoined printer word-wrap: ` ; ===== SPI interrupt (low` + `priority)` + 42 `=`.
- Rejoined printer word-wrap: ` ; ===== return from interrupt` + 48-char `=` rule.
- Rejoined printer word-wrap: `;` + 76-char `=` rule (twice, sine-table header).
- Rejoined printer word-wrap: `...The 60Hz sinusoid is` + `divided`.
- Commented-out line `;  B  GISR5_EXIT  ; return` printed one column right of normal instruction columns (B at 12, operand 20, `;` 40); kept as printed.
- INDEX/VALUE numbers right-aligned (index ends col 44, value ends col 53), measured.

### PDF p032

- Sine table rows; every hex/index/decimal triple checked against the image (hex agrees with decimal on every row).

### PDF p033

- Sine table rows; every hex/index/decimal triple checked against the image (hex agrees with decimal on every row).

### PDF p034

- Sine table rows; every hex/index/decimal triple checked against the image (hex agrees with decimal on every row).

### PDF p035

- Sine table rows; every hex/index/decimal triple checked against the image (hex agrees with decimal on every row).

### PDF p036

- Rejoined wrap: two `// ----` rule lines each had a lone `-` wrapped onto the next line; rejoined (rule = `// ` + 77 dashes).
- Sine table values verified arithmetically against decimal comments (233-255).

### PDF p037

- Rejoined wrap: `// ----- global typedef's ---` rule had a lone `-` wrapped; rejoined.
- Rejoined wrap: `//  they are also declared, otherwise unpredictable` + `results will` (printed at column 0) joined with a space.
- Rejoined wrap: `#define MAX_IMOT 190L // this number corresponds to ~26App` + `(12V)` joined with a space.
- Rejoined wrap: `#define MAX_IMOT 90L // this number corresponds to ~12App` + `(48V)` joined with a space.
- `#define MAX_IMOT 90L` (else branch) is clearly `90L` (rough OCR said 390L).
- `//#define MAX_IMOT 220L` line: column spacing approximate (commented-out line shifted relative to others).

### PDF p038

- Rejoined wrap: `#define TCSW_300K 230 // Tcsw @ 300K, estimated from xfer` + `func`.
- Rejoined wrap: `#define TCSW_70K 965 // Tcsw @ 70K, estimated from xfer` + `func`.
- Rejoined wrap: `// ----- global declarations ---` rule had a lone `-` wrapped; rejoined.

### PDF p039

- Rejoined wraps: four `// ----` rule lines (global function prototypes, two C_REGS.H header rules, Digital IO) each had a lone `-` wrapped; rejoined.
- `/* parser.c 02/10/100 11.00.20 */` date read as printed (02/10/100).

### PDF p040

- Rejoined wraps: three `// ----- ... Module Registers ---` rule lines (SCI, ADC, SPI) each had a lone `-` wrapped; rejoined.

### PDF p041

- Rejoined wrap (x2): BOOT.ASM header rule printed as `;` on one line and a full line of 78 `=` at column 0 on the next; rejoined as `; ` + 78 `=` (a bare `====` line would not assemble). Same for the closing header rule.
- Rejoined wrap: `; ===== constant declarations` + next-line `=` run (49 `=`, counted from ink width).
- Rejoined wrap: `; ===== external declarations` + next-line `=` run (49 `=`).
- Rejoined wrap: `; ===== global declarations (defined here)` + next-line `=` run (36 `=`).
- `=` counts derived from measured ink width at ~17.8 px pitch; +/-1 possible.

### PDF p042

- Rejoined wrap (x2): `_c_int0` header rules printed as `;` + a next line of 78 `=`; rejoined as `; ` + 78 `=`.

### PDF p043

- Rejoined wrap (x2): `_hw_init` header rules printed as `;` + next line of 78 `=`; rejoined as `; ` + 78 `=`.
- Rejoined wrap: `; initialize the watchdog ---` rule had a lone `-` wrapped; rejoined.
- Rejoined wrap: `; initialize any global variables ---` rule had a lone `-` wrapped; rejoined.
- `_hw_init` label printed without a colon; kept as printed.
- Synopsis list skips 7) (goes 6) then 8)); kept as printed.

### PDF p044

- Rejoined wrap: `; setup IO output ---` rule had a lone `-` wrapped; rejoined.
- Rejoined wrap: `; PORTC[7-0] => input,low (don't` + `care)`.
- Rejoined wraps: `=> output,hi -` + `/EEPROM_WP`, `/EEPROM_EN`, `/EEPROM_HOLD` (PORTD[4], [3], [2]) and `=> input,lo  -` + `/LNA_ERR` (PORTD[0]); joined with one space.
- `Regiater B` typo kept as printed.

### PDF p045

- Rejoined wraps: four `; setup ... ---` rule lines (Event Manager, ADC's, SPI registers, SCI registers) each had a lone `-` wrapped; rejoined.
- Rejoined wrap: `; 0x0400 = T2TOADC starts ADC on` + `T2PINT`.
- Comment says 0x0400 while operand is #0040h; kept as printed.

### PDF p046

- Rejoined wraps: four `; ... ---` rule lines (setup the PWM outputs, setup the timers, initialize the system clock, mask/unmask and enable core interrupts) each had a lone `-` wrapped; rejoined.
- First line is commented out with `;;` prefix, which shifts the rest of the line right by 2 columns; kept.
- `#8600h, COMCON` line has an empty `;` comment; kept.
- `initiaize` typo kept as printed.

### PDF p047

- Rejoined wrap (x2): `_var_init` header rules printed as `;` + next line of 78 `=`; rejoined as `; ` + 78 `=`.

### PDF p048

- Rejoined wrap (x4): AFUNCS.ASM module header rules and BlockMove function header rules printed as `;` + next line of 78 `=`; rejoined as `; ` + 78 `=`.
- Rejoined wrap: `;       synopsis : Misc functions that are better written in assembly` + `language`.
- Rejoined wrap: `; AR0 = *SP (i.e. AR1), SP += 1, CAR =` + `AR2`.
- Rejoined wrap: `; AR2 <= points to the arguments on` + `the stack`.
- `_BlockMove` label printed without a colon; kept.

### PDF p049

- Rejoined wrap: `PSHD * ; put return address back on hardware` + `stack`.
- Rejoined wraps: four `// ----` rule lines (EEPROM.C header x2, SpiShift header x2) each had a lone `-` wrapped; rejoined (`// ` + 77 dashes).
- `SBRK #2` line has an empty `;` comment; kept.

### PDF p050

- Rejoined wraps: four `// ----` rule lines (EEPROM_Read and EEPROM_Write headers) each had a lone `-` wrapped; rejoined.

### PDF p051

- Rejoined wraps: four `//// ----` rule lines (commented-out EEPROM_Read/EEPROM_Write headers) each had `---` wrapped onto the next line; rejoined (`//// ` + 77 dashes).

### PDF p052

- Rejoined wraps: three `// ----` rule lines (EEPROM_Read header x2, EEPROM_Write header top) each had a lone `-` wrapped; rejoined.

### PDF p053

- Rejoined wraps: five `// ----` rule lines (end of EEPROM_Write header, empty function header x2, KERNEL.C header x2) each had a lone `-` wrapped; rejoined.
- Commented-out EEPROM_Write: comment says `// READ instruction` for 0x0002 (WRITE); kept as printed.

### PDF p054

- Rejoined wraps: `// ----- macro definitions ---`, `// ----- local function prototypes ---` and both TaskDispatcher header rules each had a lone `-` wrapped; rejoined. (`// ----- global variables ---` rule was not wrapped; kept at 79 chars.)
- `period registers.;` -- the `.;` is as printed (verified on a crop).

### PDF p055

- Rejoined wraps: four `// ----` rule lines (InitKernelModule header x2, MAIN.C header x2) each had a lone `-` wrapped; rejoined.
- `posts =  nTCB[i].pends & gPosts;` has two spaces after `=` as printed.

### PDF p056

- Rejoined wraps: `// ----- global variables`, `// ----- external variable declarations` and `// ----- local function prototypes` rules each had a lone `-` wrapped; rejoined.
- Rejoined wraps: `// ----- global string declarations` rule and the closing `// ----` rule after the table each had `--` wrapped (81-char rules); rejoined.
- `assmebly`, `measurment` typos kept as printed.

### PDF p057

- Rejoined wraps: five `// ----` rule lines (main header x2, InitMainModule header x2, SignOn header top) each had a lone `-` wrapped; rejoined.
- main() header uses a narrower label column (`//   function : main`, values at col 16) than other headers; kept as printed.

### PDF p058

- Rejoined wraps: seven `// ----` rule lines (SignOn header bottom, MISC.C header x2, clock header x2, AsciiToLong header top) each had a lone `-` wrapped; rejoined.
- Star comment box: star counts (76 per border line, right `*` at col 77) derived from measured ink width; +/-1 possible.
- Blank-line count between `} // SignOn` and `MISC.C MODULE` approximated from vertical gap (4 blank lines).

### PDF p059

- Rejoined wrapped lone `-` onto the three `// ----` rule lines (dash count approximate, normalized to `// ` + 77 dashes).

### PDF p060

- Rejoined wrapped lone `-` onto the four `// ----` rule lines (header rules and the two section banners); dash counts approximate.
- Column alignment of table comments approximate.

### PDF p061

- Rejoined wrapped lone `-` onto the three `// ----` rule lines.
- ASCII diagram under `arguments` (the `[S|I]  [0-9]+ = [0-9]+` arrows): bar positions and dash counts approximate; arrow labels aligned to one column as printed.

### PDF p062

- Rejoined wrapped lone `-` onto the `// ----` rule line before `static int next`.
- Rejoined printer-wrapped word `columns` onto `asm( "   MPY     #7H ..." ); // IMPORTANT - change for # of map columns`.
- Stack-layout box drawing: dash counts/column positions approximate.
- `// AR = 3` comment printed as-is (likely meant ARP).

### PDF p063

- Rejoined wrapped lone `-` onto the two header rules and three `// ---` section banners (dash counts approximate).
- Rejoined printer-wrapped word `amp` onto `#define TDX_OK IOPB1 // bit line that controls the RS232 amp`.

### PDF p064

- Rejoined wrapped lone `-` onto the banner `// --- SmStatusBitFlag bit field definitions ---` and onto the `// ------------   -----...` table rule.
- Rejoined printer-wrapped word `bit` onto `#define SMBF_FAULT_LED 0x0008 // FAULT led, matches IO port bit`.
- Line `//  ...  1 = BYPASS relay on` is printed one column further left than its neighbours; preserved as printed.

### PDF p065

- Rejoined printer-wrapped tails: `bit` (SMBF_READY_LED, SMBF_ALIVE_LED comments), `4` (SMBF_LNA_CTRL, SMBF_FAULT_RELAY, SMBF_BYPASS_RELAY comments `>> 4`), `median filter` (SMBF_TCSN_FILTER comment), `requires` (LED comment block).
- Rejoined wrapped macro bodies: LED_MASK `(SMBF_FAULT_LED|SMBF_READY_LED|SMBF_ALIVE_LED)`, LED_ON/LED_OFF/LED_TOGGLE second statement, RELAY_MASK `((SMBF_LNA_CTRL|...)>>SHIFT_TO_RELAY)`; padding between macro name and body reconstructed to column 36.
- Lone `-` rejoined onto `// --- SmErrorBitFlag bit field definitions` banner.
- RELAY_ON/RELAY_OFF/commented //#define body columns are irregular in the print; preserved approximately.

### PDF p066

- Rejoined wrapped lone `-` onto the table rule and the three section banners (state machine state, digital filter, global variables).
- Rejoined printer-wrapped word `it` onto `UINT NvAddress; // S12 sets variable, S13 read/write it`.

### PDF p067

- Rejoined wrapped lone `-` onto the five `// ----- ...` section banners.
- Rejoined printer-wrapped comment tails: `status` (SmStatusBitFlag), `errors` (SmErrorBitFlag), `U(16,16)` (ImOut), `sensor` (Tcsn).
- `lCdSp` / `lPidSp`: first glyph read as lowercase `l` (Hungarian long prefix); glyph is close to digit `1` in this font - cross-check with NCP.MAP.

### PDF p068

- Rejoined wrapped lone `-` onto the `// ----- local function prototypes` banner and the two `// ----` header rules.

### PDF p069

- Rejoined wrapped lone `-` onto the two `// ----` header rules.
- `else                     // --- initialization`: spacing before comment approximate.

### PDF p070

clean

### PDF p071

- Rejoined wrapped lone `-` onto the two `// ----` header rules.
- Rejoined printer-wrapped word `temperature` onto `case  0 :  // measure Trej - motor heat reject temperature`.

### PDF p072

- Rejoined printer-wrapped words `voltage` (case 2 comment) and `draw` (case 3 comment).

### PDF p073

- Rejoined wrapped lone `-` onto the `// ----` header rule.

### PDF p074

- Rejoined wrapped lone `-` onto the header rule, the `// --- Do fatal error check` and `// --- Begin State Machine` banners, and the two indented `// ----` rules around the SM_INIT comment block.
- Rejoined printer-wrapped words `because` (`// inequality is reversed because`) and `facilitate` (SM_INIT comment).
- `stopping the state machint` - original typo kept.

### PDF p075

- Rejoined wrapped lone `-` onto the two indented `// ----` rules around the SM_IDLE comment block.

### PDF p076

- Rejoined wrapped lone `-` onto the indented `// ----` rule before the SM_COOLDOWN comment block.
- `drive to tne motor` - original typo kept.

### PDF p077

- Rejoined wrapped lone `-` onto the indented `// ----` rule closing the SM_COOLDOWN comment block.
- Rejoined printer-wrapped tails: `variables` (`// initialize the PID variables`), `in this state` (start_time comment), and `U(16,16)` on four `... = U(16,16)` comments (ImSpCoolDown_m, ImSpCoolDown_b, and the two commented-out 75W lines).
- Column positions of the trailing `// U(...)` comments and the `: m =` / `: b =` comment lines are approximate.
- Note: `TcUk0 = 0;` appears twice in a row in the original (kept verbatim).

### PDF p078

- Rejoined printer-wrapped tails: `= U(16,16)` / `U(16,16)` on eight `// U(...)` comments (both the commented-out 75W block and the #else 12V block), and `sp` on `// keep tracking the cool down sp`.
- `// U(16,16) - U916,16) = U(16,16)` - original typo `U916,16)` kept verbatim.
- Column positions of the trailing comments in the commented-out blocks are approximate.

### PDF p079

- Rejoined printer-wrapped words `coolder` (`// impiles Tcsn > TcSp, coolder`) and `code` (`// so shift control to the PID code`); original spellings `impiles`/`coolder` kept.
- Rejoined wrapped `--` onto the `// --- error checking ---` banner, and lone `-` onto the two `// ----` rules around the SM_CONTROL comment block.
- `// SM_CONTROL (3)  : Applies ...`: a small speck after `(3)` in the scan was ignored as noise.

### PDF p080

clean

### PDF p081

- Rejoined wrapped `--` onto the `// --- error checking ---` banner and lone `-` onto the two `// ----` rules around the SM_POWERDOWN comment block.
- Rejoined printer-wrapped word `setpoint` onto `// decrement the power setpoint`.
- A small speck above `error` in the banner line ignored as scan noise.

### PDF p082

- Rejoined printer-wrapped '-' onto the three '// ----' rule lines (lines 27, 35, 55 of the printed page).

### PDF p083

- Rejoined printer-wrapped '-' onto the three '// ----' rule lines.
- Rejoined printer-wrapped word "to" onto `{   // cooled enough` -> `// cooled enough to`.

### PDF p084

- Rejoined printer-wrapped '-' onto both '// ----' rule lines.
- Rejoined printer-wrapped word "SciTxBuf" onto `if( retval == 0 )  // indicates no data copied to` -> `... copied to SciTxBuf`.
- `#if !defined( TOWER_MOUNT_CODE  )`: gap before `)` measures as two spaces; kept two.

### PDF p085

- Rejoined printer-wrapped "data into" onto `// else the command handler copied` (comment line after #endif).
- Rejoined printer-wrapped "letting" onto `// ... first character of the SciTxBuf[]` -> `SciTxBuf[] letting`.
- Rejoined printer-wrapped '-' onto both '// ----' rule lines.

### PDF p086

- Rejoined printer-wrapped "xmit" onto `gPosts &= ~SCI_TX_DATA_READY;  // clear the event that started the` -> `... started the xmit`.
- Rejoined printer-wrapped '-' onto the '// ----' rule line.

### PDF p087

- Rejoined printer-wrapped "accumulator" onto `case 1 :  // --- LED's off, increment run time` -> `... run time accumulator`.
- Rejoined printer-wrapped '-' onto the '// ----' rule line.

### PDF p088

- Rejoined printer-wrapped "off" onto `if( gPosts & SYS_DATA_OUT )  // check to see if if we're turning` -> `... turning off`.
- Rejoined printer-wrapped '-' onto both '// ----' rule lines.

### PDF p089

- Rejoined printer-wrapped '-' onto both '// ----' rule lines.
- `lCdSp` / `lPidSp`: leading char read as lowercase 'l' (long prefix), consistent with declarations elsewhere.

### PDF p090

- Rejoined printer-wrapped '-' onto both '// ----' rule lines and onto the `case  0 :  // ----- (S0) ... gain ----------` banner (now 11 trailing dashes).
- `for( ... ; TcsnDataIndex ;  )`: gap before `)` measures as two spaces; kept.

### PDF p091

- Rejoined printer-wrapped '-' onto each `case  N :  // ----- (SN) ...` banner (S1..S5); banners end at the same column as the S0 banner. On S2 the wrapped '-' follows a space: `... saturation limit -`.

### PDF p092

- Rejoined printer-wrapped "task" onto `gPosts |= SYS_DATA_OUT;  // set the event, this toggles the` -> `... toggles the task`.
- Rejoined printer-wrapped "SciTxBuf );" onto both `retval = LongToAscii( (long)((SmStatusBitFlag & SMBF_DEBUG|SMBF_MODE)?1:0),` lines, joined with one space (space assumed lost at the wrap point).
- Rejoined printer-wrapped '-' onto the `case  6 :` banner.
- On this page the `case N :` banner comments start one column further left (col 22) than on p-091 (col 23); measured, kept as printed.

### PDF p093

- Rejoined printer-wrapped "SciTxBuf );" onto the S9 `retval = LongToAscii( ... SMBF_LNA_CTRL)?1:0),` line (one space).
- Rejoined printer word-wrapped "SMBF_FAULT_RELAY)?1:0), SciTxBuf );" onto `retval = LongToAscii( (long)((SmStatusBitFlag &` (one space).
- Rejoined printer word-wrapped "SMBF_BYPASS_RELAY)?1:0), SciTxBuf );" onto `retval = LongToAscii( (long)((SmStatusBitFlag &` (one space).

### PDF p094

- Rejoined printer-wrapped '-' onto the '// ----' rule line.

### PDF p095

- Rejoined printer-wrapped "SciInputReady)." onto `// synopsis : Handles INQUIRE commands from the user (see` -> `(see SciInputReady).`.
- Rejoined printer-wrapped '-' onto the '// ----' rule line and onto each `case  N :  // ----- (IN) ...` banner (I0..I6).

### PDF p096

- Rejoined printer-wrapped "SciTxBuf" onto `BlockMove( &csVersion, SciTxBuf );   // copy version string into` -> `... into SciTxBuf`.
- Rejoined printer-wrapped '-' onto each `case N :  // ----- (IN) ...` banner (I7..I10) and both '// ----' rule lines.

### PDF p097

- Rejoined printer-wrapped '-' onto all four '// ----' rule lines.
- asm string spacing (`" LDP     #0E8h"`, `" SPLK    #000Fh, 07413h"`) measured from column positions; operands aligned at the same column.

### PDF p098

- Rejoined printer-wrapped "upside" onto `if( it > TcLimI )  // limit windup to +TcLimI on the` -> `... on the upside`.
- Rejoined printer-wrapped '-' onto both '// ----' rule lines.

### PDF p099

- Rejoined printer-wrapped "U(16,16)" onto `// synopsis : ... return a 32-bit number in` -> `... number in U(16,16)`.
- Rejoined printer-wrapped '-' onto all three '// ----' rule lines.
- `accumulator = 0l;` / `trial = 0l;` / `remainder = 0l;`: suffix glyph has a flat top serif (lowercase L) unlike the flagged digit '1' in `+ 1`; transcribed as `0l`.

### PDF p100

- Rejoined printer-wrapped '-' onto the '// ----' rule line.
- `//  SciTxBuf[ j++ ] = 'O';`: read as letter O (test code writing "OK"); glyph is round like the 0s nearby but paired with 'K'.

### PDF p101

- Rejoined printer-wrapped '-' onto both '// ----' rule lines.
- In the `#else` (DB_ECHO) block, the printer word-wrapped each `echo( (long)X );` call: for TcLimI/TcKp/TcKi/TcKd/TcSp the trailing ");" wrapped; for TrejLoTemp/TrejHiTemp/TambLoTemp/TambHiTemp/IlnaLoCurrent the "(long)X );" wrapped after `echo(`. Rejoined each as `echo( (long)X );` (single space restored at the wrap point, matching the unwrapped spacing pattern).

### PDF p102

- Each `echo( (long)X );` call (IlnaHiCurrent, VinLoVolts, VinHiVolts, TcswLoTemp, TcswHiTemp, TcsnLoTemp, TcsnHiTemp, ImLoLimit, //ImHiLimit) was printer word-wrapped after `echo(`; rejoined as `echo( (long)X );` with one space.
- Rejoined printer-wrapped '-' onto both '// ----' rule lines.

### PDF p103

- Rejoined printer-wrapped '-' onto all seven '// ----' rule lines.

### PDF p104

- Rejoined printer word-wrapped "range" onto `// ambient temperature out-of-` -> `out-of-range` (no space; wrap occurred at the hyphen).
- Rejoined printer-wrapped '-' onto all three '// ----' rule lines.
- Last appendix page; ends with an empty function header block.
