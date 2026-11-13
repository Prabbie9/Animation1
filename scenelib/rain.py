"""Rain: everything runs on the same clock as the signals/traffic (scene time = frame / FPS).

Physical numbers (light rain, ~2-4 mm/h):
  * visible drops ~1-2 mm, terminal velocity ~4-6 m/s -> at a 180 deg shutter (1/48 s) each drop
    records a ~10-12 cm streak; streaks do not join up between frames (0.25 m per frame)
  * drops are only *seen* where they refract/scatter a bright source behind or beside them, so
    the streak shader is mostly transparent with translucent (forward-scattering) + glossy parts
  * puddle impacts: rings expanding at ~0.2-0.3 m/s, wavelength ~1-2 cm, dying within ~0.5 s
  * awning drips fall from rest under gravity: z = z0 - g t^2 / 2
Cheap by construction: a few tens of thousands of instanced quads (Geometry Nodes), and
procedural animated bump in the shaders (no simulation caches, nothing to bake).
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector
from . import config as C
from . import materials as M
from .util import collection

FALL_SPEED = 6.0          # m/s
STREAK_LEN = FALL_SPEED / (2 * C.FPS)      # 180-degree shutter
DROP_W = 0.0016           # m


# ------------------------------------------------------------------------- clock
def time_value(node_tree, name='RAIN_TIME'):
    """A Value node holding scene time in seconds, via a simple-expression driver (works with
    'Auto Run Python Scripts' disabled)."""
    v = node_tree.nodes.new('ShaderNodeValue'); v.name = name; v.label = 'scene time (s)'
    fc = v.outputs[0].driver_add('default_value')
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = f'frame / {C.FPS}'
    return v.outputs[0]


# ------------------------------------------------------------------------- streak material
def streak_material():
    m, n, l = M.new('RainStreak')
    out = n['Material Output']
    n.remove(n['Principled BSDF'])
    tr = n.new('ShaderNodeBsdfTranslucent'); tr.inputs['Color'].default_value = (0.6, 0.62, 0.64, 1)
    gl = n.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.08
    ad = n.new('ShaderNodeAddShader'); l.new(tr.outputs[0], ad.inputs[0]); l.new(gl.outputs[0], ad.inputs[1])
    tp = n.new('ShaderNodeBsdfTransparent')
    # alpha: fade out at the streak ends (motion-blur profile) and keep it thin overall
    uv = n.new('ShaderNodeUVMap')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(uv.outputs['UV'], sep.inputs['Vector'])
    pi = n.new('ShaderNodeMath'); pi.operation = 'MULTIPLY'; pi.inputs[1].default_value = math.pi
    l.new(sep.outputs['Y'], pi.inputs[0])
    sn = n.new('ShaderNodeMath'); sn.operation = 'SINE'; l.new(pi.outputs[0], sn.inputs[0])
    a = n.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; a.inputs[1].default_value = 0.4
    l.new(sn.outputs[0], a.inputs[0])
    mx = n.new('ShaderNodeMixShader')
    l.new(a.outputs[0], mx.inputs['Fac']); l.new(tp.outputs[0], mx.inputs[1]); l.new(ad.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs['Surface'])
    return m


def streak_proto(col, mat, length=STREAK_LEN, width=DROP_W, name='RainStreakProto'):
    """Vertical quad in the XZ plane (normal -Y), origin at its centre, UV v along the length."""
    me = bpy.data.meshes.new(name)
    w, h = width / 2, length / 2
    me.from_pydata([(-w, 0, -h), (w, 0, -h), (w, 0, h), (-w, 0, h)], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    for loop, uvv in zip(me.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uvl.data[loop.index].uv = uvv
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


# ------------------------------------------------------------------------- GN: falling rain
def _gn_group(name):
    g = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    return g


def rain_streaks(col, cam, proto, box_min, box_max, count, seed, name):
    """Points uniformly in a box, falling at FALL_SPEED and wrapping vertically; each instances
    the streak quad, rotated about Z to face the camera."""
    g = _gn_group(name)
    n, l = g.nodes, g.links
    gi = n.new('NodeGroupInput'); go = n.new('NodeGroupOutput')
    pts = n.new('GeometryNodePoints'); pts.inputs['Count'].default_value = count
    rnd = n.new('FunctionNodeRandomValue'); rnd.data_type = 'FLOAT_VECTOR'
    rnd.inputs['Min'].default_value = box_min; rnd.inputs['Max'].default_value = box_max
    rnd.inputs['Seed'].default_value = seed
    st = n.new('GeometryNodeInputSceneTime')
    sxyz = n.new('ShaderNodeSeparateXYZ'); l.new(rnd.outputs['Value'], sxyz.inputs['Vector'])
    H = box_max[2] - box_min[2]
    # z = zmin + floored_mod(z0 - zmin - v t, H); x drifts with a 0.4 m/s breeze (wrapping)
    def fm(op, a, b, c=None):
        x = n.new('ShaderNodeMath'); x.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                l.new(v, x.inputs[i])
        return x.outputs[0]
    zt = fm('MULTIPLY_ADD', st.outputs['Seconds'], -FALL_SPEED, fm('SUBTRACT', sxyz.outputs['Z'], box_min[2]))
    z = fm('ADD', fm('FLOORED_MODULO', zt, H), box_min[2])
    W = box_max[0] - box_min[0]
    xt = fm('MULTIPLY_ADD', st.outputs['Seconds'], 0.4, fm('SUBTRACT', sxyz.outputs['X'], box_min[0]))
    x = fm('ADD', fm('FLOORED_MODULO', xt, W), box_min[0])
    cxyz = n.new('ShaderNodeCombineXYZ')
    l.new(x, cxyz.inputs['X']); l.new(sxyz.outputs['Y'], cxyz.inputs['Y']); l.new(z, cxyz.inputs['Z'])
    l.new(cxyz.outputs['Vector'], pts.inputs['Position'])
    # face the camera (rotate about Z only)
    ci = n.new('GeometryNodeObjectInfo'); ci.inputs['Object'].default_value = cam
    pos = n.new('GeometryNodeInputPosition')
    dv = n.new('ShaderNodeVectorMath'); dv.operation = 'SUBTRACT'
    l.new(ci.outputs['Location'], dv.inputs[0]); l.new(pos.outputs['Position'], dv.inputs[1])
    al = n.new('FunctionNodeAlignRotationToVector'); al.axis = 'Y'; al.pivot_axis = 'Z'
    # the quad's normal is -Y: align -Y to the camera by aligning +Y to the opposite vector
    neg = n.new('ShaderNodeVectorMath'); neg.operation = 'SCALE'; neg.inputs['Scale'].default_value = -1
    l.new(dv.outputs['Vector'], neg.inputs[0]); l.new(neg.outputs['Vector'], al.inputs['Vector'])
    pi = n.new('GeometryNodeObjectInfo'); pi.inputs['Object'].default_value = proto
    pi.inputs['As Instance'].default_value = True
    iop = n.new('GeometryNodeInstanceOnPoints')
    l.new(pts.outputs['Geometry'], iop.inputs['Points'])
    l.new(pi.outputs['Geometry'], iop.inputs['Instance'])
    l.new(al.outputs['Rotation'], iop.inputs['Rotation'])
    # slight size variation (drop size distribution)
    rs = n.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    rs.inputs[2].default_value = 0.7; rs.inputs[3].default_value = 1.4; rs.inputs['Seed'].default_value = seed + 1
    l.new(rs.outputs[1], iop.inputs['Scale'])
    l.new(iop.outputs['Instances'], go.inputs['Geometry'])
    holder = bpy.data.meshes.new(name + '_holder')
    ob = bpy.data.objects.new(name, holder)
    col.objects.link(ob)
    mod = ob.modifiers.new('Rain', 'NODES'); mod.node_group = g
    # camera (and transmission) only: drops reflected in the road are invisible in reality and
    # tens of thousands of thin transparent quads in every glossy path add a lot of noise
    ob.visible_shadow = False
    ob.visible_glossy = False
    ob.visible_diffuse = False
    return ob


def awning_drips(col, cam, proto, edges, rng):
    """Drops detaching from awning edges every 0.4-1.2 s and falling freely to the sidewalk."""
    verts, period, phase, z0s = [], [], [], []
    for p0, p1 in edges:
        p0, p1 = Vector(p0), Vector(p1)
        L = (p1 - p0).length
        k = max(1, int(L / 0.18))
        for i in range(k):
            t = (i + rng.uniform(0.2, 0.8)) / k
            p = p0.lerp(p1, t)
            verts.append(p); period.append(rng.uniform(0.4, 1.2)); phase.append(rng.random())
    me = bpy.data.meshes.new('AwningDripPoints')
    me.from_pydata([tuple(v) for v in verts], [], [])
    for nm, data in (('period', period), ('phase', phase)):
        a = me.attributes.new(nm, 'FLOAT', 'POINT'); a.data.foreach_set('value', data)
    g = _gn_group('AwningDrips')
    n, l = g.nodes, g.links
    gi = n.new('NodeGroupInput'); go = n.new('NodeGroupOutput')
    st = n.new('GeometryNodeInputSceneTime')
    na_p = n.new('GeometryNodeInputNamedAttribute'); na_p.data_type = 'FLOAT'; na_p.inputs['Name'].default_value = 'period'
    na_f = n.new('GeometryNodeInputNamedAttribute'); na_f.data_type = 'FLOAT'; na_f.inputs['Name'].default_value = 'phase'

    def fm(op, a, b=None, c=None):
        x = n.new('ShaderNodeMath'); x.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                l.new(v, x.inputs[i])
        return x.outputs[0]
    tau = fm('MULTIPLY', fm('FRACT', fm('ADD', fm('DIVIDE', st.outputs['Seconds'], na_p.outputs['Attribute']),
                                        na_f.outputs['Attribute'])), na_p.outputs['Attribute'])
    dz = fm('MULTIPLY', fm('MULTIPLY', tau, tau), -4.905)
    pos = n.new('GeometryNodeInputPosition')
    sp = n.new('GeometryNodeSetPosition')
    off = n.new('ShaderNodeCombineXYZ'); l.new(dz, off.inputs['Z'])
    l.new(gi.outputs['Geometry'], sp.inputs['Geometry']); l.new(off.outputs['Vector'], sp.inputs['Offset'])
    # delete drops that have reached the sidewalk
    sepz = n.new('ShaderNodeSeparateXYZ'); l.new(pos.outputs['Position'], sepz.inputs['Vector'])
    below = fm('LESS_THAN', sepz.outputs['Z'], C.KERB_H + 0.03)
    dl = n.new('GeometryNodeDeleteGeometry'); dl.domain = 'POINT'
    l.new(sp.outputs['Geometry'], dl.inputs['Geometry']); l.new(below, dl.inputs['Selection'])
    tov = n.new('GeometryNodeMeshToPoints'); l.new(dl.outputs['Geometry'], tov.inputs['Mesh'])
    ci = n.new('GeometryNodeObjectInfo'); ci.inputs['Object'].default_value = cam
    dv = n.new('ShaderNodeVectorMath'); dv.operation = 'SUBTRACT'
    l.new(pos.outputs['Position'], dv.inputs[0]); l.new(ci.outputs['Location'], dv.inputs[1])
    al = n.new('FunctionNodeAlignRotationToVector'); al.axis = 'Y'; al.pivot_axis = 'Z'
    l.new(dv.outputs['Vector'], al.inputs['Vector'])
    pi = n.new('GeometryNodeObjectInfo'); pi.inputs['Object'].default_value = proto
    pi.inputs['As Instance'].default_value = True
    iop = n.new('GeometryNodeInstanceOnPoints')
    l.new(tov.outputs['Points'], iop.inputs['Points']); l.new(pi.outputs['Geometry'], iop.inputs['Instance'])
    l.new(al.outputs['Rotation'], iop.inputs['Rotation'])
    # streak length grows with speed (v = g tau), thicker than rain drops (4 mm drips)
    vlen = fm('MAXIMUM', fm('DIVIDE', fm('MULTIPLY', tau, 9.81 / (2 * C.FPS)), STREAK_LEN), 0.15)
    sc = n.new('ShaderNodeCombineXYZ')
    sc.inputs['X'].default_value = 2.5; sc.inputs['Y'].default_value = 1.0
    l.new(vlen, sc.inputs['Z'])
    l.new(sc.outputs['Vector'], iop.inputs['Scale'])
    l.new(iop.outputs['Instances'], go.inputs['Geometry'])
    ob = bpy.data.objects.new('AwningDrips', me)
    col.objects.link(ob)
    mod = ob.modifiers.new('Drips', 'NODES'); mod.node_group = g
    ob.visible_shadow = False
    ob.visible_glossy = False
    ob.visible_diffuse = False
    return ob


# ------------------------------------------------------------------------- surface water
def _ring_layer(n, l, xy, t, scale, period, speed, seed):
    """Height field of expanding impact rings: one impact per Voronoi cell per period."""
    def fm(op, a, b=None, c=None):
        x = n.new('ShaderNodeMath'); x.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                l.new(v, x.inputs[i])
        return x.outputs[0]
    vor = n.new('ShaderNodeTexVoronoi'); vor.voronoi_dimensions = '3D'
    vor.inputs['Scale'].default_value = scale; vor.inputs['Randomness'].default_value = 1.0
    off = n.new('ShaderNodeVectorMath'); off.operation = 'ADD'; off.inputs[1].default_value = (seed * 17.3, seed * 9.1, 0)
    l.new(xy, off.inputs[0]); l.new(off.outputs[0], vor.inputs['Vector'])
    sepc = n.new('ShaderNodeSeparateColor'); l.new(vor.outputs['Color'], sepc.inputs['Color'])
    phase = sepc.outputs['Red']
    tau = fm('FRACT', fm('ADD', fm('DIVIDE', t, period), phase))          # 0..1 within the period
    r = fm('MULTIPLY', tau, period * speed)                                 # ring radius (m)
    d = fm('DIVIDE', vor.outputs['Distance'], scale)                        # distance to impact (m)
    dd = fm('SUBTRACT', d, r)
    wave = fm('SINE', fm('MULTIPLY', dd, 2 * math.pi / 0.014))
    env = fm('EXPONENT', fm('MULTIPLY', fm('MULTIPLY', dd, dd), -1.0 / (0.012 ** 2)))
    fade = fm('POWER', fm('SUBTRACT', 1.0, tau), 2.0)
    return fm('MULTIPLY', fm('MULTIPLY', wave, env), fade)


def water_surface_animation(road_mat):
    """Adds rain-impact rings (puddles strong, wet film faint) and gutter runoff to the asphalt."""
    nt = road_mat.node_tree
    n, l = nt.nodes, nt.links
    b = n['Principled BSDF']
    nmix = n['WATER_NORMAL_MIX']
    water = nmix.inputs['Factor'].links[0].from_socket
    t = time_value(nt)
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    xy = n.new('ShaderNodeCombineXYZ')
    l.new(sep.outputs['X'], xy.inputs['X']); l.new(sep.outputs['Y'], xy.inputs['Y'])

    def fm(op, a, b_=None):
        x = n.new('ShaderNodeMath'); x.operation = op
        for i, v in enumerate((a, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                l.new(v, x.inputs[i])
        return x.outputs[0]
    r1 = _ring_layer(n, l, xy.outputs['Vector'], t, 7.0, 0.55, 0.22, 1)
    r2 = _ring_layer(n, l, xy.outputs['Vector'], t, 9.5, 0.45, 0.25, 2)
    rings = fm('ADD', r1, r2)
    # strong in standing water, faint on the film (impacts only dent a thin film)
    wgt = fm('ADD', fm('MULTIPLY', water, 0.85), 0.15)
    h = fm('MULTIPLY', fm('MULTIPLY', rings, wgt), 0.0004)       # metres
    # gutter runoff: ripple pattern advected along the kerbs towards the corner drains
    ax = fm('ABSOLUTE', sep.outputs['X']); ay = fm('ABSOLUTE', sep.outputs['Y'])
    along_ave = fm('ADD', ay, fm('MULTIPLY', t, 0.45))           # flows towards smaller |y|
    along_x = fm('ADD', ax, fm('MULTIPLY', t, 0.45))
    def flow(along, across):
        v = n.new('ShaderNodeCombineXYZ')
        l.new(fm('MULTIPLY', along, 2.5), v.inputs['X']); l.new(fm('MULTIPLY', across, 12.0), v.inputs['Y'])
        nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 3
        l.new(v.outputs['Vector'], nz.inputs['Vector'])
        return fm('SUBTRACT', nz.outputs['Fac'], 0.5)
    gx = fm('LESS_THAN', fm('ABSOLUTE', fm('SUBTRACT', ax, C.AVE_HALF)), 0.4)
    gy = fm('LESS_THAN', fm('ABSOLUTE', fm('SUBTRACT', ay, C.CROSS_HALF)), 0.4)
    fl = fm('ADD', fm('MULTIPLY', flow(along_ave, ax), gx), fm('MULTIPLY', flow(along_x, ay), gy))
    h = fm('ADD', h, fm('MULTIPLY', fm('MULTIPLY', fl, water), 0.0006))
    bump = n.new('ShaderNodeBump'); bump.inputs['Distance'].default_value = 1.0
    bump.inputs['Strength'].default_value = 1.0
    l.new(h, bump.inputs['Height'])
    l.new(nmix.outputs[1], bump.inputs['Normal'])
    l.new(bump.outputs['Normal'], b.inputs['Normal'])


def catch_basins(root):
    """US curb-inlet catch basins on the upstream side of each corner: a steel grate in the
    gutter and a dark inlet slot in the kerb face."""
    col = collection('Drains', root)
    grate = M.simple('Grate_steel', (0.05, 0.045, 0.04), 0.5, metal=0.8, rough_var=0.2, porosity=0.0)
    dark = M.simple('Drain_void', (0.0, 0.0, 0.0), 1.0, porosity=0.0)
    y0 = C.crosswalk_span(C.CROSS_HALF)[1] + 2.2
    for sx in (1, -1):
        for sy in (1, -1):
            x_k = sx * C.AVE_HALF
            yc = sy * (y0 + 0.6)
            bm = bmesh.new()
            # grate 0.6 x 1.2 m flush with the road, bars across the flow
            for i in range(9):
                yy = yc - 0.55 + i * 0.1375
                for (xa, xb) in ((x_k - sx * 0.62, x_k - sx * 0.02),):
                    x0_, x1_ = sorted((xa, xb))
                    v = [bm.verts.new(p) for p in ((x0_, yy - 0.025, 0.004), (x1_, yy - 0.025, 0.004),
                                                   (x1_, yy + 0.025, 0.004), (x0_, yy + 0.025, 0.004))]
                    bm.faces.new(v)
            me = bpy.data.meshes.new('Grate'); bm.to_mesh(me); bm.free()
            me.materials.append(grate)
            o = bpy.data.objects.new(f'CatchBasinGrate_{sx}_{sy}', me); col.objects.link(o)
            # the void below the bars
            x0_, x1_ = sorted((x_k - sx * 0.62, x_k - sx * 0.02))
            v = [(x0_, yc - 0.6, 0.002), (x1_, yc - 0.6, 0.002), (x1_, yc + 0.6, 0.002), (x0_, yc + 0.6, 0.002)]
            me2 = bpy.data.meshes.new('GrateVoid'); me2.from_pydata(v, [], [(0, 1, 2, 3)]); me2.materials.append(dark)
            o2 = bpy.data.objects.new(f'CatchBasinVoid_{sx}_{sy}', me2); col.objects.link(o2)
            # kerb inlet slot (dark opening 1.2 m x 0.1 m in the kerb face)
            xs = x_k + sx * 0.005
            v = [(xs, yc - 0.6, 0.02), (xs, yc + 0.6, 0.02), (xs, yc + 0.6, 0.12), (xs, yc - 0.6, 0.12)]
            if sx < 0:
                v = [v[1], v[0], v[3], v[2]]
            me3 = bpy.data.meshes.new('KerbInlet'); me3.from_pydata(v, [], [(0, 1, 2, 3)]); me3.materials.append(dark)
            o3 = bpy.data.objects.new(f'KerbInlet_{sx}_{sy}', me3); col.objects.link(o3)
    return col


# ------------------------------------------------------------------------- vehicles
def droplets_bump(nt, t, base_normal, scale=140.0, strength=0.6):
    """Water drops and rivulets on glass/paint (object space)."""
    n, l = nt.nodes, nt.links
    tc = n.new('ShaderNodeTexCoord')
    vor = n.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = scale
    vor.inputs['Randomness'].default_value = 1.0
    l.new(tc.outputs['Object'], vor.inputs['Vector'])
    # dome-shaped drops: radius varies per cell (35-60 % of the cell)
    sepc = n.new('ShaderNodeSeparateColor'); l.new(vor.outputs['Color'], sepc.inputs['Color'])
    rad = n.new('ShaderNodeMapRange')
    rad.inputs['To Min'].default_value = 0.2; rad.inputs['To Max'].default_value = 0.42
    l.new(sepc.outputs['Red'], rad.inputs['Value'])
    q = n.new('ShaderNodeMath'); q.operation = 'DIVIDE'
    l.new(vor.outputs['Distance'], q.inputs[0]); l.new(rad.outputs['Result'], q.inputs[1])
    q2 = n.new('ShaderNodeMath'); q2.operation = 'MULTIPLY'; l.new(q.outputs[0], q2.inputs[0]); l.new(q.outputs[0], q2.inputs[1])
    dome = n.new('ShaderNodeMath'); dome.operation = 'SUBTRACT'; dome.use_clamp = True
    dome.inputs[0].default_value = 1.0; l.new(q2.outputs[0], dome.inputs[1])
    sq = n.new('ShaderNodeMath'); sq.operation = 'SQRT'; l.new(dome.outputs[0], sq.inputs[0])
    # rivulets: vertically stretched noise sliding down slowly
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    zt = n.new('ShaderNodeMath'); zt.operation = 'MULTIPLY_ADD'
    l.new(t, zt.inputs[0]); zt.inputs[1].default_value = 0.04; l.new(sep.outputs['Z'], zt.inputs[2])
    cv = n.new('ShaderNodeCombineXYZ')
    xs = n.new('ShaderNodeMath'); xs.operation = 'MULTIPLY'; xs.inputs[1].default_value = 60.0
    l.new(sep.outputs['X'], xs.inputs[0]); l.new(xs.outputs[0], cv.inputs['X'])
    zs = n.new('ShaderNodeMath'); zs.operation = 'MULTIPLY'; zs.inputs[1].default_value = 3.0
    l.new(zt.outputs[0], zs.inputs[0]); l.new(zs.outputs[0], cv.inputs['Y'])
    nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0
    l.new(cv.outputs['Vector'], nz.inputs['Vector'])
    riv = n.new('ShaderNodeMapRange')
    riv.inputs['From Min'].default_value = 0.62; riv.inputs['From Max'].default_value = 0.7
    l.new(nz.outputs['Fac'], riv.inputs['Value'])
    h = n.new('ShaderNodeMath'); h.operation = 'MAXIMUM'
    l.new(sq.outputs[0], h.inputs[0]); l.new(riv.outputs['Result'], h.inputs[1])
    bp = n.new('ShaderNodeBump'); bp.inputs['Distance'].default_value = 0.002
    bp.inputs['Strength'].default_value = strength
    l.new(h.outputs[0], bp.inputs['Height'])
    if base_normal is not None:
        l.new(base_normal, bp.inputs['Normal'])
    return bp.outputs['Normal']


def wet_vehicles():
    """Drops on all vehicle glass (refract through the bump), beads on the clear coats."""
    glass_names = ('glass', 'glass_window', 'Index_0_2_SS')
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        if m.name in glass_names or m.name.startswith('Glass_'):
            b = m.node_tree.nodes.get('Principled BSDF')
            if not b:
                continue
            base = b.inputs['Normal'].links[0].from_socket if b.inputs['Normal'].links else None
            t = time_value(m.node_tree)
            m.node_tree.links.new(droplets_bump(m.node_tree, t, base), b.inputs['Normal'])
        elif m.name.startswith('CarPaint_') or m.name in ('main_frame',) or m.name.startswith('Body_'):
            b = m.node_tree.nodes.get('Principled BSDF')
            if not b:
                continue
            b.inputs['Coat Weight'].default_value = max(b.inputs['Coat Weight'].default_value, 0.8)
            b.inputs['Coat Roughness'].default_value = 0.04
            t = time_value(m.node_tree)
            m.node_tree.links.new(droplets_bump(m.node_tree, t, None, scale=90.0, strength=0.35),
                                  b.inputs['Coat Normal'])


def windscreen_frame(body, glass_prefix='Glass_'):
    """Find the windscreen in a vehicle body (local space): glass faces facing forward-and-up
    in the front half. Returns (bottom-centre point, normal, width) or None."""
    me = body.data
    idx = [i for i, m in enumerate(me.materials) if m and m.name.startswith(glass_prefix)]
    pts, nrm = [], Vector()
    for p in me.polygons:
        if p.material_index in idx and p.normal.y > 0.35 and p.normal.z > 0.3 and p.center.y > 0:
            pts += [me.vertices[v].co for v in p.vertices]
            nrm += p.normal * p.area
    if not pts:
        return None
    zmin = min(v.z for v in pts)
    low = [v for v in pts if v.z < zmin + 0.06]
    c = sum(low, Vector()) / len(low)
    w = max(v.x for v in pts) - min(v.x for v in pts)
    return c, nrm.normalized(), w


def wipers(root, vehicles):
    """Tandem wipers on the oncoming cars (windscreens face the camera), 45 sweeps/min
    (0.75 Hz) through ~80 degrees, keyed on every frame of the shared clock."""
    col = collection('Wipers', root)
    blade_m = M.simple('Wiper_rubber', (0.01, 0.01, 0.01), 0.4, porosity=0.0)
    for name, v in vehicles.items():
        if not name.startswith('sb'):
            continue
        fr = windscreen_frame(v['body'])
        if fr is None:
            continue
        c, nrm, w = fr
        for side, px in (('L', -0.38), ('R', 0.12)):
            piv = bpy.data.objects.new(f'{name}_wiper_{side}', None)
            col.objects.link(piv)
            piv.parent = v['root']
            piv.location = c + Vector((px * w, 0.03, 0.02)) + nrm * 0.02
            piv.rotation_mode = 'QUATERNION'
            piv.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(nrm)
            bl = 0.55 * w
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=Vector((bl, 0.018, 0.025)), verts=bm.verts)
            bmesh.ops.translate(bm, vec=Vector((bl / 2, 0, 0.012)), verts=bm.verts)
            me = bpy.data.meshes.new('WiperBlade'); bm.to_mesh(me); bm.free(); me.materials.append(blade_m)
            arm = bpy.data.objects.new(f'{name}_wiperblade_{side}', me)
            col.objects.link(arm)
            arm.parent = piv
            arm.rotation_mode = 'XYZ'
            for f in range(C.FRAME_START, C.FRAME_END + 1):
                t = (f - C.FRAME_START) / C.FPS
                ang = math.radians(80) * 0.5 * (1 - math.cos(2 * math.pi * 0.75 * t + 1.1))
                arm.rotation_euler = (0, 0, ang)
                arm.keyframe_insert('rotation_euler', index=2, frame=f)


# ------------------------------------------------------------------------- entry
def build(root, cam, vehicles, road_mat, awning_edges):
    col = collection('Rain', root)
    sm = streak_material()
    proto = streak_proto(col, sm)
    # near box: dense, where streaks are resolved; far box: sparse (haze takes over beyond)
    rain_streaks(col, cam, proto, (-7.0, -28.0, 0.0), (13.0, -6.0, 9.0), 22000, 11, 'RainNear')
    rain_streaks(col, cam, proto, (-12.0, -6.0, 0.0), (14.0, 40.0, 16.0), 18000, 23, 'RainFar')
    awning_drips(col, cam, streak_proto(col, sm, name='DripProto'), awning_edges, random.Random(C.SEED + 9))
    water_surface_animation(road_mat)
    catch_basins(root)
    wet_vehicles()
    wipers(root, vehicles)
    return col
