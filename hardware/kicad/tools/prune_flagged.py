"""Deletes the tracks and vias a DRC report flags as dangling. A stub several segments long
needs several rounds of DRC and this script.

Usage: prune_flagged.py board.kicad_pcb drc.json (edits in place; prints what went)
"""
import json
import sys

import pcbnew

KEEP = []


def main():
    path, report_path = sys.argv[1:3]
    report = json.load(open(report_path))
    flagged = {
        item['uuid']
        for violation in report['violations']
        if violation['type'] in ('track_dangling', 'via_dangling')
        for item in violation['items']
    }
    board = pcbnew.LoadBoard(path)
    removed = 0
    for item in list(board.GetTracks()):
        if item.m_Uuid.AsString() in flagged:
            KEEP.append(item)
            board.Remove(item)
            removed += 1
    board.Save(path)
    print('removed', removed)


if __name__ == '__main__':
    main()
