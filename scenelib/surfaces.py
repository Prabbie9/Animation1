"""Ground surfaces: asphalt (with puddles and gutter water), sidewalk slabs, kerbs, road paint.

Physical basis for the wet look:
  * a continuous water film makes asphalt nearly specular (roughness ~0.05-0.15 where it is thin,
    ~0.01 in standing puddles) and darkens it (light trapped by total internal reflection)
  * roads are crowned (~2 % cross-fall) so water collects along the kerbs (gutters) and in
    shallow depressions; puddles are therefore biased towards the kerb lines and wheel ruts
  * Fresnel is handled by the BSDF (IOR 1.33 water coat), so grazing reflections are strong
"""
import bpy
from . import config as C
from . import materials as M


def asphalt():
    m = M.pbr('Asphalt_wet', 'asphalt_02', 3.5, tint=(0.9, 0.9, 0.9), normal_strength=0.6)
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n['Principled BSDF']
    g = next(x for x in n if x.type == 'GROUP')
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    # gutter band: water within ~0.5 m of the avenue kerbs and the cross-street kerbs
    def band(axis, half):
        ab = n.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; l.new(sep.outputs[axis], ab.inputs[0])
        d = n.new('ShaderNodeMath'); d.operation = 'SUBTRACT'; d.inputs[1].default_value = half
        l.new(ab.outputs[0], d.inputs[0])
        d2 = n.new('ShaderNodeMath'); d2.operation = 'ABSOLUTE'; l.new(d.outputs[0], d2.inputs[0])
        mr = n.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 0.08; mr.inputs['From Max'].default_value = 0.45
        mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
        l.new(d2.outputs[0], mr.inputs['Value'])
        return mr.outputs['Result']
    gx = band('X', C.AVE_HALF)
    gy = band('Y', C.CROSS_HALF)
    gut = n.new('ShaderNodeMath'); gut.operation = 'MAXIMUM'
    l.new(gx, gut.inputs[0]); l.new(gy, gut.inputs[1])
    # depressions: low-frequency noise, thresholded; plus wheel-rut streaks along the avenue
    nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.12
    nz.inputs['Detail'].default_value = 5.0; nz.inputs['Roughness'].default_value = 0.6
    l.new(tc.outputs['Object'], nz.inputs['Vector'])
    pud = n.new('ShaderNodeMapRange')
    pud.inputs['From Min'].default_value = 0.63; pud.inputs['From Max'].default_value = 0.66
    l.new(nz.outputs['Fac'], pud.inputs['Value'])
    tot = n.new('ShaderNodeMath'); tot.operation = 'MAXIMUM'
    l.new(gut.outputs[0], tot.inputs[0]); l.new(pud.outputs['Result'], tot.inputs[1])
    puddle = n.new('ShaderNodeValue'); puddle.name = 'PUDDLE_AMOUNT'; puddle.outputs[0].default_value = 1.0
    pm = n.new('ShaderNodeMath'); pm.operation = 'MULTIPLY'
    l.new(tot.outputs[0], pm.inputs[0]); l.new(puddle.outputs[0], pm.inputs[1])
    # roughness: film everywhere (via the Wetness group) and mirror-like in puddles
    rmix = n.new('ShaderNodeMix'); rmix.data_type = 'FLOAT'
    l.new(pm.outputs[0], rmix.inputs['Factor'])
    l.new(g.outputs['Roughness'], rmix.inputs['A']); rmix.inputs['B'].default_value = 0.015
    l.new(rmix.outputs['Result'], b.inputs['Roughness'])
    # standing water hides the texture normal
    nrm = next(lk.from_socket for lk in m.node_tree.links if lk.to_node == b and lk.to_socket.name == 'Normal')
    geo = n.new('ShaderNodeNewGeometry')
    nmix = n.new('ShaderNodeMix'); nmix.data_type = 'VECTOR'
    l.new(pm.outputs[0], nmix.inputs['Factor'])
    l.new(nrm, nmix.inputs[4]); l.new(geo.outputs['Normal'], nmix.inputs[5])
    l.new(nmix.outputs[1], b.inputs['Normal'])
    # puddles: darker base (water absorbs / deeper saturation)
    cm = n.new('ShaderNodeMix'); cm.data_type = 'RGBA'; cm.blend_type = 'MULTIPLY'
    l.new(pm.outputs[0], cm.inputs['Factor'])
    l.new(g.outputs['Color'], cm.inputs['A']); cm.inputs['B'].default_value = (0.55, 0.55, 0.55, 1)
    l.new(cm.outputs['Result'], b.inputs['Base Color'])
    m['puddles'] = True
    return m


def apply(root):
    road = asphalt()
    walk = M.pbr('Sidewalk_wet', 'concrete_pavement', 3.0, tint=(0.85, 0.85, 0.83), tint_var=0.0,
                 normal_strength=0.7, porosity=0.55, coat_rough=0.22)
    white = M.simple('Paint_white', (0.62, 0.62, 0.58), 0.45, rough_var=0.15, porosity=0.2)
    yellow = M.simple('Paint_yellow', (0.62, 0.42, 0.05), 0.45, rough_var=0.15, porosity=0.2)
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials:
            continue
        mn = o.data.materials[0].name if o.data.materials[0] else ''
        rep = {'GB_road': road, 'GB_sidewalk': walk, 'GB_paint_white': white, 'GB_paint_yellow': yellow}.get(mn)
        if rep:
            o.data.materials[0] = rep
    return road
