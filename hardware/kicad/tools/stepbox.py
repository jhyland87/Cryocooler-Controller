"""Writes coloured box solids as an AP214 STEP file (no CAD library needed).

Used for the envelope models in pcbmodels.py. Each box is an axis-aligned
B-rep solid with a surface colour; units are mm.
"""

from itertools import product


class StepWriter:
    """Collects STEP entities and numbers them in the order they are added."""

    def __init__(self):
        self.entities = []

    def add(self, text):
        """Adds one entity and returns its '#id' reference."""
        self.entities.append(text)
        return f'#{len(self.entities)}'

    def point(self, coords):
        return self.add(f"CARTESIAN_POINT('',({number(coords[0])},{number(coords[1])},{number(coords[2])}))")

    def direction(self, coords):
        return self.add(f"DIRECTION('',({number(coords[0])},{number(coords[1])},{number(coords[2])}))")

    def placement(self, origin, axis, ref_direction):
        return self.add(
            f"AXIS2_PLACEMENT_3D('',{self.point(origin)},{self.direction(axis)},"
            f'{self.direction(ref_direction)})'
        )


def number(value):
    """A STEP real: always has a decimal point."""
    text = repr(float(value)).upper()
    return text if 'E' in text or '.' in text else f'{text}.'


def subtract(first, second):
    return tuple(a - b for a, b in zip(first, second))


def cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def write_box_solid(writer, size, centre, colour):
    """Adds one box solid and its colour; returns (solid ref, styled item ref).

    Args:
        writer: StepWriter collecting the file's entities.
        size: (x, y, z) edge lengths in mm.
        centre: (x, y, z) centre of the box in mm.
        colour: (r, g, b) in 0..1.
    """
    low = tuple(c - s / 2 for c, s in zip(centre, size))
    high = tuple(c + s / 2 for c, s in zip(centre, size))
    corners = {
        bits: tuple(high[axis] if bits[axis] else low[axis] for axis in range(3))
        for bits in product((0, 1), repeat=3)
    }
    vertices = {
        bits: writer.add(f'VERTEX_POINT(\'\',{writer.point(corner)})')
        for bits, corner in corners.items()
    }
    edges = {}

    def oriented_edge(start, end):
        key = tuple(sorted((start, end)))
        if key not in edges:
            first, second = (corners[key[0]], corners[key[1]])
            offset = subtract(second, first)
            length = max(abs(component) for component in offset)
            unit = tuple(component / length for component in offset)
            vector = writer.add(f"VECTOR('',{writer.direction(unit)},{number(length)})")
            line = writer.add(f"LINE('',{writer.point(first)},{vector})")
            edges[key] = writer.add(
                f"EDGE_CURVE('',{vertices[key[0]]},{vertices[key[1]]},{line},.T.)"
            )
        sense = '.T.' if (start, end) == key else '.F.'
        return writer.add(f"ORIENTED_EDGE('',*,*,{edges[key]},{sense})")

    faces = []
    for axis in range(3):
        for side in (0, 1):
            normal = tuple(
                (1.0 if side else -1.0) if index == axis else 0.0 for index in range(3)
            )
            others = [index for index in range(3) if index != axis]
            loop = []
            for first_bit, second_bit in ((0, 0), (1, 0), (1, 1), (0, 1)):
                bits = [0, 0, 0]
                bits[axis] = side
                bits[others[0]] = first_bit
                bits[others[1]] = second_bit
                loop.append(tuple(bits))
            # outward normal needs a counter-clockwise loop seen from outside
            turn = cross(
                subtract(corners[loop[1]], corners[loop[0]]),
                subtract(corners[loop[2]], corners[loop[1]]),
            )
            if dot(turn, normal) < 0:
                loop.reverse()
            loop_edges = [
                oriented_edge(loop[index], loop[(index + 1) % 4]) for index in range(4)
            ]
            edge_loop = writer.add(f"EDGE_LOOP('',({','.join(loop_edges)}))")
            bound = writer.add(f"FACE_OUTER_BOUND('',{edge_loop},.T.)")
            ref_direction = tuple(1.0 if index == others[0] else 0.0 for index in range(3))
            plane = writer.add(
                f"PLANE('',{writer.placement(corners[loop[0]], normal, ref_direction)})"
            )
            faces.append(writer.add(f"ADVANCED_FACE('',({bound}),{plane},.T.)"))
    shell = writer.add(f"CLOSED_SHELL('',({','.join(faces)}))")
    solid = writer.add(f"MANIFOLD_SOLID_BREP('',{shell})")
    rgb = writer.add(f"COLOUR_RGB('',{number(colour[0])},{number(colour[1])},{number(colour[2])})")
    fill_colour = writer.add(f"FILL_AREA_STYLE_COLOUR('',{rgb})")
    fill_style = writer.add(f"FILL_AREA_STYLE('',({fill_colour}))")
    fill_area = writer.add(f'SURFACE_STYLE_FILL_AREA({fill_style})')
    side_style = writer.add(f"SURFACE_SIDE_STYLE('',({fill_area}))")
    usage = writer.add(f'SURFACE_STYLE_USAGE(.BOTH.,{side_style})')
    assignment = writer.add(f'PRESENTATION_STYLE_ASSIGNMENT(({usage}))')
    styled = writer.add(f"STYLED_ITEM('color',({assignment}),{solid})")
    return solid, styled


def box_step_text(name, boxes):
    """Builds a STEP file holding coloured boxes.

    Args:
        name: product name written into the file.
        boxes: [(size (x, y, z), centre (x, y, z), colour (r, g, b))] in mm.

    Returns:
        The STEP file contents as a string.
    """
    writer = StepWriter()
    app_context = writer.add(
        "APPLICATION_CONTEXT('core data for automotive mechanical design processes')"
    )
    writer.add(
        "APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',"
        f'2000,{app_context})'
    )
    product_context = writer.add(f"PRODUCT_CONTEXT('',{app_context},'mechanical')")
    product_entity = writer.add(f"PRODUCT('{name}','{name}','',({product_context}))")
    formation = writer.add(f"PRODUCT_DEFINITION_FORMATION('','',{product_entity})")
    definition_context = writer.add(
        f"PRODUCT_DEFINITION_CONTEXT('part definition',{app_context},'design')"
    )
    definition = writer.add(
        f"PRODUCT_DEFINITION('design','',{formation},{definition_context})"
    )
    definition_shape = writer.add(f"PRODUCT_DEFINITION_SHAPE('','',{definition})")
    length_unit = writer.add('( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )')
    angle_unit = writer.add('( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )')
    solid_angle_unit = writer.add('( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )')
    uncertainty = writer.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),{length_unit},"
        "'distance_accuracy_value','confusion accuracy')"
    )
    context = writer.add(
        '( GEOMETRIC_REPRESENTATION_CONTEXT(3) '
        f'GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT(({uncertainty})) '
        f'GLOBAL_UNIT_ASSIGNED_CONTEXT(({length_unit},{angle_unit},{solid_angle_unit})) '
        "REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )"
    )
    origin = writer.placement((0, 0, 0), (0, 0, 1), (1, 0, 0))
    solids = []
    styled_items = []
    for size, centre, colour in boxes:
        solid, styled = write_box_solid(writer, size, centre, colour)
        solids.append(solid)
        styled_items.append(styled)
    shape = writer.add(
        f"ADVANCED_BREP_SHAPE_REPRESENTATION('{name}',({','.join([origin] + solids)}),{context})"
    )
    writer.add(f'SHAPE_DEFINITION_REPRESENTATION({definition_shape},{shape})')
    writer.add(
        "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',"
        f"({','.join(styled_items)}),{context})"
    )
    header = [
        'ISO-10303-21;',
        'HEADER;',
        "FILE_DESCRIPTION(('box envelope model'),'2;1');",
        f"FILE_NAME('{name}.step','',(''),(''),'stepbox.py','','');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        'ENDSEC;',
        'DATA;',
    ]
    body = [f'#{index}={entity};' for index, entity in enumerate(writer.entities, start=1)]
    return '\n'.join(header + body + ['ENDSEC;', 'END-ISO-10303-21;', ''])
