"""Night lighting. Photometric convention used throughout (so relative levels are physical):

    1 W (Blender radiant)  == 683 lm          (white light treated as 555 nm equivalent)
    emission strength S    == S * 683 cd/m2   (luminance of a surface seen directly)

Real-world references used to set levels:
    LED cobra-head street light   ~12 000 lm, 4000 K, 9 m mounting      -> avenue
    HPS (sodium) 150 W            ~16 000 lm, 2050 K                     -> cross street
    overcast urban sky glow       ~0.15 cd/m2, orange-grey               -> world
    lit room seen through window  ~20-80 cd/m2
    LED traffic signal lens       ~5 000-12 000 cd/m2
    car low beam                  ~1 000 lm per lamp, sharp cutoff ~1 deg below horizontal
    tail lamp ~300 cd/m2, brake lamp ~3 000 cd/m2
The camera is then exposed for the wet asphalt, like a real night shoot.
"""
import math
import os
import bpy
from mathutils import Vector
from . import config as C
from . import materials as M
from .util import collection, cylinder, box

LM_PER_W = 683.0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AVENUE_K = 4000      # LED retrofit on the avenue
CROSS_K = 2050       # high-pressure sodium on the cross street


def nits(cd_m2):
    return cd_m2 / LM_PER_W


def spot_watts(lumens, cone_deg):
    """Blender spot power is specified as if it were an omni point light."""
    omega = 2 * math.pi * (1 - math.cos(math.radians(cone_deg / 2)))
    return lumens / LM_PER_W * 4 * math.pi / omega


# ---------------------------------------------------------------------------------- world
SKY_ZENITH_NITS = 0.08     # overhead: cool grey cloud base, weakly lit
SKY_HORIZON_NITS = 0.22    # towards the horizon: cloud underside lit by the city (sky glow)
SKY_ZENITH_RGB = (0.78, 0.84, 0.95)
SKY_HORIZON_RGB = (1.0, 0.86, 0.72)


def world(sc):
    """Overcast night sky lit from below by the city. Colour and level come from a physical-ish
    gradient: brighter and warmer near the horizon (where the cloud base sees more of the lit
    city), cooler and darker overhead. The HDRI only contributes cloud *texture* (desaturated,
    clamped, normalised to mean 1) so its own colour/lamps don't leak in."""
    w = bpy.data.worlds.new('NightSky')
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    bg = n['Background']
    env = n.new('ShaderNodeTexEnvironment')
    path = os.path.join(ROOT, 'assets', 'polyhaven', 'hdri', 'kloppenheim_04_2k.exr')
    env.image = bpy.data.images.load(path, check_existing=True)
    tc = n.new('ShaderNodeTexCoord'); mp = n.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(74.5))
    l.new(tc.outputs['Generated'], mp.inputs['Vector']); l.new(mp.outputs['Vector'], env.inputs['Vector'])
    bw = n.new('ShaderNodeRGBToBW'); l.new(env.outputs['Color'], bw.inputs['Color'])
    # cloud texture: HDRI luminance / its median (~0.2), clamped to 0.6..1.6
    tex = n.new('ShaderNodeMapRange')
    tex.inputs['From Min'].default_value = 0.0; tex.inputs['From Max'].default_value = 0.4
    tex.inputs['To Min'].default_value = 0.6; tex.inputs['To Max'].default_value = 1.6
    l.new(bw.outputs['Val'], tex.inputs['Value'])
    # elevation gradient (direction z: 0 at horizon, 1 at zenith)
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Generated'], sep.inputs['Vector'])
    el = n.new('ShaderNodeMapRange')
    el.inputs['From Min'].default_value = 0.0; el.inputs['From Max'].default_value = 0.55
    el.interpolation_type = 'SMOOTHSTEP'
    l.new(sep.outputs['Z'], el.inputs['Value'])
    hz = [c * nits(SKY_HORIZON_NITS) for c in SKY_HORIZON_RGB]
    zn = [c * nits(SKY_ZENITH_NITS) for c in SKY_ZENITH_RGB]
    grad = n.new('ShaderNodeMix'); grad.data_type = 'RGBA'
    l.new(el.outputs['Result'], grad.inputs['Factor'])
    grad.inputs['A'].default_value = (*hz, 1); grad.inputs['B'].default_value = (*zn, 1)
    mul = n.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    l.new(grad.outputs['Result'], mul.inputs['A']); l.new(tex.outputs['Result'], mul.inputs['B'])
    l.new(mul.outputs['Result'], bg.inputs['Color'])
    st = n.new('ShaderNodeValue'); st.name = 'SKY_STRENGTH'; st.outputs[0].default_value = 1.0
    l.new(st.outputs[0], bg.inputs['Strength'])
    sc.world = w
    return w


# ---------------------------------------------------------------------------------- lamps
def luminaire_lens_material(name, kelvin, lumens):
    """Emissive lens seen directly by the camera only (the spot light does the lighting and
    the glossy reflections, so nothing is counted twice)."""
    # lens ~0.18 m2; luminance = lm / (pi * area) for a Lambertian approximation, LED lenses are
    # far brighter in their main direction -- clamp to a value that still blooms realistically.
    lum = min(lumens / (math.pi * 0.18), 60000)
    return M.emissive(name, M.blackbody_rgb(kelvin), nits(lum), base=(0.6, 0.6, 0.6))


def cobra_head(col, name, pos, heading, kelvin, lumens, steel, housing):
    """Cobra-head luminaire at pos (lens centre) pointing along heading (radians, the arm's
    direction). Spot light 150 deg cone, slightly tilted towards the road (Type III-ish)."""
    x, y, z = pos
    hx, hy = math.cos(heading), math.sin(heading)
    # housing: tapered shell approximated by two boxes
    hb = box(name + '_housing', col, (0.78, 0.34, 0.16), (x, y, z), housing, rot_z=heading)
    hb2 = box(name + '_neck', col, (0.3, 0.2, 0.12), (x - hx * 0.45, y - hy * 0.45, z + 0.02), housing,
              rot_z=heading)
    # lens: one downward-facing quad (a box would emit from its top and sides as well)
    lm = bpy.data.materials.get(f'Lens_{kelvin}K') or luminaire_lens_material(f'Lens_{kelvin}K', kelvin, lumens)
    lm.cycles.emission_sampling = 'NONE'      # camera-visible only; the spot light does the lighting
    ca, sa = math.cos(heading), math.sin(heading)
    pts = []
    for du, dv in ((-0.3, 0.14), (0.3, 0.14), (0.3, -0.14), (-0.3, -0.14)):   # clockwise from above -> normal down
        pts.append((x + du * ca - dv * sa, y + du * sa + dv * ca, z - 0.081))
    from .util import mesh_object
    lens = mesh_object(name + '_lens', pts, [(0, 1, 2, 3)], col, lm)
    lens.visible_glossy = False
    lens.visible_diffuse = False
    lens.visible_transmission = False
    lens.visible_shadow = False
    cone = 130.0     # full cut-off optic: almost nothing above ~65-70 deg from nadir
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy = spot_watts(lumens, cone) * 0.7         # ~70 % of the flux lands within the cone
    ld.color = M.blackbody_rgb(kelvin)
    ld.spot_size = math.radians(cone)
    ld.spot_blend = 0.45
    ld.shadow_soft_size = 0.2
    lo = bpy.data.objects.new(name + '_light', ld)
    col.objects.link(lo)
    lo.location = (x, y, z - 0.04)
    # tilt 12 deg towards the street side of the pole (the luminaire overhangs the road)
    lo.rotation_euler = (0, math.radians(12), heading)
    return lo


def street_lights(root):
    col = collection('StreetLights', root)
    steel = M.simple('Pole_steel', (0.18, 0.19, 0.2), 0.45, metal=0.9, rough_var=0.15, porosity=0.0)
    housing = M.simple('Luminaire_housing', (0.35, 0.36, 0.37), 0.4, metal=0.6, porosity=0.0)
    # Remove the grey-box lamp heads; keep poles + arms (re-material them)
    for o in list(bpy.data.objects):
        if o.name.startswith(('LampHead',)):
            bpy.data.objects.remove(o, do_unlink=True)
        elif o.name.startswith(('LampPole', 'LampArm', 'SigPole', 'SigArm', 'SigHanger')):
            o.data.materials.clear()
            o.data.materials.append(steel)
    lights = []
    # Avenue (LED 4000 K): same positions as the grey-box poles (layout.build_poles)
    for o in [o for o in bpy.data.objects if o.name.startswith('LampArm')]:
        x, y, z = o.location
        sx = 1 if x < 0 else -1          # arm points towards the road centre
        heading = 0.0 if sx > 0 else math.pi
        lights.append(cobra_head(col, f'AveLamp_{len(lights):02d}', (x + sx * 1.35, y, z - 0.05), heading,
                                 AVENUE_K, 12000, steel, housing))
    # Luminaire arms on the four signal mast poles, 10.5 m, over the intersection (LED, avenue spec)
    for o in [o for o in bpy.data.objects if o.name.startswith('SigPole')]:
        x, y, _ = o.location
        heading = math.atan2(-y, -x)
        ext = cylinder(o.name + '_ext', col, 0.12, 3.6, (x, y, C.KERB_H + 7.2), steel, 12)
        ax, ay = x + math.cos(heading) * 1.4, y + math.sin(heading) * 1.4
        arm = box(o.name + '_lumarm', col, (2.8, 0.08, 0.08), (ax, ay, C.KERB_H + 10.6), steel, rot_z=heading)
        lights.append(cobra_head(col, f'IxLamp_{len(lights):02d}', (x + math.cos(heading) * 2.9,
                                 y + math.sin(heading) * 2.9, C.KERB_H + 10.55), heading,
                                 AVENUE_K, 15000, steel, housing))
    # Cross street (HPS sodium 2050 K), both sides, staggered, 30 m spacing, 8 m mounting
    for sx in (1, -1):
        for i, d in enumerate((22.0, 52.0, 82.0)):
            sy = 1 if (i % 2 == 0) == (sx > 0) else -1
            px, py = sx * d, sy * (C.CROSS_HALF + 0.6)
            cylinder(f'XPole_{sx}_{i}', col, 0.09, 8.0, (px, py, C.KERB_H), steel, 12)
            heading = -math.pi / 2 if sy > 0 else math.pi / 2
            box(f'XArm_{sx}_{i}', col, (0.08, 2.0, 0.08), (px, py - sy * 1.0, C.KERB_H + 7.9), steel)
            lights.append(cobra_head(col, f'XLamp_{sx}_{i}', (px, py - sy * 2.1, C.KERB_H + 7.85), heading,
                                     CROSS_K, 16000, steel, housing))
    return lights


# ---------------------------------------------------------------------------------- vehicles
def strip_imported_emission():
    """glTF scans sometimes ship their albedo as an emissive map (e.g. the newspaper boxes),
    which makes them glow. Nothing imported should emit unless we make it."""
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.startswith(('Sign_', 'Lens_', 'SigLens_', 'Window_glass')):
            continue
        b = m.node_tree.nodes.get('Principled BSDF')
        if b is None:
            continue
        for sock in ('Emission Color', 'Emission Strength'):
            for lk in list(b.inputs[sock].links):
                m.node_tree.links.remove(lk)
        if b.inputs['Emission Strength'].default_value > 0 and not m.name.startswith(('Window_glass',)):
            b.inputs['Emission Strength'].default_value = 0.0


def fix_unlit_materials():
    """KHR_materials_unlit imports (Emission + Transparent mix) glow at night. Rebuild them as
    ordinary lit surfaces using the same texture as albedo (routed through the wet layer)."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        types = {x.type for x in nt.nodes}
        if 'EMISSION' in types and 'BSDF_PRINCIPLED' not in types and 'LIGHT_PATH' in types:
            tex = next((x for x in nt.nodes if x.type == 'TEX_IMAGE'), None)
            out = next(x for x in nt.nodes if x.type == 'OUTPUT_MATERIAL')
            for x in list(nt.nodes):
                if x not in (tex, out):
                    nt.nodes.remove(x)
            b = nt.nodes.new('ShaderNodeBsdfPrincipled')
            nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
            rv = nt.nodes.new('ShaderNodeValue'); rv.outputs[0].default_value = 0.55
            geo = nt.nodes.new('ShaderNodeNewGeometry')
            if tex is not None:
                M.wet_layer(m, tex.outputs['Color'], rv.outputs[0], geo.outputs['Normal'], porosity=0.3)


def vehicle_light_materials():
    """Add head/tail/brake emission to every vehicle material that contains lamp texels.
    Per-object switches (custom properties read via an INSTANCER attribute, so parked-car
    instances stay dark):  'head' 0/1, 'tail' 0/1, 'brake' 0..1."""
    done = set()
    for m in bpy.data.materials:
        if m.name in done or not m.use_nodes:
            continue
        nm = m.name
        is_optics = nm.startswith('Optics_')
        is_taxi = nm in ('main_frame', 'wheels_and_parts', 'glass')   # taxi lamp lenses live in 'glass'
        is_camry = nm in ('Index_0_2_SS', 'Index_0_2', 'Index_0_1')
        if not (is_optics or is_taxi or is_camry):
            continue
        done.add(nm)
        n, l = m.node_tree.nodes, m.node_tree.links
        b = n.get('Principled BSDF')
        tex = next((lk.from_node for lk in m.node_tree.links
                    if lk.to_node == b and lk.to_socket.name == 'Base Color' and lk.from_node.type == 'TEX_IMAGE'), None)
        if tex is None:
            continue
        # red lens mask in HSV: hue within ~0.04 of pure red, saturated, not black.
        # (yellow taxi paint has hue ~0.12 and is rejected.)
        hsv = n.new('ShaderNodeSeparateColor'); hsv.mode = 'HSV'
        l.new(tex.outputs['Color'], hsv.inputs['Color'])
        hsh = n.new('ShaderNodeMath'); hsh.operation = 'ADD'; hsh.inputs[1].default_value = 0.5
        l.new(hsv.outputs[0], hsh.inputs[0])
        hfr = n.new('ShaderNodeMath'); hfr.operation = 'FRACT'; l.new(hsh.outputs[0], hfr.inputs[0])
        hd = n.new('ShaderNodeMath'); hd.operation = 'SUBTRACT'; hd.inputs[1].default_value = 0.5
        l.new(hfr.outputs[0], hd.inputs[0])
        had = n.new('ShaderNodeMath'); had.operation = 'ABSOLUTE'; l.new(hd.outputs[0], had.inputs[0])
        hmask = n.new('ShaderNodeMapRange')
        hmask.inputs['From Min'].default_value = 0.03; hmask.inputs['From Max'].default_value = 0.06
        hmask.inputs['To Min'].default_value = 1.0; hmask.inputs['To Max'].default_value = 0.0
        l.new(had.outputs[0], hmask.inputs['Value'])
        smask = n.new('ShaderNodeMapRange')
        smask.inputs['From Min'].default_value = 0.55; smask.inputs['From Max'].default_value = 0.75
        l.new(hsv.outputs[1], smask.inputs['Value'])
        vmask = n.new('ShaderNodeMapRange')
        vmask.inputs['From Min'].default_value = 0.08; vmask.inputs['From Max'].default_value = 0.2
        l.new(hsv.outputs[2], vmask.inputs['Value'])
        rr = n.new('ShaderNodeMath'); rr.operation = 'MULTIPLY'
        l.new(hmask.outputs['Result'], rr.inputs[0]); l.new(smask.outputs['Result'], rr.inputs[1])
        red = n.new('ShaderNodeMath'); red.operation = 'MULTIPLY'
        l.new(rr.outputs[0], red.inputs[0]); l.new(vmask.outputs['Result'], red.inputs[1])
        # position masks in the vehicle's own space (vehicles face +Y)
        tc = n.new('ShaderNodeTexCoord')
        sxyz = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sxyz.inputs['Vector'])
        rear = n.new('ShaderNodeMath'); rear.operation = 'LESS_THAN'; rear.inputs[1].default_value = -1.2
        l.new(sxyz.outputs['Y'], rear.inputs[0])
        front = n.new('ShaderNodeMath'); front.operation = 'GREATER_THAN'; front.inputs[1].default_value = 1.2
        l.new(sxyz.outputs['Y'], front.inputs[0])
        hi = n.new('ShaderNodeMath'); hi.operation = 'GREATER_THAN'; hi.inputs[1].default_value = 0.45
        l.new(sxyz.outputs['Z'], hi.inputs[0])
        def attr(name):
            a = n.new('ShaderNodeAttribute'); a.attribute_type = 'INSTANCER'; a.attribute_name = name
            return a.outputs['Fac']
        # tail: 0.45 + brake 4.0 (relative), times rear & red mask
        # Physical lamp luminance (SAE J586/J585: brake 80-185 cd, tail 2-18 cd from a ~0.03 m2
        # lens -> peak ~4000 cd/m2 brake, ~250 cd/m2 tail). The light is concentrated in hotspots
        # behind the diffuser (bulb/LED cores), so the emissive area follows the lens texture's
        # brightness instead of filling the whole red region uniformly.
        bn = n.new('ShaderNodeValue'); bn.name = 'BRAKE_NITS'; bn.outputs[0].default_value = nits(4000)
        tn = n.new('ShaderNodeValue'); tn.name = 'TAIL_NITS'; tn.outputs[0].default_value = nits(250)
        tb = n.new('ShaderNodeMath'); tb.operation = 'MULTIPLY_ADD'
        l.new(attr('brake'), tb.inputs[0]); l.new(bn.outputs[0], tb.inputs[1])
        tl = n.new('ShaderNodeMath'); tl.operation = 'MULTIPLY'
        l.new(attr('tail'), tl.inputs[0]); l.new(tn.outputs[0], tl.inputs[1])
        l.new(tl.outputs[0], tb.inputs[2])
        hot = n.new('ShaderNodeMapRange'); hot.name = 'LAMP_HOTSPOT'
        hot.inputs['From Min'].default_value = 0.05; hot.inputs['From Max'].default_value = 0.35
        hot.inputs['To Min'].default_value = 0.0; hot.inputs['To Max'].default_value = 1.0
        hot.interpolation_type = 'SMOOTHERSTEP'
        l.new(hsv.outputs[2], hot.inputs['Value'])
        tbh = n.new('ShaderNodeMath'); tbh.operation = 'MULTIPLY'
        l.new(tb.outputs[0], tbh.inputs[0]); l.new(hot.outputs['Result'], tbh.inputs[1])
        tb = tbh
        rm = n.new('ShaderNodeMath'); rm.operation = 'MULTIPLY'
        l.new(red.outputs[0], rm.inputs[0]); l.new(rear.outputs[0], rm.inputs[1])
        rm2 = n.new('ShaderNodeMath'); rm2.operation = 'MULTIPLY'
        l.new(rm.outputs[0], rm2.inputs[0]); l.new(hi.outputs[0], rm2.inputs[1])
        rstr = n.new('ShaderNodeMath'); rstr.operation = 'MULTIPLY'
        l.new(rm2.outputs[0], rstr.inputs[0]); l.new(tb.outputs[0], rstr.inputs[1])
        # headlights: bright, low-saturation texels at the front (lens/reflector areas)
        lum = n.new('ShaderNodeRGBToBW'); l.new(tex.outputs['Color'], lum.inputs['Color'])
        wh = n.new('ShaderNodeMapRange')
        wh.inputs['From Min'].default_value = 0.10; wh.inputs['From Max'].default_value = 0.28
        l.new(lum.outputs['Val'], wh.inputs['Value'])
        hm = n.new('ShaderNodeMath'); hm.operation = 'MULTIPLY'
        l.new(wh.outputs['Result'], hm.inputs[0]); l.new(front.outputs[0], hm.inputs[1])
        lowsat = n.new('ShaderNodeMapRange')
        lowsat.inputs['From Min'].default_value = 0.15; lowsat.inputs['From Max'].default_value = 0.3
        lowsat.inputs['To Min'].default_value = 1.0 if is_optics else 0.0
        lowsat.inputs['To Max'].default_value = 0.0
        l.new(hsv.outputs[1], lowsat.inputs['Value'])
        hmo = n.new('ShaderNodeMath'); hmo.operation = 'MULTIPLY'
        l.new(hm.outputs[0], hmo.inputs[0]); l.new(lowsat.outputs['Result'], hmo.inputs[1])
        hm2 = n.new('ShaderNodeMath'); hm2.operation = 'MULTIPLY'
        l.new(hmo.outputs[0], hm2.inputs[0]); l.new(attr('head'), hm2.inputs[1])
        hstr = n.new('ShaderNodeMath'); hstr.operation = 'MULTIPLY'; hstr.inputs[1].default_value = nits(40000)
        l.new(hm2.outputs[0], hstr.inputs[0])
        # combine: colour = red where tail, warm white where head
        tot = n.new('ShaderNodeMath'); tot.operation = 'ADD'
        l.new(rstr.outputs[0], tot.inputs[0]); l.new(hstr.outputs[0], tot.inputs[1])
        mixc = n.new('ShaderNodeMix'); mixc.data_type = 'RGBA'
        l.new(front.outputs[0], mixc.inputs['Factor'])
        mixc.inputs['A'].default_value = (1.0, 0.0, 0.0, 1)   # sRGB gamut edge; real lamps are even more saturated
        mixc.inputs['B'].default_value = (*M.blackbody_rgb(5000), 1)
        l.new(mixc.outputs['Result'], b.inputs['Emission Color'])
        l.new(tot.outputs[0], b.inputs['Emission Strength'])


def taxi_roof_sign():
    """Roof sign lit (cab available): back-lit translucent panel ~250 cd/m2."""
    m = bpy.data.materials.get('taxi_sign')
    if not m:
        return
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n['Principled BSDF']
    tex = next((lk.from_node for lk in m.node_tree.links if lk.to_node == b and lk.to_socket.name == 'Base Color'), None)
    if tex is not None:
        l.new(tex.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = nits(250)


def headlight_beam(col, name, parent, local, kelvin=5000, lumens=1000):
    """Low beam: spot light whose node tree cuts everything above ~1 deg below horizontal
    (sharp cutoff) and fades the horizontal spread, parented to the vehicle."""
    ld = bpy.data.lights.new(name, 'SPOT')
    cone = 80.0
    ld.energy = spot_watts(lumens, cone)
    ld.color = M.blackbody_rgb(kelvin)
    ld.spot_size = math.radians(cone)
    ld.spot_blend = 0.3
    ld.shadow_soft_size = 0.05
    ld.use_nodes = True
    n, l = ld.node_tree.nodes, ld.node_tree.links
    em = n['Emission']
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Normal'], sep.inputs['Vector'])
    # light local frame: -Z forward, +Y up (set by the rotation below). Cut-off: y < -0.017
    cut = n.new('ShaderNodeMapRange')
    cut.inputs['From Min'].default_value = -0.03; cut.inputs['From Max'].default_value = -0.012
    cut.inputs['To Min'].default_value = 1.0; cut.inputs['To Max'].default_value = 0.04
    l.new(sep.outputs['Y'], cut.inputs['Value'])
    l.new(cut.outputs['Result'], em.inputs['Strength'])
    o = bpy.data.objects.new(name, ld)
    col.objects.link(o)
    o.parent = parent
    o.location = local
    # point along +Y of the vehicle, 1.5 deg down; local +Y of the light = up
    o.rotation_euler = (math.radians(90 - 1.5), 0, math.pi)
    return o


VEHICLE_LAMPS = {
    # key: (headlamp x, y-from-front, z)
    'taxi_cvpi': (0.62, 0.25, 0.68), 'camry': (0.66, 0.30, 0.72), 'car_sedan': (0.62, 0.2, 0.66),
    'car_suv': (0.70, 0.2, 0.92), 'car_minivan': (0.68, 0.25, 0.85), 'car_hatch': (0.60, 0.2, 0.7),
    'car_wagon': (0.64, 0.2, 0.7), 'car_pickup': (0.70, 0.2, 0.9),
}


def vehicles(root, vehicles, sizes):
    """Lights on for the moving/stopped traffic. Stopped at a red light: brake held on."""
    col = collection('VehicleLights', root)
    strip_imported_emission()
    fix_unlit_materials()
    vehicle_light_materials()
    taxi_roof_sign()
    for name, v in vehicles.items():
        key = v['key']
        body, root_o = v['body'], v['root']
        for o in (body, root_o):
            o['head'] = 1.0
            o['tail'] = 1.0
            o['brake'] = 1.0
        L = sizes[key][1]
        hx, hy, hz = VEHICLE_LAMPS[key]
        v['beams'] = [headlight_beam(col, f'{name}_beam_{s}', root_o, (s * hx, L / 2 - hy, hz))
                      for s in (-1, 1)]


# ---------------------------------------------------------------------------------- camera / look
def colour_management(sc, exposure):
    vs = sc.view_settings
    sc.display_settings.display_device = 'sRGB'
    vs.view_transform = 'AgX'
    try:
        vs.look = 'AgX - Medium Low Contrast'
    except TypeError:
        vs.look = 'None'
    vs.exposure = exposure
    vs.gamma = 1.0
    sc.sequencer_colorspace_settings.name = 'sRGB'


# ---------------------------------------------------------------------------------- skyline / haze
def skyline():
    """Distant towers (layout's Sky_* blocks): dark facades with a procedural window grid,
    ~25 % lit, plus red aviation obstruction lights on the tallest. Seen through haze only."""
    m, n, l = M.new('Skyline')
    b = n['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.02, 0.02, 0.022, 1)
    b.inputs['Roughness'].default_value = 0.5
    tc = n.new('ShaderNodeTexCoord')
    sep = n.new('ShaderNodeSeparateXYZ'); l.new(tc.outputs['Object'], sep.inputs['Vector'])
    def cell(axis_expr, size):
        d = n.new('ShaderNodeMath'); d.operation = 'DIVIDE'; d.inputs[1].default_value = size
        l.new(axis_expr, d.inputs[0])
        return d.outputs[0]
    xy = n.new('ShaderNodeMath'); xy.operation = 'ADD'
    l.new(sep.outputs['X'], xy.inputs[0]); l.new(sep.outputs['Y'], xy.inputs[1])
    u = cell(xy.outputs[0], 3.0); v = cell(sep.outputs['Z'], 3.6)
    fu = n.new('ShaderNodeMath'); fu.operation = 'FLOOR'; l.new(u, fu.inputs[0])
    fv = n.new('ShaderNodeMath'); fv.operation = 'FLOOR'; l.new(v, fv.inputs[0])
    cv = n.new('ShaderNodeCombineXYZ'); l.new(fu.outputs[0], cv.inputs['X']); l.new(fv.outputs[0], cv.inputs['Y'])
    oi = n.new('ShaderNodeObjectInfo'); l.new(oi.outputs['Random'], cv.inputs['Z'])
    wn = n.new('ShaderNodeTexWhiteNoise'); l.new(cv.outputs['Vector'], wn.inputs['Vector'])
    lit = n.new('ShaderNodeMath'); lit.operation = 'GREATER_THAN'; lit.inputs[1].default_value = 0.75
    l.new(wn.outputs['Value'], lit.inputs[0])
    # window opening inside each cell
    ru = n.new('ShaderNodeMath'); ru.operation = 'FRACT'; l.new(u, ru.inputs[0])
    rv = n.new('ShaderNodeMath'); rv.operation = 'FRACT'; l.new(v, rv.inputs[0])
    def inside(x, a, bnd):
        g1 = n.new('ShaderNodeMath'); g1.operation = 'GREATER_THAN'; g1.inputs[1].default_value = a
        l.new(x, g1.inputs[0])
        g2 = n.new('ShaderNodeMath'); g2.operation = 'LESS_THAN'; g2.inputs[1].default_value = bnd
        l.new(x, g2.inputs[0])
        mm = n.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'
        l.new(g1.outputs[0], mm.inputs[0]); l.new(g2.outputs[0], mm.inputs[1])
        return mm.outputs[0]
    win = n.new('ShaderNodeMath'); win.operation = 'MULTIPLY'
    l.new(inside(ru.outputs[0], 0.15, 0.85), win.inputs[0]); l.new(inside(rv.outputs[0], 0.25, 0.8), win.inputs[1])
    e = n.new('ShaderNodeMath'); e.operation = 'MULTIPLY'
    l.new(win.outputs[0], e.inputs[0]); l.new(lit.outputs[0], e.inputs[1])
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*M.blackbody_rgb(2800), 1)
    ramp.color_ramp.elements[1].color = (*M.blackbody_rgb(5000), 1)
    l.new(wn.outputs['Color'], ramp.inputs['Fac'])
    l.new(ramp.outputs['Color'], b.inputs['Emission Color'])
    st = n.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = nits(25)
    l.new(e.outputs[0], st.inputs[0]); l.new(st.outputs[0], b.inputs['Emission Strength'])
    for o in bpy.data.objects:
        if o.name.startswith('Sky_'):
            o.data.materials.clear(); o.data.materials.append(m)
    # aviation obstruction lights (steady red, FAA L-810) on the tallest towers
    red = M.emissive('AviationRed', (1, 0.02, 0.01), nits(2500))
    towers = sorted([o for o in bpy.data.objects if o.name.startswith('Sky_')],
                    key=lambda o: -o.dimensions.z)[:5]
    for i, o in enumerate(towers):
        x, y, _ = o.location
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(x, y, o.dimensions.z + 0.6))
        s_ = bpy.context.active_object; s_.name = f'AviationLight_{i}'
        s_.data.materials.append(red)


def haze_compositor(sc):
    """Cheap atmosphere: mist pass (camera depth) blends towards a warm sky-glow colour.
    A light-rain night has ~1-3 km visibility; start 25 m, full effect at 600 m."""
    sc.view_layers[0].use_pass_mist = True
    w = sc.world
    w.mist_settings.start = 25.0
    w.mist_settings.depth = 600.0
    w.mist_settings.falloff = 'QUADRATIC'
    sc.use_nodes = True
    t = sc.node_tree
    for nd in list(t.nodes):
        t.nodes.remove(nd)
    rl = t.nodes.new('CompositorNodeRLayers')
    comp = t.nodes.new('CompositorNodeComposite')
    mul = t.nodes.new('CompositorNodeMath'); mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 0.55          # max haze fraction at the far end
    t.links.new(rl.outputs['Mist'], mul.inputs[0])
    mix = t.nodes.new('CompositorNodeMixRGB'); mix.blend_type = 'MIX'
    t.links.new(mul.outputs[0], mix.inputs['Fac'])
    t.links.new(rl.outputs['Image'], mix.inputs[1])
    haze = SKY_HORIZON_RGB                       # same light as the horizon sky glow
    k = nits(0.3)                                # scattered lamp/sky light, scene-linear
    mix.inputs[2].default_value = (haze[0] * k, haze[1] * k, haze[2] * k, 1)
    mix.name = 'HAZE'
    t.links.new(mix.outputs[0], comp.inputs['Image'])
    return t


def glare(sc, threshold=1.0, mix=-0.75, size=8):
    """Lens bloom (compositor Glare/Fog Glow) applied after the haze: only values above
    ~threshold (scene-linear, after exposure scaling in the view transform) bloom, so lamps,
    signals and brake lamps get a soft halo of their own colour."""
    t = sc.node_tree
    comp = next(n for n in t.nodes if n.type == 'COMPOSITE')
    src = comp.inputs['Image'].links[0].from_socket
    g = t.nodes.new('CompositorNodeGlare'); g.name = 'GLARE'
    g.glare_type = 'FOG_GLOW'
    g.quality = 'HIGH'
    g.size = size
    g.mix = mix
    # threshold is in scene-linear units *before* the view exposure, so convert
    g.threshold = threshold / (2 ** sc.view_settings.exposure)
    t.links.new(src, g.inputs['Image'])
    t.links.new(g.outputs['Image'], comp.inputs['Image'])
    return g
