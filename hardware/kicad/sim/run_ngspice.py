"""Runs a SPICE deck through KiCad's bundled libngspice (no standalone ngspice binary needed).

Usage: python3 run_ngspice.py deck.cir
"""
import ctypes
import sys

LIB_PATH = '/Applications/KiCad/KiCad.app/Contents/PlugIns/sim/libngspice.dylib'
CODEMODEL_DIR = '/Applications/KiCad/KiCad.app/Contents/PlugIns/sim/ngspice'

SEND_CHAR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
SEND_STAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
CONTROLLED_EXIT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int,
                                   ctypes.c_void_p)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ngspice = ctypes.CDLL(LIB_PATH)

    def on_output(text, _ident, _user):
        print(text.decode(errors='replace'))
        return 0

    callbacks = (SEND_CHAR(on_output), SEND_STAT(lambda *_: 0), CONTROLLED_EXIT(lambda *_: 0))
    ngspice.ngSpice_Init(callbacks[0], callbacks[1], callbacks[2], None, None, None, None)
    # TI PSpice-style models need PSpice compat mode, set before the deck is parsed.
    ngspice.ngSpice_Command(b'set ngbehavior=ltpsa')
    ngspice.ngSpice_Command(f'source {sys.argv[1]}'.encode())
    ngspice.ngSpice_Command(b'quit')


if __name__ == '__main__':
    main()
