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
    'J10': 'white',
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
    # Adafruit 1769 (4UCON 17311): body 7.9 x 6.0 mm, 5.5 mm high, mating
    # face at footprint y 4.4 (model y is footprint -y)
    'Adafruit_1769_JST-PH_1x02_P2.00mm_Horizontal_SMD': (
        'Adafruit_1769_envelope',
        [(7.9, 6.0, 5.5, 0.0, -1.4, BLACK)],
    ),
    # Adafruit_CAD_Parts' '4392 STEMMA QT Horizontal' is a 1 mm JST SH, so it can't be used.
    # Adafruit 4392 (CW2001-04T): body 12.0 x 6.0 mm, 5.5 mm high, mating
    # face at footprint y 4.6
    'Adafruit_4392_JST-PH_1x04_P2.00mm_Horizontal_SMD': (
        'Adafruit_4392_envelope',
        [(12.0, 6.0, 5.5, 0.0, -1.6, BLACK)],
    ),
    # Coilcraft MSD7342: 7.5 x 7.5 mm, 4.6 mm max (Document 621-1)
    'L_Coilcraft_MSD7342': (
        'MSD7342_envelope',
        [(7.5, 7.5, 4.6, 0.0, 0.0, GRAY)],
    ),
    # Sullins SWR25X S02 RB (catalog): body and locking plate, pins left out
    'Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal': (
        'Sullins_SWR25X_S02_RB_envelope',
        [
            (5.12, 3.2, 5.8, 1.27, -3.5, TAN),
            (3.14, 8.2, 0.5, 1.27, -9.2, TAN),
        ],
    ),
    # Wurth 61900311021 (datasheet): body and locking plate, pins left out
    'Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal': (
        'Wurth_61900311021_envelope',
        [
            (7.62, 3.3, 5.8, 2.54, -3.34, TAN),
            (5.68, 8.2, 0.5, 2.54, -9.09, TAN),
        ],
    ),
    # fan_header_90deg.step envelope: housing and key tab (pins left out).
    # Fallback for LOCAL_STEP_MODELS.
    'FanHeader_4P_P2.54mm_Horizontal': (
        'FanHeader_4P_envelope',
        [
            (10.81, 5.29, 6.35, 3.81, -4.448, BLACK),
            (7.62, 6.25, 1.59, 3.79, -10.22, BLACK),
        ],
    ),
    # Fallbacks for LOCAL_STEP_MODELS, sized from the maker drawings
    'Tensility_54-00164_5.5x2.1mm_Horizontal_SMD': (
        'Tensility_54-00164_envelope',
        [(9.0, 14.7, 11.0, 0.0, 7.35, BLACK)],
    ),
    'SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD': (
        'SameSky_MJ-3523_envelope',
        [(6.0, 14.5, 5.0, 0.0, 9.75, BLACK), (5.0, 2.5, 5.0, 0.0, 1.25, BLACK)],
    ),
    # TE 2305908 fallback (drawing C-2305908 rev A1): body 9.8 deep, 8.9
    # high, 3.5 past each end pin; tails on the pads
    'TE_2305908-2_1x02_P5.00mm_Horizontal_SMD': (
        'TE_2305908-2_envelope',
        [(12.0, 9.8, 8.9, 2.5, -6.85, BLACK),
         (1.0, 4.2, 0.4, 0.0, 0.15, SILVER), (1.0, 4.2, 0.4, 5.0, 0.15, SILVER)],
    ),
    'TE_2305908-3_1x03_P5.00mm_Horizontal_SMD': (
        'TE_2305908-3_envelope',
        [(17.0, 9.8, 8.9, 5.0, -6.85, BLACK),
         (1.0, 4.2, 0.4, 0.0, 0.15, SILVER), (1.0, 4.2, 0.4, 5.0, 0.15, SILVER),
         (1.0, 4.2, 0.4, 10.0, 0.15, SILVER)],
    ),
    # Phoenix 1821698 fallback (drawing 00783144 rev 02)
    'PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal': (
        'MC05_2_SMD_envelope',
        [(9.66, 4.0, 4.85, 1.27, 1.2, BLACK), (5.58, 3.1, 4.85, 1.27, -4.8, BLACK)],
    ),
    # Amphenol RJSSE-5380 (drawing P-RJSSE-5380 rev E): shield 16.51 wide,
    # 13.58 high, 15.75 deep; mouth 4.37 in front of the hole line, so the
    # body spans footprint y -11.38 .. 4.37. Fallback for LOCAL_STEP_MODELS.
    'RJ45_Amphenol_RJSSE-5380_Horizontal': (
        'RJSSE5380_envelope',
        [(16.51, 15.75, 13.58, 0.0, 3.505, SILVER)],
    ),
}

# footprint name -> (STEP file in MODEL_DIR, offset mm, rotation deg). These
# vendor models are licensed for design use only, so they are gitignored and
# used when present; without the file the footprint gets its envelope.
# RJSSE5380.step (Amphenol M-RJSSE-5380, via SnapMagic) is Y-up with the
# pegs at x 1.52 / 14.22, z -4.13 and the contact feet at y -0.76.
LOCAL_STEP_MODELS = {
    # fan_header_90deg.step (GrabCAD) has its board plane at z 3.175, tails
    # towards +z at y -3.655 and pin 1 at x -3.81
    'FanHeader_4P_P2.54mm_Horizontal': (
        'fan_header_90deg.step',
        (3.81, -3.655, 3.175),
        (180.0, 0.0, 0.0),
    ),
    # SWR25X-NRTC-S02-RB-BA.step (the user's own model) is Y-up: board plane at y 0,
    # pins at z -1.9 and x -1.27 / 1.27
    'Sullins_SWR25X-NRTC-S02-RB-BA_1x02_P2.54mm_Horizontal': (
        'SWR25X-NRTC-S02-RB-BA.step',
        (1.27, -1.9, 0.0),
        (-90.0, 0.0, 0.0),
    ),
    # SWR25X-NRTC-S03-RB-BA.step (the user's own model of the Sullins part, on J5's
    # Wurth footprint) is Y-up: board plane at y 0, pins at z -1.9, pin 2 at x 0
    'Wurth_WR-WTB_61900311021_1x03_P2.54mm_Horizontal': (
        'SWR25X-NRTC-S03-RB-BA.step',
        (2.54, -1.9, 0.0),
        (-90.0, 0.0, 0.0),
    ),
    # 54-00164.step (Tensility) is Y-up: mouth at z 21.217, body underside at
    # y 4.887, jack axis at x -9.717
    'Tensility_54-00164_5.5x2.1mm_Horizontal_SMD': (
        '54-00164.step',
        (9.717, 21.217, -4.887),
        (-90.0, 0.0, 0.0),
    ),
    # MJ-3523-SMT-TR.step (Same Sky) is Y-up: nose towards +z, shoulder at z 0,
    # body underside at y -2.5
    'SameSky_MJ-3523-SMT-TR_3.5mm_Horizontal_SMD': (
        'MJ-3523-SMT-TR.step',
        (0.0, 2.5, 2.5),
        (-90.0, 0.0, 0.0),
    ),
    # TE STEPs (C-2305908-2 / -3): pins centred on x, tail bottoms at y -4.975,
    # mating face at z 0, 11.75 mm in front of the pads
    'TE_2305908-2_1x02_P5.00mm_Horizontal_SMD': (
        '2305908-2.step',
        (2.5, -11.75, 4.975),
        (-90.0, 0.0, 0.0),
    ),
    'TE_2305908-3_1x03_P5.00mm_Horizontal_SMD': (
        '2305908-3.step',
        (5.0, -11.75, 4.975),
        (-90.0, 0.0, 0.0),
    ),
    # 1821698.step (Phoenix, via TraceParts) has z up, board plane at z 0, mating
    # face at y 0, pins at x 1.52 / 4.06 and y 6.35
    'PhoenixContact_MC_0,5_2-G-2,54_SMD_1x02_P2.54mm_Horizontal': (
        '1821698.step',
        (-1.52, -6.35, 0.0),
        (0.0, 0.0, 0.0),
    ),
    'RJ45_Amphenol_RJSSE-5380_Horizontal': (
        'RJSSE5380.step',
        (-7.874, -4.13, 0.762),
        (-90.0, 0.0, 0.0),
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
    """True if a footprint's 3D model file is present in the KiCad install
    or the project library."""
    for prefix, root in (('${KICAD10_3DMODEL_DIR}/', STOCK_MODELS), ('${KIPRJMOD}/', KICAD_DIR)):
        if model_path.startswith(prefix):
            return (root / model_path[len(prefix) :]).exists()
    return Path(model_path).exists()


def attach_missing_models(footprint):
    """Gives a footprint its local vendor STEP (LOCAL_STEP_MODELS) when the
    file is present, otherwise an envelope model if it has none or its model
    file is missing; returns True if it changed the model.
    """
    name = str(footprint.GetFPID().GetLibItemName())
    local_step = LOCAL_STEP_MODELS.get(name)
    if local_step is not None and (MODEL_DIR / local_step[0]).exists():
        wanted = f'${{KIPRJMOD}}/lib/cryocooler.3dshapes/{local_step[0]}'
        if [m.m_Filename for m in footprint.Models()] == [wanted]:
            return False
        model = pcbnew.FP_3DMODEL()
        model.m_Filename = wanted
        model.m_Offset = pcbnew.VECTOR3D(*local_step[1])
        model.m_Rotation = pcbnew.VECTOR3D(*local_step[2])
    else:
        if name not in ENVELOPES:
            return False
        if any(library_model_exists(m.m_Filename) for m in footprint.Models()):
            return False
        path = write_model(*ENVELOPES[name])
        model = pcbnew.FP_3DMODEL()
        model.m_Filename = f'${{KIPRJMOD}}/lib/cryocooler.3dshapes/{path.name}'
        model.m_Scale = pcbnew.VECTOR3D(VRML_SCALE, VRML_SCALE, VRML_SCALE)
    while footprint.Models().size():
        footprint.Models().pop_back()
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
