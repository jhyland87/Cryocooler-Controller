"""3D envelope models for footprints whose KiCad library model file is missing.

KiCad ships footprints for a few of our parts (SG-8002CA oscillator, SRP7050TA
inductors, NANO2 fuse) without the STEP file they point at, and the MIE1W0505
footprint is our own, so they render as bare pads. These are plain box models
(VRML) sized from the part datasheets; they show where the part sits and how
tall it is, not its exact shape.
"""

from pathlib import Path

import pcbnew

from pcbnetlist import KICAD_DIR

MODEL_DIR = KICAD_DIR / 'lib' / 'cryocooler.3dshapes'
STOCK_MODELS = Path(
    '/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels'
)
# VRML units in KiCad are 2.54 mm; the files are written in mm and scaled
VRML_SCALE = 1 / 2.54

BLACK = (0.10, 0.10, 0.11)
GRAY = (0.22, 0.22, 0.24)
TAN = (0.82, 0.72, 0.50)
SILVER = (0.80, 0.80, 0.82)

# Housing colours for the connector models (STEP files from the KiCad library).
HOUSING_COLOURS = {
    'red': (0.80, 0.08, 0.08),
    'black': (0.08, 0.08, 0.09),
    'yellow': (0.95, 0.78, 0.10),
    'blue': (0.10, 0.30, 0.75),
    'orange': (0.95, 0.45, 0.05),
    'grey': (0.55, 0.56, 0.58),
    'white': (0.894, 0.890, 0.812),  # stock JST / Molex housing
}

# reference -> housing colour: terminal blocks black, Molex KK red / black,
# JST XH white
CONNECTOR_COLOURS = {
    'J2': 'black',
    'J8': 'black',
    'J9': 'black',
    'J11': 'black',
    'J12': 'black',
    'J3': 'black',  # fan / pump
    'J4': 'black',
    'J5': 'red',  # fan tach
    'J6': 'white',
    'J7': 'white',
    'J13': 'white',
    'J10': 'white',
    'J14': 'white',
}

# housing RGB in the stock STEP files: Phoenix terminal block (green), JST / Molex (cream)
STOCK_HOUSING_RGB = (
    '0.339999993741,0.679999990811,0.445000007484',
    '0.89411765337,0.890196084976,0.811764717102',
)

# footprint name -> (model name, [(size x, y, z mm, centre x, y mm, colour)])
# heights: SG-8002CA 1.4 mm (distributor data), SRP7050TA 5.0 mm max (Bourns, 4.8 +/- 0.2),
# NANO2 453 2.69 mm (Littelfuse); MIE1W0505 LGA-12 is 5 x 4 mm, height assumed
# 1.8 mm (not read from its datasheet).
ENVELOPES = {
    'Oscillator_SMD_SeikoEpson_SG8002CA-4Pin_7.0x5.0mm': (
        'SG8002CA_envelope',
        [(7.0, 5.0, 1.4, 0.0, 0.0, BLACK)],
    ),
    'L_Bourns_SRP7050TA': (
        'SRP7050TA_envelope',
        [(7.3, 6.6, 5.0, 0.0, 0.0, GRAY)],
    ),
    'Fuse_Littelfuse-NANO2-451_453': (
        'NANO2_453_envelope',
        [
            (4.3, 2.69, 2.69, 0.0, 0.0, TAN),
            (0.9, 2.69, 2.69, -2.6, 0.0, SILVER),
            (0.9, 2.69, 2.69, 2.6, 0.0, SILVER),
        ],
    ),
    'CONV_MIE1W0505BGLVH-3R-Z': (
        'MIE1W0505_envelope',
        [(5.0, 4.0, 1.8, 0.0, 0.0, BLACK)],
    ),
    # LT3097 22-lead DFN, 3 x 6 mm, 0.75 mm high (datasheet Fig. 132)
    'DFN-22-2EP_6x3mm_P0.5mm_LT3097': (
        'LT3097_envelope',
        [(3.0, 6.0, 0.75, 0.0, 0.0, BLACK)],
    ),
}


def write_model(name, boxes):
    """Writes the VRML file for one envelope and returns its path."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    lines = ['#VRML V2.0 utf8', f'# {name}: box envelope, units are mm']
    for size_x, size_y, size_z, center_x, center_y, colour in boxes:
        lines += [
            'Transform {',
            f'  translation {center_x} {center_y} {size_z / 2}',
            '  children Shape {',
            '    appearance Appearance { material Material {',
            f'      diffuseColor {colour[0]} {colour[1]} {colour[2]} }} }}',
            f'    geometry Box {{ size {size_x} {size_y} {size_z} }}',
            '  }',
            '}',
        ]
    path = MODEL_DIR / f'{name}.wrl'
    path.write_text('\n'.join(lines) + '\n')
    return path


def library_model_exists(model_path):
    """True if a footprint's 3D model file is present in the KiCad install."""
    prefix = '${KICAD10_3DMODEL_DIR}/'
    if not model_path.startswith(prefix):
        return Path(model_path).exists()
    return (STOCK_MODELS / model_path[len(prefix) :]).exists()


def attach_missing_models(footprint):
    """Gives a footprint an envelope model if it has none or its model file
    is missing; returns True if it did.
    """
    name = str(footprint.GetFPID().GetLibItemName())
    if name not in ENVELOPES:
        return False
    if any(library_model_exists(m.m_Filename) for m in footprint.Models()):
        return False
    model_name, boxes = ENVELOPES[name]
    path = write_model(model_name, boxes)
    while footprint.Models().size():
        footprint.Models().pop_back()
    model = pcbnew.FP_3DMODEL()
    model.m_Filename = f'${{KIPRJMOD}}/lib/cryocooler.3dshapes/{path.name}'
    model.m_Scale = pcbnew.VECTOR3D(VRML_SCALE, VRML_SCALE, VRML_SCALE)
    model.m_Show = True
    footprint.Models().push_back(model)
    return True


def colour_string(rgb):
    """RGB tuple as written inside a STEP COLOUR_RGB entry."""
    return ','.join(str(channel) for channel in rgb)


def apply_connector_colour(footprint):
    """Points a connector at a recoloured copy of its STEP model.

    Writes lib/cryocooler.3dshapes/<model>_<colour>.step with only the
    housing colour replaced (metal parts keep theirs) and repoints the
    footprint's existing 3D model at it, keeping its offset and rotation.
    Works from the stock model or from an earlier recoloured copy.

    Args:
        footprint: pcbnew footprint whose reference is in CONNECTOR_COLOURS.

    Returns:
        True if the model was repointed, False if the reference has no
        colour or no usable STEP model was found.
    """
    colour = CONNECTOR_COLOURS.get(footprint.GetReference())
    if colour is None:
        return False
    stock_prefix = '${KICAD10_3DMODEL_DIR}/'
    copy_prefix = '${KIPRJMOD}/lib/cryocooler.3dshapes/'
    known_rgb = STOCK_HOUSING_RGB + tuple(
        colour_string(rgb) for rgb in HOUSING_COLOURS.values()
    )
    for index in range(footprint.Models().size()):
        model = footprint.Models()[index]
        filename = model.m_Filename
        if filename.startswith(stock_prefix):
            source = STOCK_MODELS / filename[len(stock_prefix) :]
        elif filename.startswith(copy_prefix):
            source = MODEL_DIR / filename[len(copy_prefix) :]
        else:
            continue
        if source.suffix != '.step' or not source.exists():
            continue
        text = source.read_text()
        old_rgb = next((rgb for rgb in known_rgb if rgb in text), None)
        if old_rgb is None:
            continue
        stem = source.stem
        for name in HOUSING_COLOURS:
            stem = stem.removesuffix(f'_{name}')
        path = MODEL_DIR / f'{stem}_{colour}.step'
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text.replace(old_rgb, colour_string(HOUSING_COLOURS[colour]))
        )
        # the SWIG vector hands out copies, so rebuild the list with the edit
        kept = []
        for i in range(footprint.Models().size()):
            old = footprint.Models()[i]
            new = pcbnew.FP_3DMODEL()
            new.m_Filename = (
                f'{copy_prefix}{path.name}' if i == index else old.m_Filename
            )
            new.m_Scale = pcbnew.VECTOR3D(
                old.m_Scale.x, old.m_Scale.y, old.m_Scale.z
            )
            new.m_Rotation = pcbnew.VECTOR3D(
                old.m_Rotation.x, old.m_Rotation.y, old.m_Rotation.z
            )
            new.m_Offset = pcbnew.VECTOR3D(
                old.m_Offset.x, old.m_Offset.y, old.m_Offset.z
            )
            new.m_Opacity = old.m_Opacity
            new.m_Show = old.m_Show
            kept.append(new)
        while footprint.Models().size():
            footprint.Models().pop_back()
        for new in kept:
            footprint.Models().push_back(new)
        return True
    return False
