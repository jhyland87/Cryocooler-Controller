"""Ties pads a DRC report lists as unconnected to the GND or +3V3 plane, with a short stub
to the nearest via of that net or to a new via beside the pad.

Usage: plane_ties.py board.kicad_pcb drc.json NET[,NET...] (edits in place)
"""
import json
import re
import sys

import pcbnew

from cs_decoder_finish import tie_pad_to_ground

PAD_ITEM = re.compile(r'^Pad (\S+) \[(.*?)\] of (\S+) on')


def main():
    path, report_path, net_list = sys.argv[1:4]
    wanted = set(net_list.split(','))
    board = pcbnew.LoadBoard(path)
    pads = set()
    for entry in json.load(open(report_path))['unconnected_items']:
        for item in entry['items']:
            match = PAD_ITEM.match(item['description'])
            if match and match.group(2) in wanted:
                pads.add((match.group(3), match.group(1)))
    for ref, number in sorted(pads):
        try:
            tie_pad_to_ground(board, ref, number)
        except (StopIteration, RuntimeError) as error:
            print('not tied', ref, number, error)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
