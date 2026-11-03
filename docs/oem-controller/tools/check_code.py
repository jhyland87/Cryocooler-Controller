"""
@file check_code.py
@brief Consistency checks for the transcribed US6446444 firmware (OCR error hunting).

1. NCP.MAP: the linker map lists every symbol twice (sorted by name and by
   address); both listings must agree, and every symbol must appear in a source.
2. C modules: bracket balance and `gcc -fsyntax-only` (TI-isms reported, not hidden).
3. Assembly: every instruction mnemonic must be a TMS320C2xx mnemonic or directive.
Usage: python3 -I check_code.py
"""

import re
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent / 'US6446444' / 'code'

# TMS320C2xx instruction set (SPRU127), the C2x-compatible forms dspa accepts
# (LAC, ADDK, EINT, ...), plus assembler directives used by TI cl2000/dspa.
MNEMONICS = set("""
ABS ADD ADDC ADDS ADDT ADRK AND APAC B BACC BANZ BCND BIT BITT BLDD BLPD CALA CALL CC CLRC
CMPL CMPR DMOV IDLE IN INTR LACC LACL LACT LAR LDP LMMR LPH LST MAC MACD MAR MPY MPYA MPYS
MPYU NEG NMI NOP NORM OR OUT PAC POP POPD PSHD PUSH RET RETC RETE RETI ROL ROR RPT SACH
SACL SAR SBRK SETC SFL SFR SMMR SPAC SPH SPL SPLK SPM SQRA SQRS SST SUB SUBB SUBC SUBS
SUBT TBLR TBLW TRAP XOR ZALR LT LTA LTD LTP LTS MPYK
LAC ADDK EINT DINT SUBK LALK ADLK SBLK
""".split())
DIRECTIVES = {'.global', '.ref', '.def', '.bss', '.text', '.data', '.sect', '.asect', '.usect',
              '.word', '.end', '.set', '.equ', '.include', '.copy', '.space', '.mmregs', '.int',
              '.long', '.string', '.title', '.width', '.length', '.option', '.if', '.else',
              '.endif', '.label', '.align', '.even', '.newblock', '.def', '.globl', '.byte'}


def strip_c_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    return re.sub(r'"(\\.|[^"\\])*"|\'(\\.|[^\'\\])*\'', '""', text)


def check_map():
    text = (CODE / 'NCP.MAP').read_text()
    pairs = re.findall(r'\b([0-9a-f]{8}) +(_[\w$]+|L\$\$\w+|RESET|\.bss|\.text|\.data|etext|edata|end|cinit|__\w+)', text)
    seen, problems = {}, 0
    for address, name in pairs:
        if name in seen and seen[name] != address:
            print(f'  map: {name} listed at {seen[name]} and {address}')
            problems += 1
        seen.setdefault(name, address)
    sources = '\n'.join(p.read_text() for p in CODE.iterdir() if p.suffix in {'.C', '.H', '.ASM'})
    words = set(re.findall(r'\w+', sources))
    missing = []
    for name in sorted(seen):
        if not name.startswith("_") or name.startswith("__") or "$$" in name:
            continue
        if name in words or name[1:] in words:
            continue
        missing.append(name)
    print(f'NCP.MAP: {len(seen)} symbols, {problems} address conflicts, '
          f'not found in sources: {missing or "none"}')
    return problems


def check_c():
    problems = 0
    for path in sorted(CODE.glob('*.[CH]')):
        body = strip_c_comments(path.read_text())
        for opener, closer in ('()', '[]', '{}'):
            if body.count(opener) != body.count(closer):
                print(f'  {path.name}: {opener} {body.count(opener)} vs {closer} {body.count(closer)}')
                problems += 1
        if path.suffix != '.C':
            continue
        result = subprocess.run(['gcc', '-fsyntax-only', '-x', 'c', '-std=gnu89', '-w', '-I', str(CODE),
                                 str(path)], capture_output=True, text=True)
        errors = [line for line in result.stderr.splitlines() if ': error:' in line]
        status = 'ok' if not errors else f'{len(errors)} errors'
        print(f'  gcc {path.name}: {status}')
        for line in errors:
            print('    ' + line.split('/')[-1])
    return problems


def check_asm():
    unknown = []
    for path in sorted(CODE.glob('*.ASM')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split(';', 1)[0]
            if not code.strip() or code.lstrip().startswith('*'):
                continue
            tokens = code.split()
            if not code[0].isspace():
                tokens = tokens[1:]  # label in column 0
            if not tokens:
                continue
            word = tokens[0]
            if word.upper() in MNEMONICS or word.lower() in DIRECTIVES:
                continue
            unknown.append(f'{path.name}:{number}: {word}')
    print(f'assembly: {len(unknown)} lines with unknown mnemonics')
    for item in unknown:
        print('   ', item)
    return 0


def main():
    problems = check_map() + check_c() + check_asm()
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
