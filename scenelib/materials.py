"""Material library. PBR maps from Poly Haven, mapped with BOX projection in object space so
nothing needs UVs and every surface keeps real-world texel scale (metres).

All surface materials route roughness / base colour through a shared 'Wetness' node group so the
wet look is consistent and tunable in one place (see wet_layer()).
"""
import os
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PH = os.path.join(ROOT, 'assets', 'polyhaven')


def _img(path, colour):
    name = os.path.basename(path)
    im = bpy.data.images.get(name)
    if im is None:
        im = bpy.data.images.load(path, check_existing=True)
        im.filepath = bpy.path.relpath(path) if bpy.data.filepath else path
    im.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    return im


def tex_paths(tid):
    d = os.path.join(PH, tid)
    out = {}
    for f in os.listdir(d):
        key = f[len(tid) + 1:].split('_')[0]           # diffuse / rough / nor / displacement / ao
        out[key] = os.path.join(d, f)
    return out


def new(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def pbr(name, tid, size_m, tint=(1, 1, 1), tint_var=0.0, rough_mul=1.0, normal_strength=1.0,
        box_blend=0.2, coord='Object', bump_disp=0.0, porosity=1.0, coat_rough=0.07):
    """Image-based PBR material. size_m: real-world width (m) covered by one texture tile.
    tint_var: per-object random brightness/hue variation (uses Object Info > Random)."""
    m, n, l = new(name)
    p = tex_paths(tid)
    bsdf = n['Principled BSDF']
    tc = n.new('ShaderNodeTexCoord')
    mp = n.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / size_m,) * 3
    l.new(tc.outputs[coord], mp.inputs['Vector'])

    def tex(key, colour):
        t = n.new('ShaderNodeTexImage')
        t.image = _img(p[key], colour)
        t.projection = 'BOX'
        t.projection_blend = box_blend
        l.new(mp.outputs['Vector'], t.inputs['Vector'])
        return t
    dif = tex('diffuse', True)
    col = dif.outputs['Color']
    if tint != (1, 1, 1) or tint_var:
        mix = n.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        l.new(col, mix.inputs['A'])
        if tint_var:
            oi = n.new('ShaderNodeObjectInfo')
            ramp = n.new('ShaderNodeValToRGB')
            c0 = [max(0, t * (1 - tint_var)) for t in tint]
            c1 = [min(2, t * (1 + tint_var)) for t in tint]
            ramp.color_ramp.elements[0].color = (*c0, 1)
            ramp.color_ramp.elements[1].color = (*c1, 1)
            l.new(oi.outputs['Random'], ramp.inputs['Fac'])
            l.new(ramp.outputs['Color'], mix.inputs['B'])
        else:
            mix.inputs['B'].default_value = (*tint, 1)
        col = mix.outputs['Result']
    rough = tex('rough', False).outputs['Color']
    if rough_mul != 1.0:
        mm = n.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'
        mm.inputs[1].default_value = rough_mul
        l.new(rough, mm.inputs[0]); rough = mm.outputs[0]
    nt = tex('nor', False)
    nm = n.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = normal_strength
    l.new(nt.outputs['Color'], nm.inputs['Color'])
    normal = nm.outputs['Normal']
    if bump_disp and 'displacement' in p:
        dt = tex('displacement', False)
        bp = n.new('ShaderNodeBump'); bp.inputs['Distance'].default_value = bump_disp
        bp.inputs['Strength'].default_value = 1.0
        l.new(dt.outputs['Color'], bp.inputs['Height']); l.new(normal, bp.inputs['Normal'])
        normal = bp.outputs['Normal']
    wet_layer(m, col, rough, normal, porosity)
    m.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = coat_rough
    return m


def wet_layer(m, col, rough, normal, porosity=1.0):
    """Connect base colour / roughness / normal into the BSDF through the shared Wetness group:
    wet surfaces get darker (porous materials absorb water), much smoother, plus a thin clear
    water film (coat, IOR 1.33). Wetness amount lives in the group so it can be tuned globally."""
    n, l = m.node_tree.nodes, m.node_tree.links
    g = n.new('ShaderNodeGroup'); g.node_tree = wetness_group()
    g.inputs['Porosity'].default_value = porosity
    l.new(col, g.inputs['Color'])
    l.new(rough, g.inputs['Roughness'])
    b = n['Principled BSDF']
    l.new(g.outputs['Color'], b.inputs['Base Color'])
    l.new(g.outputs['Roughness'], b.inputs['Roughness'])
    l.new(g.outputs['Coat'], b.inputs['Coat Weight'])
    b.inputs['Coat IOR'].default_value = 1.33
    b.inputs['Coat Roughness'].default_value = 0.07
    l.new(normal, b.inputs['Normal'])


def wetness_group():
    g = bpy.data.node_groups.get('Wetness')
    if g:
        return g
    g = bpy.data.node_groups.new('Wetness', 'ShaderNodeTree')
    io = g.interface
    io.new_socket('Color', in_out='INPUT', socket_type='NodeSocketColor')
    io.new_socket('Roughness', in_out='INPUT', socket_type='NodeSocketFloat')
    s = io.new_socket('Porosity', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 1.0
    s = io.new_socket('Wet', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = -1.0
    io.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    io.new_socket('Roughness', in_out='OUTPUT', socket_type='NodeSocketFloat')
    io.new_socket('Coat', in_out='OUTPUT', socket_type='NodeSocketFloat')
    n, l = g.nodes, g.links
    gi = n.new('NodeGroupInput'); go = n.new('NodeGroupOutput')
    wet = n.new('ShaderNodeValue'); wet.name = 'WET_AMOUNT'; wet.label = 'Global wetness 0..1'
    wet.outputs[0].default_value = 0.0          # greybox/asset stages: dry
    # darkening: colour^(1 + 0.6*wet*porosity) * (1 - 0.25*wet*porosity)  (Lekner & Dorf style)
    k = n.new('ShaderNodeMath'); k.operation = 'MULTIPLY'
    l.new(wet.outputs[0], k.inputs[0]); l.new(gi.outputs['Porosity'], k.inputs[1])
    ex = n.new('ShaderNodeMath'); ex.operation = 'MULTIPLY_ADD'
    ex.inputs[1].default_value = 0.6; ex.inputs[2].default_value = 1.0
    l.new(k.outputs[0], ex.inputs[0])
    gam = n.new('ShaderNodeGamma')
    l.new(gi.outputs['Color'], gam.inputs['Color']); l.new(ex.outputs[0], gam.inputs['Gamma'])
    dk = n.new('ShaderNodeMath'); dk.operation = 'MULTIPLY_ADD'
    dk.inputs[1].default_value = -0.25; dk.inputs[2].default_value = 1.0
    l.new(k.outputs[0], dk.inputs[0])
    mul = n.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    l.new(gam.outputs['Color'], mul.inputs['A'])
    cmb = n.new('ShaderNodeCombineColor')
    for i in range(3):
        l.new(dk.outputs[0], cmb.inputs[i])
    l.new(cmb.outputs['Color'], mul.inputs['B'])
    l.new(mul.outputs['Result'], go.inputs['Color'])
    # orientation: rain soaks horizontal surfaces into a film; vertical ones just darken/gloss a bit
    geo = n.new('ShaderNodeNewGeometry')
    sz = n.new('ShaderNodeSeparateXYZ'); l.new(geo.outputs['Normal'], sz.inputs['Vector'])
    hz = n.new('ShaderNodeMapRange')
    hz.inputs['From Min'].default_value = 0.7; hz.inputs['From Max'].default_value = 0.95
    l.new(sz.outputs['Z'], hz.inputs['Value'])
    # roughness factor: vertical 0.6x, horizontal 0.3x (water fills the micro-texture)
    fac = n.new('ShaderNodeMapRange')
    fac.inputs['To Min'].default_value = 0.6; fac.inputs['To Max'].default_value = 0.3
    l.new(hz.outputs['Result'], fac.inputs['Value'])
    r2 = n.new('ShaderNodeMath'); r2.operation = 'MULTIPLY'
    l.new(gi.outputs['Roughness'], r2.inputs[0]); l.new(fac.outputs['Result'], r2.inputs[1])
    lr = n.new('ShaderNodeMix'); lr.data_type = 'FLOAT'
    l.new(wet.outputs[0], lr.inputs['Factor'])
    l.new(gi.outputs['Roughness'], lr.inputs['A']); l.new(r2.outputs[0], lr.inputs['B'])
    l.new(lr.outputs['Result'], go.inputs['Roughness'])
    # water film (coat): only on near-horizontal surfaces, partial (the aggregate pokes through)
    c = n.new('ShaderNodeMath'); c.operation = 'MULTIPLY'; c.inputs[1].default_value = 0.35
    l.new(wet.outputs[0], c.inputs[0])
    c2 = n.new('ShaderNodeMath'); c2.operation = 'MULTIPLY'
    l.new(c.outputs[0], c2.inputs[0]); l.new(hz.outputs['Result'], c2.inputs[1])
    c3 = n.new('ShaderNodeMath'); c3.operation = 'MULTIPLY'
    l.new(c2.outputs[0], c3.inputs[0]); l.new(gi.outputs['Porosity'], c3.inputs[1])
    l.new(c3.outputs[0], go.inputs['Coat'])
    return g


def set_wetness(v):
    wetness_group().nodes['WET_AMOUNT'].outputs[0].default_value = v


def simple(name, color, rough=0.5, metal=0.0, rough_var=0.0, porosity=0.5, coat=None):
    """Untextured material with optional noise roughness variation, still routed through Wetness."""
    m, n, l = new(name)
    b = n['Principled BSDF']
    b.inputs['Metallic'].default_value = metal
    rgb = n.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (*color, 1)
    rv = n.new('ShaderNodeValue'); rv.outputs[0].default_value = rough
    r = rv.outputs[0]
    if rough_var:
        nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0
        nz.inputs['Detail'].default_value = 6
        mr = n.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = max(0.02, rough - rough_var)
        mr.inputs['To Max'].default_value = min(1, rough + rough_var)
        l.new(nz.outputs['Fac'], mr.inputs['Value']); r = mr.outputs['Result']
    nrm = n.new('ShaderNodeNewGeometry')
    wet_layer(m, rgb.outputs[0], r, nrm.outputs['Normal'], porosity)
    m.diffuse_color = (*color, 1)
    return m


def emissive(name, color, strength, base=(0.02, 0.02, 0.02)):
    m, n, l = new(name)
    b = n['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Emission Color'].default_value = (*color, 1)
    b.inputs['Emission Strength'].default_value = strength
    b.inputs['Roughness'].default_value = 0.3
    return m


def glass(name, tint=(0.9, 0.92, 0.92), rough=0.02):
    m, n, l = new(name)
    b = n['Principled BSDF']
    b.inputs['Base Color'].default_value = (*tint, 1)
    b.inputs['Transmission Weight'].default_value = 1.0
    b.inputs['IOR'].default_value = 1.5
    b.inputs['Roughness'].default_value = rough
    return m


def blackbody_rgb(kelvin):
    """Approximate sRGB-linear colour of a blackbody (good enough for lamp colours 1500-10000 K)."""
    import math
    t = kelvin / 100.0
    if t <= 66:
        r = 255
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255
    c = [min(max(v, 0), 255) / 255 for v in (r, g, b)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def weather_facade(m, streak_amt=0.35, base_amt=0.3):
    """Facade weathering on top of an existing wet-layer material (object/world space, m):
      * rain-runoff streaks: vertical, stretched noise (dirt washed down from sills/cornices)
      * splash zone: lowest ~0.6 m darker and wetter (rain splash-back, de-icing salt, grime)
      * slight soot darkening towards the top (traffic pollution deposits on ledges)"""
    n, l = m.node_tree.nodes, m.node_tree.links
    grp = next(x for x in n if x.type == 'GROUP' and x.node_tree.name == 'Wetness')
    col_in = grp.inputs['Color'].links[0].from_socket
    tc = n.new('ShaderNodeTexCoord')
    vm = n.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'
    vm.inputs[1].default_value = (7.0, 7.0, 0.18)                 # vertical streaks
    l.new(tc.outputs['Object'], vm.inputs[0])
    nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.0
    nz.inputs['Detail'].default_value = 3.0
    l.new(vm.outputs[0], nz.inputs['Vector'])
    st = n.new('ShaderNodeMapRange')
    st.inputs['From Min'].default_value = 0.5; st.inputs['From Max'].default_value = 0.7
    st.inputs['To Min'].default_value = 0.0; st.inputs['To Max'].default_value = streak_amt
    l.new(nz.outputs['Fac'], st.inputs['Value'])
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    base = n.new('ShaderNodeMapRange')
    base.inputs['From Min'].default_value = 0.2; base.inputs['From Max'].default_value = 0.8
    base.inputs['To Min'].default_value = base_amt; base.inputs['To Max'].default_value = 0.0
    l.new(sep.outputs['Z'], base.inputs['Value'])
    tot = n.new('ShaderNodeMath'); tot.operation = 'ADD'; tot.use_clamp = True
    l.new(st.outputs['Result'], tot.inputs[0]); l.new(base.outputs['Result'], tot.inputs[1])
    mix = n.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    l.new(tot.outputs[0], mix.inputs['Factor'])
    l.new(col_in, mix.inputs['A']); mix.inputs['B'].default_value = (0.42, 0.38, 0.33, 1)
    l.new(mix.outputs['Result'], grp.inputs['Color'])
    # splash zone is wetter: lower roughness
    r_in = grp.inputs['Roughness'].links[0].from_socket if grp.inputs['Roughness'].links else None
    if r_in is not None:
        rm = n.new('ShaderNodeMath'); rm.operation = 'MULTIPLY'
        inv = n.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        l.new(base.outputs['Result'], inv.inputs[1])
        l.new(r_in, rm.inputs[0]); l.new(inv.outputs[0], rm.inputs[1])
        l.new(rm.outputs[0], grp.inputs['Roughness'])
    return m
