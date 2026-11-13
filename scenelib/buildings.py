"""Procedural buildings with real geometric depth.

Every street facade is built from geometry, not textures alone:
  * recessed windows (reveals 15-25 cm) with sills, lintels and mullions
  * ground-floor shopfronts: pilasters, bulkheads, recessed glazing, transoms, sign fascias with
    3D lettering, fabric awnings, roller shutters, and lit shop interiors (real room boxes + area
    lights, so the light that spills onto the wet sidewalk is physically sourced)
  * belt courses, multi-step cornices with brackets, parapets
  * setbacks on taller buildings
  * fire escapes (platforms, railings, stairs, drop ladder) on brick walk-ups
  * rooftop water tanks and stair bulkheads (silhouettes against the sky glow)

Local facade frame: u along the frontage, v outward (towards the street), z up.
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector
from . import config as C
from . import materials as M
from .util import collection

# material slot indices (same for every building mesh)
WALL, TRIM, GLASS, FRAME, SHOPGLASS, SHOPFRAME, FASCIA, AWNING, SHUTTER, STEEL, ROOF, CORNICE, \
    INTERIOR, INT_BAR, INT_LAUNDRY, INT_PIZZA = range(16)
N_SLOTS = 16
AWNING_EDGES = []      # (p0, p1) world points of awning front edges, used for rain drips

SHOP_TYPES = [
    # name, open?, interior colour temperature (K), sign text options, sign colour, awning?
    ('deli', True, 4000, ['DELI', 'GROCERY', '24H DELI'], (1.0, 0.25, 0.12), True),
    ('bar', True, 2400, ['BAR', 'TAVERN', 'PUB'], (1.0, 0.1, 0.35), False),
    ('laundromat', True, 5000, ['LAUNDROMAT', 'WASH & FOLD'], (0.2, 0.6, 1.0), False),
    ('pizza', True, 3000, ['PIZZA', 'SLICE'], (1.0, 0.45, 0.1), True),
    ('pharmacy', False, 4500, ['PHARMACY'], (0.1, 1.0, 0.3), False),
    ('closed', False, None, ['NAILS', 'CELL REPAIR', 'TAILOR', 'SHOES'], None, True),
    ('shutter', False, None, [], None, False),
    ('vacant', False, None, [], None, False),
]


class Mesh:
    """bmesh wrapper working in a local facade frame."""

    def __init__(self, origin, udir, vdir):
        self.bm = bmesh.new()
        self.o = Vector(origin)
        self.u = Vector(udir).normalized()
        self.v = Vector(vdir).normalized()
        self.z = Vector((0, 0, 1))
        self.attr = self.bm.faces.layers.float.new('wid')

    def P(self, u, v, z):
        return self.o + self.u * u + self.v * v + self.z * z

    def quad(self, pts, mat, wid=0.0):
        vs = [self.bm.verts.new(self.P(*p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        f[self.attr] = wid
        return f

    def box(self, u0, u1, v0, v1, z0, z1, mat, skip=(), wid=0.0):
        """Axis-aligned (in the local frame) box; skip: names of faces to omit."""
        u0, u1 = min(u0, u1), max(u0, u1)
        v0, v1 = min(v0, v1), max(v0, v1)
        F = {
            'front': [(u0, v1, z0), (u1, v1, z0), (u1, v1, z1), (u0, v1, z1)],
            'back': [(u1, v0, z0), (u0, v0, z0), (u0, v0, z1), (u1, v0, z1)],
            'left': [(u0, v0, z0), (u0, v1, z0), (u0, v1, z1), (u0, v0, z1)],
            'right': [(u1, v1, z0), (u1, v0, z0), (u1, v0, z1), (u1, v1, z1)],
            'top': [(u0, v0, z1), (u0, v1, z1), (u1, v1, z1), (u1, v0, z1)],
            'bottom': [(u0, v1, z0), (u0, v0, z0), (u1, v0, z0), (u1, v1, z0)],
        }
        for k, pts in F.items():
            if k not in skip:
                self.quad(pts, mat, wid)

    def slab(self, a, b, thick, width, mat):
        """Thin beam between local points a and b (used for stairs / ladders)."""
        a, b = Vector(a), Vector(b)
        d = (b - a)
        side = Vector((0, 1, 0)) if abs(d.normalized().y) < 0.9 else Vector((1, 0, 0))
        w = d.cross(side).normalized()
        h = d.cross(w).normalized()
        if h.z < 0:
            h = -h
        corners = []
        for s1 in (-1, 1):
            for s2 in (-1, 1):
                corners.append((w * s1 * width / 2 + h * s2 * thick / 2))
        A = [a + c for c in corners]
        B = [b + c for c in corners]
        idx = [(0, 1, 3, 2)]
        vsA = [self.bm.verts.new(self.P(*p)) for p in A]
        vsB = [self.bm.verts.new(self.P(*p)) for p in B]
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            f = self.bm.faces.new((vsA[i], vsA[j], vsB[j], vsB[i]))
            f.material_index = mat

    def finish(self, name, col, mats):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0005)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        return ob


# --------------------------------------------------------------------------------------------
def window_grid(m, u0, u1, z0, floors, fh, style, rng, recess, detail):
    """Upper-floor wall [u0,u1] x [z0, z0+floors*fh] with punched, recessed windows."""
    W = u1 - u0
    nb = max(1, int(round(W / style['bay'])))
    bay = W / nb
    ww = min(style['win_w'], bay - 0.5)
    wh = style['win_h']
    sill_h = style['sill']
    for f in range(floors):
        fz0 = z0 + f * fh
        fz1 = fz0 + fh
        wz0 = fz0 + sill_h
        wz1 = min(wz0 + wh, fz1 - 0.35)
        # horizontal bands
        m.quad([(u0, 0, fz0), (u1, 0, fz0), (u1, 0, wz0), (u0, 0, wz0)], WALL)
        m.quad([(u0, 0, wz1), (u1, 0, wz1), (u1, 0, fz1), (u0, 0, fz1)], WALL)
        prev = u0
        for b in range(nb):
            cu = u0 + bay * (b + 0.5)
            a, c = cu - ww / 2, cu + ww / 2
            m.quad([(prev, 0, wz0), (a, 0, wz0), (a, 0, wz1), (prev, 0, wz1)], WALL)
            prev = c
            # reveals (inside faces of the opening)
            r = recess
            m.quad([(a, 0, wz0), (a, -r, wz0), (a, -r, wz1), (a, 0, wz1)], WALL)
            m.quad([(c, -r, wz0), (c, 0, wz0), (c, 0, wz1), (c, -r, wz1)], WALL)
            m.quad([(a, -r, wz1), (c, -r, wz1), (c, 0, wz1), (a, 0, wz1)], WALL)
            m.quad([(a, 0, wz0), (c, 0, wz0), (c, -r, wz0), (a, -r, wz0)], TRIM)
            wid = rng.random()
            m.quad([(a, -r, wz0), (c, -r, wz0), (c, -r, wz1), (a, -r, wz1)], GLASS, wid)
            if detail:
                fw = 0.06
                # frame ring + meeting rail (double-hung sash) / centre mullion
                m.box(a, c, -r, -r + 0.07, wz0, wz0 + fw, FRAME, skip=('back',))
                m.box(a, c, -r, -r + 0.07, wz1 - fw, wz1, FRAME, skip=('back',))
                m.box(a, a + fw, -r, -r + 0.07, wz0, wz1, FRAME, skip=('back',))
                m.box(c - fw, c, -r, -r + 0.07, wz0, wz1, FRAME, skip=('back',))
                mz = (wz0 + wz1) / 2
                m.box(a, c, -r, -r + 0.09, mz - 0.03, mz + 0.03, FRAME, skip=('back',))
                if ww > 1.4:
                    m.box(cu - 0.03, cu + 0.03, -r, -r + 0.07, wz0, wz1, FRAME, skip=('back',))
                # stone sill (projecting) and lintel
                m.box(a - 0.08, c + 0.08, -0.02, 0.06, wz0 - 0.07, wz0, TRIM, skip=('back',))
                if style['lintel']:
                    m.box(a - 0.1, c + 0.1, -0.01, 0.025, wz1, wz1 + 0.22, TRIM, skip=('back',))
            # (air-conditioner units in a few windows: a real NYC giveaway)
            if detail and rng.random() < style.get('ac', 0.0):
                m.box(cu - 0.33, cu + 0.33, -r + 0.05, 0.38, wz0 + 0.02, wz0 + 0.42, TRIM)
        m.quad([(prev, 0, wz0), (u1, 0, wz0), (u1, 0, wz1), (prev, 0, wz1)], WALL)
    return nb, bay


def cornice(m, u0, u1, ztop, depth, rng, detail):
    """Frieze + stepped cornice + brackets, ending at ztop. depth: projection (m)."""
    m.box(u0, u1, 0.0, 0.05, ztop - 1.0, ztop - 0.45, CORNICE, skip=('back',))
    steps = ((0.15, 0.45, 0.33), (0.35, 0.33, 0.18), (depth, 0.18, 0.0))
    for proj, zb, zt in steps:
        m.box(u0 - proj * 0.3, u1 + proj * 0.3, 0.0, proj, ztop - zb, ztop - zt, CORNICE, skip=('back',))
    if detail:
        n = int((u1 - u0) / 0.75)
        for i in range(n + 1):
            uc = u0 + (u1 - u0) * i / max(n, 1)
            m.box(uc - 0.07, uc + 0.07, 0.0, depth * 0.85, ztop - 0.45, ztop - 0.18, CORNICE)


def fire_escape(m, ua, ub, z0, floors, fh, rng):
    """Steel fire escape spanning [ua, ub] on floors 2..top (z0 = floor-2 level)."""
    D = 1.05
    for f in range(floors):
        zf = z0 + f * fh - 0.05
        m.box(ua, ub, 0.0, D, zf - 0.06, zf, STEEL)                       # grated platform
        m.box(ua, ub, D - 0.03, D, zf + 0.95, zf + 1.0, STEEL)            # top rail front
        m.box(ua, ub, D - 0.03, D, zf + 0.45, zf + 0.48, STEEL)           # mid rail
        for uu in (ua, ub - 0.03):
            m.box(uu, uu + 0.03, 0.0, D, zf + 0.95, zf + 1.0, STEEL)      # side rails
            m.box(uu, uu + 0.03, D - 0.03, D, zf, zf + 1.0, STEEL)        # corner posts
        k = int((ub - ua) / 0.5)
        for i in range(1, k):
            uu = ua + (ub - ua) * i / k
            m.box(uu - 0.012, uu + 0.012, D - 0.025, D, zf, zf + 0.95, STEEL)   # balusters
        # brackets under the platform
        for uu in (ua + 0.2, ub - 0.2):
            m.slab((uu, 0.0, zf - 0.6), (uu, D * 0.9, zf - 0.06), 0.05, 0.05, STEEL)
        # stair to the platform above (inside the railing line)
        if f < floors - 1:
            su0 = ua + 0.15
            su1 = su0 + min(2.4, (ub - ua) - 0.4)
            for vv in (0.25, 0.75):
                m.slab((su0, vv, zf), (su1, vv, zf + fh), 0.12, 0.03, STEEL)
            nsteps = 11
            for i in range(1, nsteps):
                t = i / nsteps
                uu = su0 + (su1 - su0) * t
                zz = zf + fh * t
                m.box(uu - 0.1, uu + 0.1, 0.25, 0.75, zz - 0.02, zz, STEEL)
    # drop ladder below the lowest platform
    ul = ub - 0.6
    for uu in (ul, ul + 0.45):
        m.slab((uu, D - 0.12, z0 - 0.06), (uu, D - 0.12, z0 - 2.6), 0.04, 0.04, STEEL)
    for i in range(7):
        zz = z0 - 0.3 - i * 0.33
        m.box(ul, ul + 0.45, D - 0.14, D - 0.10, zz - 0.015, zz + 0.015, STEEL)


def shopfront(m, u0, u1, zb, h, shop, rng, sign_col, lights):
    """One shop bay between pilasters. zb = sidewalk level. Builds glazing, bulkhead, transom,
    door recess, fascia, optional awning/shutter and (if lit) an interior room."""
    name, is_open, kelvin, texts, sign_rgb, awn = shop
    gl0, gl1 = zb + 0.5, zb + 3.0           # glass zone
    tr1 = zb + 3.45                         # transom top
    fz0, fz1 = zb + 3.55, zb + 4.35         # fascia band
    rec = 0.22
    W = u1 - u0
    # wall above fascia up to the floor line is part of the belt; below: storefront
    m.quad([(u0, 0, tr1), (u1, 0, tr1), (u1, 0, zb + h), (u0, 0, zb + h)], WALL)
    # bulkhead (kick plate), set in by the recess
    m.box(u0, u1, -rec, -rec + 0.04, zb, gl0, SHOPFRAME, skip=('back',))
    # reveals of the big opening
    m.quad([(u0, 0, zb), (u0, -rec, zb), (u0, -rec, tr1), (u0, 0, tr1)], SHOPFRAME)
    m.quad([(u1, -rec, zb), (u1, 0, zb), (u1, 0, tr1), (u1, -rec, tr1)], SHOPFRAME)
    m.quad([(u0, -rec, tr1), (u1, -rec, tr1), (u1, 0, tr1), (u0, 0, tr1)], SHOPFRAME)
    m.quad([(u0, 0, zb + 0.001), (u1, 0, zb + 0.001), (u1, -rec, zb + 0.001), (u0, -rec, zb + 0.001)], TRIM)
    # door position
    du0 = u0 + W * rng.choice((0.12, 0.62)) if W > 4 else u0 + 0.3
    du1 = du0 + 1.0
    glass_wid = rng.random()
    # glazing (fixed lites) left and right of the door, door glass too
    for a, b in ((u0, du0), (du0, du1), (du1, u1)):
        if b - a < 0.05:
            continue
        z0g = gl0 if (a, b) != (du0, du1) else zb + 0.05
        m.quad([(a, -rec, z0g), (b, -rec, z0g), (b, -rec, gl1), (a, -rec, gl1)], SHOPGLASS, glass_wid)
    m.quad([(u0, -rec, gl1 + 0.05), (u1, -rec, gl1 + 0.05), (u1, -rec, tr1), (u0, -rec, tr1)], SHOPGLASS, glass_wid)
    # aluminium frame members
    for uu in sorted({u0, du0, du1, u1}):
        m.box(uu - 0.04, uu + 0.04, -rec, -rec + 0.1, zb, tr1, SHOPFRAME, skip=('back',))
    m.box(u0, u1, -rec, -rec + 0.1, gl1, gl1 + 0.06, SHOPFRAME, skip=('back',))
    m.box(u0, u1, -rec, -rec + 0.1, gl0 - 0.04, gl0, SHOPFRAME, skip=('back',))
    # fascia sign box
    m.box(u0 + 0.05, u1 - 0.05, 0.0, 0.14, fz0, fz1, FASCIA)
    sign = None
    if texts and sign_rgb is None:       # closed shop: painted, unlit lettering
        sign_rgb = rng.choice(((0.75, 0.7, 0.6), (0.6, 0.08, 0.05), (0.85, 0.65, 0.15), (0.1, 0.25, 0.55)))
    if texts:
        sign = (rng.choice(texts), ((u0 + u1) / 2, 0.15, (fz0 + fz1) / 2), min(0.5, (fz1 - fz0) * 0.62),
                W - 0.6, sign_rgb, is_open)
    if name == 'shutter' or (name == 'closed' and rng.random() < 0.3):
        # roller shutter down over the glazing, housing box at the top
        m.box(u0 + 0.02, u1 - 0.02, -0.06, -0.02, zb, tr1, SHUTTER, skip=('back',))
        m.box(u0, u1, -0.05, 0.12, tr1 - 0.02, fz0 - 0.02, SHOPFRAME)
        is_open = False
    if awn and rng.random() < 0.75:
        a0, a1 = zb + 3.4, zb + 2.75
        proj = 1.25
        m.quad([(u0 + 0.05, 0.0, a0), (u1 - 0.05, 0.0, a0), (u1 - 0.05, proj, a1), (u0 + 0.05, proj, a1)], AWNING)
        m.quad([(u0 + 0.05, proj, a1), (u1 - 0.05, proj, a1), (u1 - 0.05, proj, a1 - 0.25), (u0 + 0.05, proj, a1 - 0.25)], AWNING)
        AWNING_EDGES.append((tuple(m.P(u0 + 0.1, proj + 0.01, a1 - 0.25)), tuple(m.P(u1 - 0.1, proj + 0.01, a1 - 0.25))))
        for uu in (u0 + 0.05, u1 - 0.05):
            m.quad([(uu, 0.0, a0), (uu, proj, a1), (uu, proj, a1 - 0.25), (uu, 0.0, a1 - 0.25)], AWNING)
    # interior room (only when the shop is lit; dark shops show their reflective glass)
    if is_open or name == 'pharmacy':
        dpt = 4.5
        imat = {'bar': INT_BAR, 'laundromat': INT_LAUNDRY, 'pizza': INT_PIZZA}.get(name, INTERIOR)
        m.box(u0 + 0.05, u1 - 0.05, -rec - dpt, -rec - 0.02, zb, tr1, imat, skip=('front',))
        lights.append(dict(kelvin=kelvin, open=is_open, centre=((u0 + u1) / 2, -rec - dpt / 2, tr1 - 0.05),
                           size=(W - 0.4, dpt - 0.6), frame=m))
    return sign


def make_sign(text, local, height, max_w, rgb, lit, frame, col, name):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = text
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.size = height
    cu.extrude = 0.025
    ob = bpy.data.objects.new(name, cu)
    col.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in me.vertices] or [0]
    w = max(xs) - min(xs)
    s = min(1.0, max_w / max(w, 1e-3))
    so = bpy.data.objects.new(name, me)
    col.objects.link(so)
    # text lies in its XY plane: rotate so it stands on the facade (u along X, facing +v)
    p = frame.P(*local)
    ang = math.atan2(frame.v.y, frame.v.x) + math.pi / 2
    so.location = p
    so.rotation_euler = (math.pi / 2, 0, ang)
    so.scale = (s, s, 1)
    mat = M.emissive(f'Sign_{name}', rgb, (900.0 / 683.0) if lit else 0.0, base=tuple(c * 0.4 for c in rgb))
    me.materials.append(mat)
    return so


# --------------------------------------------------------------------------------------------
STYLES = {
    'walkup':  dict(floors=(4, 6), bay=(2.4, 3.0), win_w=1.05, win_h=1.65, sill=0.85, lintel=True,
                    cornice=0.6, fire=0.6, setback=False, ac=0.12, walls=['brick_red', 'brick_brown', 'brick_patch']),
    'loft':    dict(floors=(6, 10), bay=(3.0, 3.6), win_w=1.6, win_h=2.1, sill=0.75, lintel=True,
                    cornice=0.8, fire=0.25, setback=True, ac=0.06, walls=['brick_red', 'brick_brown', 'stone_tile']),
    'modern':  dict(floors=(8, 14), bay=(1.6, 1.8), win_w=1.4, win_h=2.2, sill=0.6, lintel=False,
                    cornice=0.0, fire=0.0, setback=True, ac=0.0, walls=['stone_tile', 'concrete_panel']),
    'low':     dict(floors=(2, 3), bay=(2.6, 3.2), win_w=1.15, win_h=1.6, sill=0.9, lintel=True,
                    cornice=0.45, fire=0.0, setback=False, ac=0.1, walls=['stucco_cream', 'stucco_grey', 'brick_brown']),
}


def make_materials():
    mats = {}
    mats['brick_red'] = M.pbr('Wall_brick_red', 'brick_wall_02', 1.6, tint=(1.0, 0.93, 0.88), tint_var=0.2)
    mats['brick_brown'] = M.pbr('Wall_brick_brown', 'brick_wall_10', 1.6, tint=(0.95, 0.95, 0.98), tint_var=0.2)
    mats['brick_patch'] = M.pbr('Wall_brick_patch', 'red_brick_plaster_patch_02', 2.2, tint_var=0.1)
    mats['stone_tile'] = M.pbr('Wall_stone_tile', 'concrete_tile_facade', 2.5, tint=(0.95, 0.92, 0.86), tint_var=0.1)
    mats['concrete_panel'] = M.pbr('Wall_concrete', 'brushed_concrete', 2.5, tint=(0.8, 0.8, 0.8), tint_var=0.15)
    mats['stucco_cream'] = M.simple('Wall_stucco_cream', (0.55, 0.48, 0.36), 0.8, rough_var=0.1, porosity=0.8)
    mats['stucco_grey'] = M.simple('Wall_stucco_grey', (0.35, 0.36, 0.36), 0.8, rough_var=0.1, porosity=0.8)
    for k in ('brick_red', 'brick_brown', 'brick_patch', 'stone_tile', 'concrete_panel', 'stucco_cream', 'stucco_grey'):
        M.weather_facade(mats[k], streak_amt=0.4 if k.startswith(('stone', 'concrete', 'stucco')) else 0.3)
    mats['trim'] = M.pbr('Trim_stone', 'brushed_concrete', 1.2, tint=(0.75, 0.72, 0.66), tint_var=0.08)
    mats['frame'] = M.simple('Window_frame', (0.05, 0.05, 0.05), 0.45, rough_var=0.1, porosity=0.0)
    mats['shopframe'] = M.simple('Shop_frame', (0.12, 0.12, 0.12), 0.35, metal=0.8, rough_var=0.15, porosity=0.0)
    mats['fascia'] = M.simple('Shop_fascia', (0.08, 0.08, 0.09), 0.4, rough_var=0.1, porosity=0.0)
    mats['awning'] = M.simple('Awning_fabric', (0.12, 0.03, 0.03), 0.7, rough_var=0.1, porosity=1.0)
    mats['shutter'] = M.pbr('Shutter', 'painted_metal_shutter', 1.5, tint=(0.7, 0.7, 0.72), tint_var=0.2)
    mats['steel'] = M.simple('FireEscape_steel', (0.02, 0.02, 0.02), 0.55, metal=0.6, rough_var=0.2, porosity=0.0)
    mats['roof'] = M.simple('Roof_tar', (0.04, 0.04, 0.04), 0.85, porosity=0.3)
    mats['cornice'] = M.simple('Cornice_paint', (0.32, 0.3, 0.27), 0.55, metal=0.3, rough_var=0.15, porosity=0.0)
    mats['window_glass'] = window_glass_material()
    mats['shop_glass'] = M.glass('Shop_glass', rough=0.03)
    mats['interior'] = shop_interior_material('shelves')
    mats['int_bar'] = shop_interior_material('bar')
    mats['int_laundry'] = shop_interior_material('laundry')
    mats['int_pizza'] = shop_interior_material('pizza')
    return mats


def shop_interior_material(kind):
    """Shop interiors seen through the glass from 10-30 m. Object-space procedural patterns,
    confined to a 'fixture zone' 0.15-2.1 m above the floor with plain painted wall above and
    plain floor/ceiling (told apart by the normal):
      shelves : deli / pharmacy gondola shelving, muted packaging colours
      bar     : dark wood panelling, back-bar with a lit band of bottles at 1.1-1.7 m
      laundry : row of white front-loaders (dark round doors) at 0.3-1.2 m, dryers stacked above
      pizza   : white subway tile, stainless counter band, menu boards above"""
    m, n, l = M.new(f'Shop_interior_{kind}')
    b = n['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.5
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    oi = n.new('ShaderNodeObjectInfo')

    def mth(op, a, b_=None, c=None):
        x = n.new('ShaderNodeMath'); x.operation = op
        for i, v in enumerate((a, b_, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                l.new(v, x.inputs[i])
        return x.outputs[0]

    def mix(f, a, b_):
        x = n.new('ShaderNodeMix'); x.data_type = 'RGBA'
        for sock, v in (('Factor', f), ('A', a), ('B', b_)):
            if isinstance(v, tuple):
                x.inputs[sock].default_value = (*v, 1)
            elif isinstance(v, (int, float)):
                x.inputs[sock].default_value = v
            else:
                l.new(v, x.inputs[sock])
        return x.outputs['Result']
    Z = mth('SUBTRACT', sep.outputs['Z'], C.KERB_H)
    along = mth('ADD', sep.outputs['X'], sep.outputs['Y'])
    zone = mth('MULTIPLY', mth('GREATER_THAN', Z, 0.15), mth('LESS_THAN', Z, 2.1))
    wall_col = {'shelves': (0.55, 0.53, 0.5), 'bar': (0.12, 0.07, 0.04), 'laundry': (0.5, 0.55, 0.55),
                'pizza': (0.6, 0.58, 0.52)}[kind]
    if kind == 'shelves':
        rowz = mth('DIVIDE', Z, 0.42); row = mth('FLOOR', rowz); rfr = mth('FRACT', rowz)
        wr = n.new('ShaderNodeTexWhiteNoise'); wr.noise_dimensions = '1D'; l.new(row, wr.inputs['W'])
        wsz = mth('MULTIPLY_ADD', wr.outputs['Value'], 0.09, 0.07)
        cid = mth('FLOOR', mth('DIVIDE', along, wsz))
        cv = n.new('ShaderNodeCombineXYZ'); l.new(cid, cv.inputs['X']); l.new(row, cv.inputs['Y'])
        l.new(oi.outputs['Random'], cv.inputs['Z'])
        wn = n.new('ShaderNodeTexWhiteNoise'); l.new(cv.outputs['Vector'], wn.inputs['Vector'])
        ph = mth('MULTIPLY_ADD', wn.outputs['Value'], 0.4, 0.45)
        prod = mth('MULTIPLY', mth('LESS_THAN', rfr, ph), mth('GREATER_THAN', rfr, 0.06))
        hsv = n.new('ShaderNodeHueSaturation')
        hsv.inputs['Saturation'].default_value = 0.35; hsv.inputs['Value'].default_value = 0.5
        l.new(wn.outputs['Color'], hsv.inputs['Color'])
        fix = mix(prod, (0.03, 0.03, 0.032), hsv.outputs['Color'])
        fix = mix(mth('LESS_THAN', rfr, 0.06), fix, (0.35, 0.35, 0.36))
    elif kind == 'bar':
        band = mth('MULTIPLY', mth('GREATER_THAN', Z, 1.1), mth('LESS_THAN', Z, 1.7))
        cid = mth('FLOOR', mth('DIVIDE', along, 0.09))
        wn = n.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'; l.new(cid, wn.inputs['W'])
        bottle = mth('LESS_THAN', mth('FRACT', mth('DIVIDE', along, 0.09)), 0.7)
        bh = mth('LESS_THAN', mth('SUBTRACT', Z, 1.1), mth('MULTIPLY_ADD', wn.outputs['Value'], 0.15, 0.22))
        glass = mth('MULTIPLY', mth('MULTIPLY', band, bottle), bh)
        hsv = n.new('ShaderNodeHueSaturation')
        hsv.inputs['Hue'].default_value = 0.08; hsv.inputs['Saturation'].default_value = 0.8
        l.new(wn.outputs['Color'], hsv.inputs['Color'])
        fix = mix(glass, (0.1, 0.06, 0.035), hsv.outputs['Color'])
        # back-lit bottle shelf glows (LED strip)
        em = mth('MULTIPLY', glass, 0.6)
        l.new(hsv.outputs['Color'], b.inputs['Emission Color'])
        l.new(mth('MULTIPLY', em, 40 / 683), b.inputs['Emission Strength'])
    elif kind == 'laundry':
        cell = mth('DIVIDE', along, 0.7)
        u = mth('SUBTRACT', mth('FRACT', cell), 0.5)
        lowz = mth('SUBTRACT', Z, 0.75); upz = mth('SUBTRACT', Z, 1.6)
        def door(zc):
            cv = n.new('ShaderNodeCombineXYZ'); l.new(mth('MULTIPLY', u, 0.7), cv.inputs['X']); l.new(zc, cv.inputs['Y'])
            ln = n.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; l.new(cv.outputs['Vector'], ln.inputs[0])
            return mth('LESS_THAN', ln.outputs['Value'], 0.2)
        machine = mth('MULTIPLY', mth('GREATER_THAN', Z, 0.3), mth('LESS_THAN', Z, 2.0))
        gap = mth('LESS_THAN', mth('ABSOLUTE', u), 0.47)
        body = mth('MULTIPLY', machine, gap)
        doors = mth('MAXIMUM', door(lowz), door(upz))
        fix = mix(body, (0.12, 0.13, 0.13), (0.75, 0.76, 0.74))
        fix = mix(mth('MULTIPLY', doors, body), fix, (0.04, 0.05, 0.06))
    else:   # pizza
        tile = n.new('ShaderNodeTexBrick')
        tile.inputs['Scale'].default_value = 1.0
        tile.inputs['Color1'].default_value = (0.72, 0.72, 0.68, 1); tile.inputs['Color2'].default_value = (0.68, 0.68, 0.64, 1)
        tile.inputs['Mortar'].default_value = (0.35, 0.35, 0.33, 1)
        tile.inputs['Mortar Size'].default_value = 0.004
        tile.inputs['Brick Width'].default_value = 0.15; tile.inputs['Row Height'].default_value = 0.075
        cv = n.new('ShaderNodeCombineXYZ'); l.new(along, cv.inputs['X']); l.new(Z, cv.inputs['Y'])
        l.new(cv.outputs['Vector'], tile.inputs['Vector'])
        counter = mth('MULTIPLY', mth('GREATER_THAN', Z, 0.15), mth('LESS_THAN', Z, 1.0))
        fix = mix(counter, tile.outputs['Color'], (0.45, 0.45, 0.47))
        b.inputs['Metallic'].default_value = 0.0
        menu = mth('MULTIPLY', mth('GREATER_THAN', Z, 2.15), mth('LESS_THAN', Z, 2.9))
        fix = mix(menu, fix, (0.08, 0.08, 0.08))
        l.new(mth('MULTIPLY', menu, 120 / 683), b.inputs['Emission Strength'])
        b.inputs['Emission Color'].default_value = (1.0, 0.85, 0.6, 1)
        zone = mth('LESS_THAN', Z, 3.0)
    col = mix(zone, wall_col, fix)
    geo = n.new('ShaderNodeNewGeometry')
    nz = n.new('ShaderNodeSeparateXYZ'); l.new(geo.outputs['Normal'], nz.inputs['Vector'])
    hz = mth('GREATER_THAN', mth('ABSOLUTE', nz.outputs['Z']), 0.7)
    col = mix(hz, col, (0.4, 0.38, 0.35))
    l.new(col, b.inputs['Base Color'])
    return m


def window_glass_material():
    """Upper-floor glass: specular reflective pane over a fake room. Per-window random 'wid'
    decides: dark (60 %), warm tungsten/LED (27 %), cool (8 %), TV-blue (5 %); curtains partly
    block the glow. Emission is in nits-like units, kept low so windows read as rooms, not lamps."""
    m, n, l = M.new('Window_glass')
    b = n['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.03
    b.inputs['Specular IOR Level'].default_value = 0.5
    b.inputs['IOR'].default_value = 1.5
    b.inputs['Base Color'].default_value = (0.01, 0.012, 0.014, 1)
    at = n.new('ShaderNodeAttribute'); at.attribute_name = 'wid'; at.attribute_type = 'GEOMETRY'
    oi = n.new('ShaderNodeObjectInfo')
    add = n.new('ShaderNodeMath'); add.operation = 'ADD'
    l.new(at.outputs['Fac'], add.inputs[0]); l.new(oi.outputs['Random'], add.inputs[1])
    fr = n.new('ShaderNodeMath'); fr.operation = 'FRACT'
    l.new(add.outputs[0], fr.inputs[0])
    ramp = n.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    cr.elements[0].position = 0.0; cr.elements[0].color = (0, 0, 0, 1)
    # ~1/3 of windows lit at 11 pm on a weeknight; the rest dark. Lit ones vary in source and
    # brightness: warm tungsten / warm LED (most), cool LED / fluorescent, and TV-blue flicker.
    for pos, k, g in ((0.665, 2700, 0.85), (0.745, 2400, 0.6), (0.80, 3000, 0.75), (0.855, 2700, 0.5),
                      (0.885, 4300, 0.7), (0.925, 5500, 0.6), (0.955, 3500, 0.55), (0.975, 0, 0.45)):
        e = cr.elements.new(pos)
        rgb = M.blackbody_rgb(k) if k else (0.22, 0.38, 1.0)
        e.color = (rgb[0] * g, rgb[1] * g, rgb[2] * g, 1)
    l.new(fr.outputs[0], ramp.inputs['Fac'])
    # Window dressing, chosen per window from a second random number:
    #   35 % plain (lit room, brighter toward the ceiling light), 35 % venetian blinds (fine
    #   4 cm slats), 30 % drawn curtains (soft vertical folds, transmit ~35 %).
    r2 = n.new('ShaderNodeMath'); r2.operation = 'MULTIPLY_ADD'
    r2.inputs[1].default_value = 17.31; r2.inputs[2].default_value = 0.37
    l.new(add.outputs[0], r2.inputs[0])
    r2f = n.new('ShaderNodeMath'); r2f.operation = 'FRACT'; l.new(r2.outputs[0], r2f.inputs[0])
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    # floor-relative height 0..1 (storey 3.25 m) -> ceiling glow gradient
    zf = n.new('ShaderNodeMath'); zf.operation = 'DIVIDE'; zf.inputs[1].default_value = 3.25
    l.new(sep.outputs['Z'], zf.inputs[0])
    zfr = n.new('ShaderNodeMath'); zfr.operation = 'FRACT'; l.new(zf.outputs[0], zfr.inputs[0])
    grad = n.new('ShaderNodeMapRange')
    grad.inputs['From Min'].default_value = 0.25; grad.inputs['From Max'].default_value = 0.95
    grad.inputs['To Min'].default_value = 0.65; grad.inputs['To Max'].default_value = 0.9
    l.new(zfr.outputs[0], grad.inputs['Value'])
    # blinds: fine slats in Z
    sl = n.new('ShaderNodeMath'); sl.operation = 'MULTIPLY'; sl.inputs[1].default_value = 25.0
    l.new(sep.outputs['Z'], sl.inputs[0])
    sls = n.new('ShaderNodeMath'); sls.operation = 'SINE'; l.new(sl.outputs[0], sls.inputs[0])
    slm = n.new('ShaderNodeMapRange')
    slm.inputs['From Min'].default_value = -1; slm.inputs['From Max'].default_value = 1
    slm.inputs['To Min'].default_value = 0.3; slm.inputs['To Max'].default_value = 0.65
    l.new(sls.outputs[0], slm.inputs['Value'])
    # curtains: soft folds along the facade (x + y), noise-modulated
    xy = n.new('ShaderNodeMath'); xy.operation = 'ADD'
    l.new(sep.outputs['X'], xy.inputs[0]); l.new(sep.outputs['Y'], xy.inputs[1])
    cxyz = n.new('ShaderNodeCombineXYZ'); l.new(xy.outputs[0], cxyz.inputs['X'])
    l.new(sep.outputs['Z'], cxyz.inputs['Y'])
    nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 4.0
    nz.inputs['Detail'].default_value = 2.0
    l.new(cxyz.outputs['Vector'], nz.inputs['Vector'])
    cm = n.new('ShaderNodeMapRange')
    cm.inputs['To Min'].default_value = 0.3; cm.inputs['To Max'].default_value = 0.6
    l.new(nz.outputs['Fac'], cm.inputs['Value'])
    s1 = n.new('ShaderNodeMath'); s1.operation = 'GREATER_THAN'; s1.inputs[1].default_value = 0.35
    s2 = n.new('ShaderNodeMath'); s2.operation = 'GREATER_THAN'; s2.inputs[1].default_value = 0.70
    l.new(r2f.outputs[0], s1.inputs[0]); l.new(r2f.outputs[0], s2.inputs[0])
    m1 = n.new('ShaderNodeMix'); m1.data_type = 'FLOAT'
    l.new(s1.outputs[0], m1.inputs['Factor']); l.new(grad.outputs['Result'], m1.inputs['A'])
    l.new(slm.outputs['Result'], m1.inputs['B'])
    m2 = n.new('ShaderNodeMix'); m2.data_type = 'FLOAT'
    l.new(s2.outputs[0], m2.inputs['Factor']); l.new(m1.outputs['Result'], m2.inputs['A'])
    l.new(cm.outputs['Result'], m2.inputs['B'])
    mul = n.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    l.new(ramp.outputs['Color'], mul.inputs['A']); l.new(m2.outputs['Result'], mul.inputs['B'])
    l.new(mul.outputs['Result'], b.inputs['Emission Color'])
    st = n.new('ShaderNodeValue'); st.name = 'WINDOW_NITS'; st.outputs[0].default_value = 24.0 / 683.0  # cd/m2
    l.new(st.outputs[0], b.inputs['Emission Strength'])
    return m


# --------------------------------------------------------------------------------------------
def build_lot(col, name, origin, udir, vdir, W, D, style_name, rng, mats, detail, sign_col,
              lights, extra_facades=(), corner_side=None):
    """One building: facade on the street side (local v=0), mass extending to v=-D.
    extra_facades: [(origin, udir, vdir, W)] additional street facades (corner buildings)."""
    rng = random.Random(f'{C.SEED}-{name}')     # per-lot stream: edits stay local
    st = STYLES[style_name]
    floors = rng.randint(*st['floors'])
    zb = C.KERB_H
    H = C.GROUND_STOREY + (floors - 1) * C.STOREY
    wall_key = rng.choice(st['walls'])
    style = dict(st, bay=rng.uniform(*st['bay']))
    setback = st['setback'] and floors >= 9 and rng.random() < 0.7
    sb_floor = rng.randint(floors - 3, floors - 2) if setback else floors
    sb_depth = rng.uniform(2.5, 4.0)
    m = Mesh(origin, udir, vdir)
    facades = [(Vector(origin), Vector(udir), Vector(vdir), W)] + [
        (Vector(o), Vector(u), Vector(v), w) for o, u, v, w in extra_facades]
    signs = []
    for fi, (o, u, v, fw) in enumerate(facades):
        f = m if fi == 0 else _sub(m, o, u, v)
        _facade(f, fw, H, floors, sb_floor, sb_depth, style, rng, detail, zb, signs, lights, mats,
                is_corner=bool(extra_facades), lower_h=C.GROUND_STOREY + (sb_floor - 1) * C.STOREY)
    # mass: side and back walls and roof (local frame of the main facade)
    Hl = C.GROUND_STOREY + (sb_floor - 1) * C.STOREY
    m.box(0, W, -D, 0.0, zb, zb + Hl, WALL, skip=('front', 'bottom') + ((corner_side,) if corner_side else ()))
    m.box(0, W, -D, 0.0, zb + Hl, zb + Hl + 0.9, WALL, skip=('front', 'bottom', 'top'))   # parapet
    m.quad([(0.3, -D + 0.3, zb + Hl + 0.4), (0.3, -0.3, zb + Hl + 0.4), (W - 0.3, -0.3, zb + Hl + 0.4),
            (W - 0.3, -D + 0.3, zb + Hl + 0.4)], ROOF)
    if setback:
        m.box(0.0, W, -D + 1.0, -sb_depth, zb + Hl, zb + H, WALL, skip=('front', 'bottom'))
    # rooftop: stair bulkhead and (older buildings) a timber water tank on a steel stand
    roof_z = zb + Hl + 0.4
    if detail >= 1 and style_name in ('walkup', 'loft') and rng.random() < 0.55:
        cx, cv = rng.uniform(2.5, max(2.6, W - 2.5)), -rng.uniform(4, max(4.5, D - 4))
        water_tank(m, cx, cv, roof_z, rng)
    if detail >= 1 and rng.random() < 0.7:
        bx = rng.uniform(1, max(1.2, W - 4))
        m.box(bx, bx + 3.0, -D * 0.6, -D * 0.6 + 3.5, roof_z, roof_z + 2.8, WALL)
    allm = [mats[wall_key], mats['trim'], mats['window_glass'], mats['frame'], mats['shop_glass'],
            mats['shopframe'], mats['fascia'], mats['awning'], mats['shutter'], mats['steel'], mats['roof'],
            mats['cornice'], mats['interior'], mats['int_bar'], mats['int_laundry'], mats['int_pizza']]
    ob = m.finish(name, col, allm)
    for i, (text, loc, h, mw, rgb, lit, frame) in enumerate(signs):
        make_sign(text, loc, h, mw, rgb, lit, frame, sign_col, f'{name}_sign{i}')
    return ob, H


def _sub(m, o, u, v):
    """A second facade frame that writes into the same bmesh."""
    s = Mesh.__new__(Mesh)
    s.bm, s.attr = m.bm, m.attr
    s.o, s.u, s.v, s.z = Vector(o), Vector(u).normalized(), Vector(v).normalized(), Vector((0, 0, 1))
    return s


def _facade(m, W, H, floors, sb_floor, sb_depth, style, rng, detail, zb, signs, lights, mats,
            is_corner, lower_h):
    gh = C.GROUND_STOREY
    # Ground floor: pilasters + shop bays
    nshops = max(1, int(W // rng.uniform(5.0, 8.0)))
    edges = [0.0] + sorted(rng.uniform(W * i / nshops - 0.6, W * i / nshops + 0.6)
                           for i in range(1, nshops)) + [W]
    pil = 0.4
    used = set()
    for i in range(nshops):
        u0, u1 = edges[i] + pil / 2, edges[i + 1] - pil / 2
        if i == 0:
            u0 = pil
        if i == nshops - 1:
            u1 = W - pil
        if detail >= 1:
            pool = [t for t in SHOP_TYPES if t[0] not in used or t[0] in ('closed', 'shutter')]
            # 11 pm on a weeknight: most shops closed; a deli, a bar or a laundromat still open
            w = {'deli': 1.6, 'bar': 1.2, 'laundromat': 0.5, 'pizza': 0.8, 'pharmacy': 0.8, 'closed': 6,
                 'shutter': 2.0, 'vacant': 1.2}
            shop = rng.choices(pool, weights=[w[t[0]] for t in pool])[0]
            used.add(shop[0])
        else:
            shop = SHOP_TYPES[6]
        sg = shopfront(m, u0, u1, zb, gh, shop, rng, None, lights)
        if sg:
            text, loc, h, mw, rgb, lit = sg
            signs.append((text, loc, h, mw, rgb, lit, m))
    for e in edges:
        a = min(max(0.0, e - pil / 2), W - pil)
        b = a + pil
        m.box(a, b, 0.0, 0.1, zb, zb + gh, TRIM, skip=('back',))
    # belt course over the shops
    m.box(-0.05, W + 0.05, 0.0, 0.18, zb + gh - 0.12, zb + gh + 0.22, TRIM, skip=('back',))
    # upper floors up to the setback
    up = sb_floor - 1
    if up > 0:
        nb, bay = window_grid(m, 0.0, W, zb + gh, up, C.STOREY, style, rng,
                              recess=0.2 if style['lintel'] else 0.12, detail=detail >= 1)
        if detail >= 1 and rng.random() < style['fire'] and nb >= 3 and up >= 3 and not is_corner:
            b0 = rng.randint(0, nb - 2)
            fire_escape(m, bay * b0 + 0.25, bay * (b0 + 2) - 0.25, zb + gh + C.STOREY, up - 1, C.STOREY, rng)
    ztop = zb + lower_h
    if style['cornice'] > 0:
        cornice(m, 0.0, W, ztop + 0.9, style['cornice'], rng, detail >= 1)
        m.quad([(0, 0, ztop - 0.0), (W, 0, ztop), (W, 0, ztop + 0.9), (0, 0, ztop + 0.9)], WALL)
    else:
        m.quad([(0, 0, ztop), (W, 0, ztop), (W, 0, ztop + 0.9), (0, 0, ztop + 0.9)], WALL)
        m.box(-0.02, W + 0.02, -0.02, 0.06, ztop + 0.85, ztop + 0.95, CORNICE)   # metal coping
    # setback storeys
    if sb_floor < floors:
        z0 = zb + lower_h + 0.9
        nfl = floors - sb_floor
        s = _sub(m, m.o - m.v * sb_depth, m.u, m.v)
        window_grid(s, 0.0, W, z0, nfl, C.STOREY, style, rng, recess=0.15, detail=detail >= 1)
        s.quad([(0, 0, z0 + nfl * C.STOREY), (W, 0, z0 + nfl * C.STOREY),
                (W, 0, z0 + nfl * C.STOREY + 0.8), (0, 0, z0 + nfl * C.STOREY + 0.8)], WALL)
        s.box(-0.02, W + 0.02, -0.02, 0.06, z0 + nfl * C.STOREY + 0.75, z0 + nfl * C.STOREY + 0.85, CORNICE)
        # roof deck between facade and setback is covered by the main roof quad


def water_tank(m, cu, cv, z, rng):
    """Classic NYC timber water tank: ~3.6 m diameter, 4 m staves on a 3 m steel stand."""
    r, h, legs = rng.uniform(1.6, 2.0), rng.uniform(3.4, 4.2), 3.0
    for du, dv in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        m.box(cu + du * r * 0.6 - 0.08, cu + du * r * 0.6 + 0.08, cv + dv * r * 0.6 - 0.08,
              cv + dv * r * 0.6 + 0.08, z, z + legs, STEEL)
    seg = 20
    ring0, ring1 = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring0.append(m.bm.verts.new(m.P(cu + r * math.cos(a), cv + r * math.sin(a), z + legs)))
        ring1.append(m.bm.verts.new(m.P(cu + r * math.cos(a), cv + r * math.sin(a), z + legs + h)))
    for i in range(seg):
        j = (i + 1) % seg
        f = m.bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i])); f.material_index = ROOF
    apex = m.bm.verts.new(m.P(cu, cv, z + legs + h + r * 0.55))
    for i in range(seg):
        j = (i + 1) % seg
        f = m.bm.faces.new((ring1[i], ring1[j], apex)); f.material_index = ROOF
    f = m.bm.faces.new(list(reversed(ring0))); f.material_index = ROOF
    for k in range(4):          # steel hoops
        zz = z + legs + 0.4 + k * (h - 0.8) / 3
        m.box(cu - r - 0.02, cu + r + 0.02, cv - 0.02, cv + 0.02, zz, zz + 0.05, STEEL)


# --------------------------------------------------------------------------------------------
def build(root):
    rng = random.Random(C.SEED + 101)
    col = collection('Buildings', root)
    sign_col = collection('Signs', root)
    mats = make_materials()
    lights = []
    hw, hs = C.AVE_HALF + C.SIDEWALK, C.CROSS_HALF + C.SIDEWALK
    n = 0
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        ylen = C.AVE_LEN_N if sy > 0 else C.AVE_LEN_S
        # avenue frontage: facade plane at x = sx*hw, facing -sx (towards the avenue)
        vdir = Vector((-sx, 0, 0))
        udir = Vector((0, sy, 0))
        y = hs
        first = True
        corner_depth = None
        while y < ylen:
            dist = y
            detail = 2 if dist < 70 else (1 if dist < 140 else 0)
            W = rng.uniform(7.5, 16.0) if not first else rng.uniform(14, 20)
            W = min(W, ylen - y)
            if W < 4:
                break
            D = rng.uniform(16, 24) if not first else rng.uniform(18, 24)
            style = rng.choices(['walkup', 'loft', 'modern', 'low'], weights=(5, 3, 1.5, 1.5))[0]
            origin = Vector((sx * hw, sy * y, 0))
            # local u runs along +sy; v must be outward (-sx). Keep right-handedness consistent
            # by flipping u when needed so the facade normal (u x z) points along v.
            u = udir
            o = origin
            corner_side = 'left'          # local u=0 is the corner end
            if u.cross(Vector((0, 0, 1))).dot(vdir) < 0:
                u = -udir
                o = origin + udir * W
                corner_side = 'right'
            extra = ()
            if first:
                corner_depth = D
                # cross-street facade of the corner building: plane y = sy*hs facing -sy
                v2 = Vector((0, -sy, 0))
                u2 = Vector((sx, 0, 0))
                o2 = Vector((sx * hw, sy * hs, 0))
                if u2.cross(Vector((0, 0, 1))).dot(v2) < 0:
                    u2 = -u2
                    o2 = o2 + Vector((sx * D, 0, 0))
                extra = ((o2, u2, v2, D),)
            build_lot(col, f'Bldg_{n:03d}', o, u, vdir, W, D, style, rng, mats, detail, sign_col,
                      lights, extra, corner_side if first else None)
            n += 1
            y += W
            first = False
        # cross-street frontage beyond the corner building
        vdir = Vector((0, -sy, 0))
        x = hw + corner_depth
        while x < C.CROSS_LEN:
            detail = 2 if x < 45 else 1
            W = min(rng.uniform(7.0, 15.0), C.CROSS_LEN - x)
            if W < 4:
                break
            D = rng.uniform(14, 22)
            style = rng.choices(['walkup', 'loft', 'low', 'modern'], weights=(5, 2.5, 2, 1))[0]
            udir = Vector((sx, 0, 0))
            o = Vector((sx * x, sy * hs, 0))
            if udir.cross(Vector((0, 0, 1))).dot(vdir) < 0:
                udir = -udir
                o = o + Vector((sx * W, 0, 0))
            build_lot(col, f'Bldg_{n:03d}', o, udir, vdir, W, D, style, rng, mats, detail, sign_col, lights)
            n += 1
            x += W
    shop_lights(root, lights)
    return col, lights


def shop_lights(root, lights):
    """One rectangular area light per lit shop, in the ceiling, pointing down. Power from a
    plausible retail illuminance: ~500 lx open shops, ~80 lx after-hours security lighting."""
    col = collection('ShopLights', root)
    for i, L in enumerate(lights):
        m = L['frame']
        p = m.P(*L['centre'])
        w, d = L['size']
        lux = 220 if L['open'] else 30
        watts = lux * w * d * 1.5 / 683           # flux = E*A, x1.5 for losses to walls/shelving
        ld = bpy.data.lights.new(f'Shop_{i:02d}', 'AREA')
        ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = max(d, 0.5), max(w, 0.5)    # local X runs along v (depth)
        ld.energy = watts
        ld.color = M.blackbody_rgb(L['kelvin'] or 3500)
        ob = bpy.data.objects.new(f'ShopLight_{i:02d}', ld)
        col.objects.link(ob)
        ob.location = p
        ang = math.atan2(m.v.y, m.v.x)
        ob.rotation_euler = (0, 0, ang)
