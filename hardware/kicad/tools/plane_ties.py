"""Ties pads a DRC report lists as unconnected to the GND or +3V3 plane, with a short stub
to the nearest via of that net or to a new via beside the pad.

Vias and stubs stay out of rule areas (the ISO moat, antenna keep-outs) and 0.6 mm off the
board edge.

Usage: plane_ties.py board.kicad_pcb drc.json NET[,NET...] (edits in place)
"""
import json
import re
import sys

import pcbnew

import cs_decoder_finish as ties

PAD_ITEM = re.compile(r'^Pad (\S+) \[(.*?)\] of (\S+) on')


def keep_out(board):
    """Makes the tie helpers refuse spots inside a rule area or near the board edge."""
    areas = [zone.Outline() for zone in board.Zones() if zone.GetIsRuleArea()]
    box = board.GetBoardEdgesBoundingBox()
    edge = pcbnew.FromMM(0.6)

    def allowed(point):
        if not (box.GetLeft() + edge <= point.x <= box.GetRight() - edge
                and box.GetTop() + edge <= point.y <= box.GetBottom() - edge):
            return False
        return not any(area.Contains(point, -1, pcbnew.FromMM(0.4)) for area in areas)

    via_clear, path_clear = ties.via_clear, ties.path_clear
    ties.via_clear = lambda copper, position: allowed(position) and via_clear(copper, position)
    ties.path_clear = lambda copper, points, layer: all(map(allowed, points)) and path_clear(copper, points, layer)


def main():
    path, report_path, net_list = sys.argv[1:4]
    wanted = set(net_list.split(','))
    board = pcbnew.LoadBoard(path)
    keep_out(board)
    pads = set()
    for entry in json.load(open(report_path))['unconnected_items']:
        for item in entry['items']:
            match = PAD_ITEM.match(item['description'])
            if match and match.group(2) in wanted:
                pads.add((match.group(3), match.group(1)))
    for ref, number in sorted(pads):
        try:
            ties.tie_pad_to_ground(board, ref, number)
        except (StopIteration, RuntimeError) as error:
            print('not tied', ref, number, error)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)


if __name__ == '__main__':
    main()
