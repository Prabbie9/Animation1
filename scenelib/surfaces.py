"""Ground surfaces: asphalt, sidewalk, kerbs, road paint, plus road-repair geometry.

Physical basis for the wet look
  * a continuous water film makes asphalt nearly specular (roughness ~0.05-0.15 where it is
    thin; ~0.01 in standing water) and darkens it (light trapped by total internal reflection)
  * roads are crowned (~2 % cross-fall), so water collects along the kerbs, but kerb-side water
    is broken up by leaves, grit and the uneven gutter line; shallow depressions in the wheel
    paths (rutting) hold puddles
  * wheel paths are polished by tyres (darker, smoother aggregate); lane centres collect oil
    drips, densest where cars idle at the stop lines; wet oil shows a faint thin-film sheen
  * Fresnel is handled by the BSDF (IOR 1.33 water coat), so grazing reflections are strong
Everything is in object space (metres), so no UVs are needed and the scale is real.
"""
import math
import random
import bpy
import bmesh
from . import config as C
from . import materials as M
from .util import collection, mesh_object


class G:
    """Tiny helper for building node graphs."""

    def __init__(self, m):
        self.n, self.l = m.node_tree.nodes, m.node_tree.links

    def math(self, op, a, b=None, c=None, clamp=False):
        x = self.n.new('ShaderNodeMath'); x.operation = op; x.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                self.l.new(v, x.inputs[i])
        return x.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0, smooth=False):
        x = self.n.new('ShaderNodeMapRange')
        if smooth:
            x.interpolation_type = 'SMOOTHSTEP'
        x.inputs['From Min'].default_value = a; x.inputs['From Max'].default_value = b
        x.inputs['To Min'].default_value = c; x.inputs['To Max'].default_value = d
        self.l.new(v, x.inputs['Value'])
        return x.outputs['Result']

    def noise(self, vec, scale, detail=4.0, rough=0.55, dims=None):
        x = self.n.new('ShaderNodeTexNoise')
        x.inputs['Scale'].default_value = scale
        x.inputs['Detail'].default_value = detail
        x.inputs['Roughness'].default_value = rough
        self.l.new(vec, x.inputs['Vector'])
        return x.outputs['Fac']

    def vscale(self, vec, s):
        x = self.n.new('ShaderNodeVectorMath'); x.operation = 'MULTIPLY'
        x.inputs[1].default_value = s
        self.l.new(vec, x.inputs[0])
        return x.outputs[0]

    def mixc(self, f, a, b, blend='MIX'):
        x = self.n.new('ShaderNodeMix'); x.data_type = 'RGBA'; x.blend_type = blend
        for sock, v in (('Factor', f), ('A', a), ('B', b)):
            if isinstance(v, (tuple, list)):
                x.inputs[sock].default_value = (*v, 1) if len(v) == 3 else v
            elif isinstance(v, (int, float)):
                x.inputs[sock].default_value = v
            else:
                self.l.new(v, x.inputs[sock])
        return x.outputs['Result']

    def mixf(self, f, a, b):
        x = self.n.new('ShaderNodeMix'); x.data_type = 'FLOAT'
        for sock, v in (('Factor', f), ('A', a), ('B', b)):
            if isinstance(v, (int, float)):
                x.inputs[sock].default_value = v
            else:
                self.l.new(v, x.inputs[sock])
        return x.outputs['Result']


def _upstream(m, sock_name):
    b = m.node_tree.nodes['Principled BSDF']
    return next(lk.from_socket for lk in m.node_tree.links if lk.to_node == b and lk.to_socket.name == sock_name)


def lane_bands(g, coord, lane=C.LANE, path_off=0.85):
    """Given a coordinate across the lanes (x for the avenue), return (wheel_path, lane_centre)
    masks 0..1. Lanes are 3.3 m wide with boundaries at multiples of 3.3 m from the centre line."""
    u = g.math('DIVIDE', coord, lane)
    f = g.math('SUBTRACT', g.math('FRACT', u), 0.5)              # -0.5..0.5 across a lane
    a = g.math('ABSOLUTE', f)
    dpath = g.math('MULTIPLY', g.math('ABSOLUTE', g.math('SUBTRACT', a, path_off / lane)), lane)
    wheel = g.maprange(dpath, 0.12, 0.42, 1.0, 0.0, smooth=True)
    centre = g.maprange(g.math('MULTIPLY', a, lane), 0.08, 0.4, 1.0, 0.0, smooth=True)
    return wheel, centre


def asphalt():
    m = M.pbr('Asphalt_wet', 'asphalt_02', 3.5, tint=(0.9, 0.9, 0.9), normal_strength=0.6)
    g = G(m)
    n, l = g.n, g.l
    b = n['Principled BSDF']
    wet_grp = next(x for x in n if x.type == 'GROUP')
    tc = n.new('ShaderNodeTexCoord')
    obj = tc.outputs['Object']
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(obj, sep.inputs['Vector'])
    X, Y = sep.outputs['X'], sep.outputs['Y']
    ax, ay = g.math('ABSOLUTE', X), g.math('ABSOLUTE', Y)

    # --- anti-tiling: second lookup of the diffuse at a different scale/rotation -------------
    dif_tex = next(x for x in n if x.type == 'TEX_IMAGE' and x.image.colorspace_settings.name == 'sRGB')
    mp2 = n.new('ShaderNodeMapping')
    mp2.inputs['Scale'].default_value = (1 / 4.7,) * 3
    mp2.inputs['Rotation'].default_value = (0, 0, 0.9)
    l.new(obj, mp2.inputs['Vector'])
    dif2 = n.new('ShaderNodeTexImage'); dif2.image = dif_tex.image; dif2.projection = 'BOX'
    l.new(mp2.outputs['Vector'], dif2.inputs['Vector'])
    macro = g.noise(obj, 0.06, 3.0)
    base_in = wet_grp.inputs['Color'].links[0].from_socket
    blend = g.mixc(g.maprange(macro, 0.4, 0.6), base_in, dif2.outputs['Color'])
    # large-scale tonal variation (resurfacing age, sun-bleaching): +-12 %
    tone = g.maprange(g.noise(obj, 0.025, 2.0), 0.3, 0.7, 0.88, 1.12)
    col = g.mixc(1.0, blend, g.mixc(1.0, (1, 1, 1), tone, 'MULTIPLY'), 'MULTIPLY')

    # --- lane-based wear: avenue (|x|<6.6) and the cross street's travel lanes (|y|<3.3) -----
    in_ave = g.maprange(ax, C.AVE_HALF - 0.2, C.AVE_HALF + 0.1, 1.0, 0.0)
    in_x = g.maprange(ay, C.CROSS_HALF - C.PARKING - 0.2, C.CROSS_HALF - C.PARKING + 0.1, 1.0, 0.0)
    wa, ca = lane_bands(g, X)
    wx, cx = lane_bands(g, Y)
    streak = g.maprange(g.noise(g.vscale(obj, (3.0, 0.15, 1.0)), 4.0, 3.0), 0.35, 0.65, 0.6, 1.0)
    streak2 = g.maprange(g.noise(g.vscale(obj, (0.15, 3.0, 1.0)), 4.0, 3.0), 0.35, 0.65, 0.6, 1.0)
    wheel = g.math('MAXIMUM', g.math('MULTIPLY', g.math('MULTIPLY', wa, in_ave), streak),
                   g.math('MULTIPLY', g.math('MULTIPLY', wx, in_x), streak2))
    # oil: lane centres, blotchy, denser within 25 m of the stop lines (idling cars)
    stopzone = g.maprange(g.math('ABSOLUTE', g.math('SUBTRACT', ay, C.stopline_pos(C.CROSS_HALF) + 6)),
                          4.0, 22.0, 1.0, 0.35)
    blot = g.maprange(g.noise(obj, 1.6, 2.0), 0.5, 0.62)
    oil_a = g.math('MULTIPLY', g.math('MULTIPLY', ca, in_ave), stopzone)
    oil_x = g.math('MULTIPLY', g.math('MULTIPLY', cx, in_x), 0.6)
    oil = g.math('MULTIPLY', g.math('MAXIMUM', oil_a, oil_x), blot)
    # gutter grime: 0.5 m dirty band along the kerbs
    def kerb_dist(a, half):
        return g.math('ABSOLUTE', g.math('SUBTRACT', a, half))
    dk = g.math('MINIMUM', kerb_dist(ax, C.AVE_HALF), kerb_dist(ay, C.CROSS_HALF))
    gutter = g.maprange(dk, 0.1, 0.6, 1.0, 0.0, smooth=True)
    grime = g.math('MULTIPLY', gutter, g.maprange(g.noise(obj, 2.5, 4.0), 0.35, 0.65, 0.5, 1.0))

    col = g.mixc(g.math('MULTIPLY', wheel, 0.35), col, (0.55, 0.55, 0.55), 'MULTIPLY')
    col = g.mixc(g.math('MULTIPLY', oil, 0.6), col, (0.35, 0.33, 0.3), 'MULTIPLY')
    col = g.mixc(g.math('MULTIPLY', grime, 0.5), col, (0.5, 0.45, 0.38), 'MULTIPLY')
    l.new(col, wet_grp.inputs['Color'])
    # dry roughness: polished wheel paths smoother, oil smoother, gutter grit rougher
    r_in = wet_grp.inputs['Roughness'].links[0].from_socket
    r = g.math('MULTIPLY', r_in, g.math('SUBTRACT', 1.0, g.math('MULTIPLY', wheel, 0.3)))
    r = g.math('MULTIPLY', r, g.math('SUBTRACT', 1.0, g.math('MULTIPLY', oil, 0.4)))
    l.new(r, wet_grp.inputs['Roughness'])

    # --- standing water ----------------------------------------------------------------------
    # kerb water: band 0.08-0.4 m, broken into patches (leaves/grit/uneven gutter)
    gband = g.maprange(dk, 0.06, 0.4, 1.0, 0.0, smooth=True)
    gbreak = g.maprange(g.noise(g.vscale(obj, (1.0, 1.0, 1.0)), 0.9, 3.0), 0.5, 0.62)
    gwater = g.math('MULTIPLY', gband, gbreak)
    # rut puddles in the wheel paths + random depressions; size varies with a second noise
    dep = g.noise(obj, 0.14, 5.0, 0.6)
    pud_th = g.maprange(g.noise(obj, 0.035, 2.0), 0.3, 0.7, 0.67, 0.61)    # threshold varies
    pud = g.maprange(g.math('SUBTRACT', g.math('ADD', dep, g.math('MULTIPLY', wheel, 0.05)), pud_th),
                     0.0, 0.025, 0.0, 1.0)
    water = g.math('MAXIMUM', gwater, pud, clamp=True)
    amount = n.new('ShaderNodeValue'); amount.name = 'PUDDLE_AMOUNT'; amount.outputs[0].default_value = 1.0
    water = g.math('MULTIPLY', water, amount.outputs[0])
    # water depth proxy: deeper in the middle -> smoother; edges are thin films (rougher)
    depth = g.maprange(water, 0.0, 1.0, 0.0, 1.0)
    film_r = wet_grp.outputs['Roughness']
    pud_r = g.mixf(depth, 0.08, 0.02)
    # tiny roughness noise even in puddles (dust film, rain ripples are added in the rain pass)
    pud_r = g.math('ADD', pud_r, g.math('MULTIPLY', g.noise(obj, 30.0, 2.0), 0.02))
    rough = g.mixf(water, film_r, pud_r)
    l.new(rough, b.inputs['Roughness'])
    nrm = _upstream(m, 'Normal')
    geo = n.new('ShaderNodeNewGeometry')
    nmix = n.new('ShaderNodeMix'); nmix.data_type = 'VECTOR'
    l.new(water, nmix.inputs['Factor'])
    l.new(nrm, nmix.inputs[4]); l.new(geo.outputs['Normal'], nmix.inputs[5])
    nmix.name = 'WATER_NORMAL_MIX'
    l.new(nmix.outputs[1], b.inputs['Normal'])
    bc = g.mixc(water, wet_grp.outputs['Color'], g.mixc(1.0, wet_grp.outputs['Color'], (0.6, 0.6, 0.6), 'MULTIPLY'))
    l.new(bc, b.inputs['Base Color'])
    # wet oil: thin-film interference (~250-450 nm), only where oil and wet
    if 'Thin Film Thickness' in b.inputs:
        tf = g.math('MULTIPLY', oil, g.maprange(g.noise(obj, 6.0, 2.0), 0.3, 0.7, 250, 450))
        l.new(tf, b.inputs['Thin Film Thickness'])
        b.inputs['Thin Film IOR'].default_value = 1.47
    m['water_mask'] = True
    return m


def asphalt_patch():
    """Utility-cut repair: newer, darker, finer asphalt."""
    m = M.pbr('Asphalt_patch', 'asphalt_04', 2.5, tint=(0.62, 0.62, 0.62), normal_strength=0.5)
    return m


def tar_seal():
    """Crack-seal / patch-joint bitumen: black, smoother than asphalt, glossy when wet."""
    return M.simple('Tar_seal', (0.02, 0.02, 0.02), 0.35, rough_var=0.15, porosity=0.9)


def repairs(root, rng):
    """Road repairs as thin geometry 3 mm above the road (no z-fighting): rectangular trench
    patches outlined with tar seal, plus meandering crack-seal 'tar snakes'."""
    col = collection('RoadRepairs', root)
    pm, tm = asphalt_patch(), tar_seal()
    z = 0.003
    patches = [   # (x0, y0, x1, y1)
        (0.4, -24.5, 6.4, -22.6),          # trench across the northbound lanes (camera's path)
        (-6.4, 21.0, -2.0, 23.4),
        (2.2, -41.0, 4.2, -33.0),          # longitudinal cut along a lane
        (-5.6, 34.0, -3.6, 40.0),
        (14.0, -3.2, 18.5, -0.6),          # cross street, east
    ]
    for i, (x0, y0, x1, y1) in enumerate(patches):
        mesh_object(f'Patch_{i}', [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)], col, pm)
        w = 0.06
        for (a, b2) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            _ribbon(f'PatchSeam_{i}', [a, b2], w, z + 0.0005, col, tm)
    # tar snakes: random walks roughly along the lane lines (longitudinal joint cracks)
    for i in range(14):
        sx = rng.choice((-3.3, 0.0, 3.3, -6.3, 6.3))
        y = rng.uniform(-45, 120)
        pts = []
        x = sx + rng.uniform(-0.25, 0.25)
        L = rng.uniform(3, 12)
        steps = int(L / 0.25)
        ang = math.pi / 2 + rng.uniform(-0.15, 0.15)
        for k in range(steps):
            pts.append((x, y))
            ang += rng.uniform(-0.35, 0.35)
            ang = max(math.pi / 2 - 0.6, min(math.pi / 2 + 0.6, ang))
            x += math.cos(ang) * 0.25; y += math.sin(ang) * 0.25
        _ribbon(f'TarSnake_{i}', pts, rng.uniform(0.035, 0.07), z, col, tm)
    return col


def _ribbon(name, pts, width, z, col, mat):
    verts, faces = [], []
    for i, (x, y) in enumerate(pts):
        if i < len(pts) - 1:
            dx, dy = pts[i + 1][0] - x, pts[i + 1][1] - y
        else:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * width / 2, dx / L * width / 2
        verts += [(x + nx, y + ny, z), (x - nx, y - ny, z)]
        if i:
            a = 2 * (i - 1)
            faces.append((a, a + 1, a + 3, a + 2))
    return mesh_object(name, verts, faces, col, mat)


def sidewalk():
    m = M.pbr('Sidewalk_wet', 'concrete_pavement', 3.0, tint=(0.85, 0.85, 0.83), tint_var=0.0,
              normal_strength=0.7, porosity=0.55, coat_rough=0.22)
    g = G(m); n, l = g.n, g.l
    wet_grp = next(x for x in n if x.type == 'GROUP')
    tc = n.new('ShaderNodeTexCoord'); obj = tc.outputs['Object']
    col = wet_grp.inputs['Color'].links[0].from_socket
    # per-slab tone (1.5 m slabs): cellular noise -> +-10 %
    vor = n.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 0.67
    vor.feature = 'F1'; l.new(obj, vor.inputs['Vector'])
    slab = g.maprange(vor.outputs['Distance'], 0.0, 1.0, 0.92, 1.06)
    col = g.mixc(1.0, col, g.mixc(1.0, (1, 1, 1), slab, 'MULTIPLY'), 'MULTIPLY')
    # stains (spills, rust, leaf tannin) and chewing gum (dark flattened dots, 2-4 cm)
    stain = g.maprange(g.noise(obj, 0.8, 5.0), 0.55, 0.75)
    col = g.mixc(g.math('MULTIPLY', stain, 0.4), col, (0.55, 0.5, 0.42), 'MULTIPLY')
    gum = n.new('ShaderNodeTexVoronoi'); gum.inputs['Scale'].default_value = 9.0
    gum.inputs['Randomness'].default_value = 1.0; l.new(obj, gum.inputs['Vector'])
    gsel = n.new('ShaderNodeTexWhiteNoise'); l.new(gum.outputs['Position'], gsel.inputs['Vector'])
    dots = g.math('MULTIPLY', g.maprange(gum.outputs['Distance'], 0.02, 0.035, 1.0, 0.0),
                  g.math('GREATER_THAN', gsel.outputs['Value'], 0.82))
    col = g.mixc(g.math('MULTIPLY', dots, 0.75), col, (0.2, 0.19, 0.18), 'MULTIPLY')
    l.new(col, wet_grp.inputs['Color'])
    return m


def paint(name, rgb):
    """Road paint, worn: gaps where tyres cross it, abraded edges, dirt."""
    m = M.simple(name, rgb, 0.45, rough_var=0.15, porosity=0.2)
    g = G(m); n, l = g.n, g.l
    wet_grp = next(x for x in n if x.type == 'GROUP')
    tc = n.new('ShaderNodeTexCoord'); obj = tc.outputs['Object']
    wear = g.maprange(g.noise(obj, 3.0, 6.0, 0.7), 0.28, 0.4, 1.0, 0.0)     # ~15 % worn through
    col = g.mixc(wear, (0.07, 0.07, 0.07), rgb)
    dirt = g.maprange(g.noise(obj, 0.7, 3.0), 0.3, 0.7, 0.7, 1.0)
    col = g.mixc(1.0, col, g.mixc(1.0, (1, 1, 1), dirt, 'MULTIPLY'), 'MULTIPLY')
    l.new(col, wet_grp.inputs['Color'])
    return m


def apply(root):
    road = asphalt()
    walk = sidewalk()
    white = paint('Paint_white', (0.62, 0.62, 0.58))
    yellow = paint('Paint_yellow', (0.62, 0.42, 0.05))
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials:
            continue
        mn = o.data.materials[0].name if o.data.materials[0] else ''
        rep = {'GB_road': road, 'GB_sidewalk': walk, 'GB_paint_white': white, 'GB_paint_yellow': yellow}.get(mn)
        if rep:
            o.data.materials[0] = rep
    repairs(root, random.Random(C.SEED + 5))
    return road
