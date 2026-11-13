"""US 3-section 300 mm (12 in) vehicle signal heads with visors and backplates.

Orientation convention: a head is built with its lenses facing local -Y, then rotated so the
lenses face the drivers it controls (i.e. AGAINST their direction of travel).
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix
from .util import box, cylinder, flat_mat, bm_to_object

# Which way the lenses face, per approach (drivers' travel direction is the opposite).
FACING_ROT_Z = {
    'NB': 0.0,              # northbound drivers look north -> lenses face south (-Y), i.e. towards the camera
    'SB': math.pi,          # southbound drivers look south -> lenses face north (+Y)
    'EB': -math.pi / 2,     # eastbound drivers look east  -> lenses face west (-X)
    'WB': math.pi / 2,      # westbound drivers look west  -> lenses face east (+X)
}
COLOURS = {'red': (1.0, 0.03, 0.01), 'amber': (1.0, 0.35, 0.0), 'green': (0.05, 1.0, 0.45)}


def lens_material(approach, colour):
    """One material per approach+section so render-time animation can switch it."""
    name = f'SigLens_{approach}_{colour}'
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    c = COLOURS[colour]
    b.inputs['Base Color'].default_value = (c[0] * 0.15, c[1] * 0.15, c[2] * 0.15, 1)
    b.inputs['Roughness'].default_value = 0.15
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Emission Color'].default_value = (*c, 1)
    b.inputs['Emission Strength'].default_value = 0.0
    m['approach'] = approach
    m['colour'] = colour
    return m


def build_head(name, col, approach, loc, housing_mat, backplate_mat):
    """loc = (x, y, z_bottom). Returns the parent empty."""
    parent = bpy.data.objects.new(name, None)
    parent.empty_display_size = 0.5
    col.objects.link(parent)
    parts = []
    W, D, H = 0.36, 0.26, 1.07
    parts.append(box(name + '_housing', col, (W, D, H), (0, 0, 0), housing_mat))
    # backplate (behind the housing, slightly larger, thin)
    parts.append(box(name + '_backplate', col, (0.66, 0.025, 1.38), (0, D / 2 + 0.02, -0.155),
                     backplate_mat))
    for i, colour in enumerate(('green', 'amber', 'red')):   # bottom -> top
        z = 0.18 + i * 0.355
        lens = cylinder(name + f'_lens_{colour}', col, 0.15, 0.02, (0, -D / 2, z),
                        lens_material(approach, colour), 24, rot=(math.pi / 2, 0, 0))
        parts.append(lens)
        # tunnel visor: open tube, top 3/4, protruding 0.24 m
        bm = bmesh.new()
        segs = 18
        r = 0.165
        rings = []
        for yy in (0.0, 0.24):
            ring = []
            for k in range(segs + 1):
                a = math.radians(-45) + math.radians(270) * k / segs   # open at the bottom
                ring.append(bm.verts.new((r * math.cos(a), -yy, r * math.sin(a))))
            rings.append(ring)
        for k in range(segs):
            bm.faces.new((rings[0][k], rings[0][k + 1], rings[1][k + 1], rings[1][k]))
        bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.004)
        v = bm_to_object(bm, name + f'_visor_{colour}', col, housing_mat)
        v.location = (0, -D / 2 - 0.005, z)
        parts.append(v)
    for p in parts:
        p.parent = parent
    parent.location = loc
    parent.rotation_euler.z = FACING_ROT_Z[approach]
    # Hanger to the mast arm
    return parent


SIGNAL_NITS = 9000.0       # LED signal lens luminance (cd/m2)


def _strength(colour, lit):
    return SIGNAL_NITS / 683.0 if colour == lit else 0.0


def set_state(approach, lit):
    """lit: 'red' | 'amber' | 'green' | None. Used for static test renders."""
    for colour in COLOURS:
        m = bpy.data.materials.get(f'SigLens_{approach}_{colour}')
        if m:
            m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = \
                _strength(colour, lit)


def animate_cycle():
    """Keyframe every signal lens on the shared clock (constant interpolation: LED heads switch
    instantly). See config.SIG_* for the phase plan."""
    from . import config as C
    plan = {
        'EB': [(C.FRAME_START, 'green'), (C.t2f(C.SIG_CROSS_AMBER_T), 'amber'), (C.t2f(C.SIG_CROSS_RED_T), 'red')],
        'NB': [(C.FRAME_START, 'red'), (C.t2f(C.SIG_AVE_GREEN_T), 'green')],
    }
    plan['WB'] = plan['EB']
    plan['SB'] = plan['NB']
    for ap, steps in plan.items():
        for colour in COLOURS:
            m = bpy.data.materials.get(f'SigLens_{ap}_{colour}')
            if not m:
                continue
            sock = m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
            for f, lit in steps:
                sock.default_value = _strength(colour, lit)
                sock.keyframe_insert('default_value', frame=f)
            for fc in m.node_tree.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


def state_at(approach, frame):
    from . import config as C
    if approach in ('EB', 'WB'):
        if frame < C.t2f(C.SIG_CROSS_AMBER_T):
            return 'green'
        return 'amber' if frame < C.t2f(C.SIG_CROSS_RED_T) else 'red'
    return 'red' if frame < C.t2f(C.SIG_AVE_GREEN_T) else 'green'
