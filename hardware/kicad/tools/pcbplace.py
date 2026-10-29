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


def placed_rect(local_rect, center_x, center_y, angle_degrees):
    """Bounding rect of a footprint-local rect after rotation/translation."""
    corners = [
        rotate_point(x, y, angle_degrees)
        for x in (local_rect.min_x, local_rect.max_x)
        for y in (local_rect.min_y, local_rect.max_y)
    ]
    return Rect(
        center_x + min(c[0] for c in corners),
        center_y + min(c[1] for c in corners),
        center_x + max(c[0] for c in corners),
        center_y + max(c[1] for c in corners),
    )


class RectIndex(dict):
    """name -> Rect dict with a coarse grid index, so collision checks only
    look at the rectangles near a spot.
    """

    CELL = 4.0

    def __init__(self):
        super().__init__()
        self.grid = {}

    def _cells(self, rect):
        for cell_x in range(
            math.floor(rect.min_x / self.CELL), math.floor(rect.max_x / self.CELL) + 1
        ):
            for cell_y in range(
                math.floor(rect.min_y / self.CELL),
                math.floor(rect.max_y / self.CELL) + 1,
            ):
                yield cell_x, cell_y

    def __setitem__(self, name, rect):
        if name in self:
            del self[name]
        super().__setitem__(name, rect)
        for cell in self._cells(rect):
            self.grid.setdefault(cell, set()).add(name)

    def __delitem__(self, name):
        for cell in self._cells(self[name]):
            self.grid[cell].discard(name)
        super().__delitem__(name)

    def pop(self, name, *default):
        if name not in self:
            if default:
                return default[0]
            raise KeyError(name)
        rect = self[name]
        del self[name]
        return rect

    def near(self, rect):
        """Names of the rectangles that may overlap rect."""
        names = set()
        for cell in self._cells(rect):
            names |= self.grid.get(cell, set())
        return names


class Occupancy:
    """Tracks placed rectangles and keep-out areas inside the board outline."""

    def __init__(self, board_rect, edge_margin, gap):
        self.board_rect = board_rect.inflated(-edge_margin)
        self.gap = gap
        self.rects = RectIndex()
        self.keepouts = []

    def add(self, name, rect):
        self.rects[name] = rect

    def is_free(self, rect, ignore=()):
        if not rect.inside(self.board_rect):
            return False
        if any(rect.overlaps(keepout) for keepout in self.keepouts):
            return False
        padded = rect.inflated(self.gap / 2)
        return not any(
            padded.overlaps(self.rects[name].inflated(self.gap / 2))
            for name in self.rects.near(rect.inflated(self.gap))
            if name not in ignore
        )

    def overlaps_report(self):
        names = list(self.rects)
        pairs = []
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
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
