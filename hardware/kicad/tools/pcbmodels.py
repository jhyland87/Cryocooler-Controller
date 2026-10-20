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
