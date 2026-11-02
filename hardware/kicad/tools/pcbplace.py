"""Placement helpers for gen_pcb.py: rotated rectangles, collision checks and
the passive placer.

All lengths are millimetres, y grows downwards (KiCad board coordinates).
Angles are KiCad orientation degrees (positive = counter-clockwise on screen).
"""

import math
from dataclasses import dataclass


def rotate_point(point_x, point_y, angle_degrees):
    """Rotates a footprint-local point to board orientation (KiCad: CCW
    positive, y down).
    """
    radians = math.radians(angle_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    return (
        point_x * cosine + point_y * sine,
        -point_x * sine + point_y * cosine,
    )


@dataclass
class Rect:
    """Axis-aligned rectangle (min/max corners)."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def inflated(self, margin):
        return Rect(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def overlaps(self, other):
        return (
            self.min_x < other.max_x
            and other.min_x < self.max_x
            and self.min_y < other.max_y
            and other.min_y < self.max_y
        )

    def inside(self, outer):
        return (
            self.min_x >= outer.min_x
            and self.min_y >= outer.min_y
            and self.max_x <= outer.max_x
            and self.max_y <= outer.max_y
        )


def placed_rect(local_rect, center_x, center_y, angle_degrees, bottom=False):
    """Bounding rect of a footprint-local rect after rotation/translation;
    a bottom-side part is mirrored in y first (KiCad's left-right flip).
    """
    corners = [
        rotate_point(x, -y if bottom else y, angle_degrees)
        for x in (local_rect.min_x, local_rect.max_x)
        for y in (local_rect.min_y, local_rect.max_y)
    ]
    return Rect(
        center_x + min(c[0] for c in corners),
        center_y + min(c[1] for c in corners),
        center_x + max(c[0] for c in corners),
        center_y + max(c[1] for c in corners),
    )


class Occupancy:
    """Tracks placed rectangles and keep-out areas inside the board outline.

    Every rectangle belongs to a side: 'top', 'bottom' or 'both' (through-hole
    parts, holes). New rectangles take the current `side`; collision checks
    only see rectangles on the same side or on both.
    """

    def __init__(self, board_rect, edge_margin, gap):
        self.board_rect = board_rect.inflated(-edge_margin)
        self.gap = gap
        self.rects = {}
        self.sides = {}
        self.keepouts = []
        self.side = 'top'

    def add(self, name, rect, side=None):
        self.rects[name] = rect
        self.sides[name] = side or self.side

    def shares_side(self, name, side=None):
        """True if the named rectangle blocks parts on `side`."""
        side = side or self.side
        other = self.sides.get(name, 'both')
        return 'both' in (side, other) or other == side

    def on_side(self, side=None):
        """(name, rect) pairs that block parts on `side`."""
        return [
            (name, rect)
            for name, rect in self.rects.items()
            if self.shares_side(name, side)
        ]

    def is_free(self, rect, ignore=()):
        if not rect.inside(self.board_rect):
            return False
        if any(rect.overlaps(keepout) for keepout in self.keepouts):
            return False
        padded = rect.inflated(self.gap / 2)
        return not any(
            padded.overlaps(other.inflated(self.gap / 2))
            for name, other in self.on_side()
            if name not in ignore
        )

    def overlaps_report(self):
        names = list(self.rects)
        pairs = []
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                if not self.shares_side(first, self.sides.get(second, 'both')):
                    continue
                if self.rects[first].overlaps(self.rects[second]):
                    pairs.append((first, second))
        return pairs


def ring_offsets(max_radius, step):
    """Grid offsets sorted by distance from the origin (spiral order)."""
    count = int(max_radius / step)
    offsets = [
        (ix * step, iy * step)
        for ix in range(-count, count + 1)
        for iy in range(-count, count + 1)
    ]
    offsets.sort(key=lambda offset: offset[0] ** 2 + offset[1] ** 2)
    return offsets
