"""Car paint replacing broken imported paint (the Camry file ships metallic=1 everywhere, i.e.
bare chrome, which smeared the taxi's yellow over its side). Real automotive finish: pigmented
base with metallic flakes under a glossy clear coat (IOR ~1.5)."""
import bpy
from . import materials as M


def car_paint(name, base, flake=0.45, rough=0.32):
    m, n, l = M.new(name)
    b = n['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Metallic'].default_value = flake
    b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.03
    b.inputs['Coat IOR'].default_value = 1.5
    # metallic flake sparkle: very fine noise perturbing the base-layer normal only
    nz = n.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3000.0
    bp = n.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08
    l.new(nz.outputs['Fac'], bp.inputs['Height'])
    l.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def apply():
    paint = car_paint('CarPaint_camry_darkgrey', (0.012, 0.014, 0.017), flake=0.6, rough=0.38)
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith('camry_body'):
            for i, m in enumerate(o.data.materials):
                if m and m.name.startswith('Paint_Color'):
                    o.data.materials[i] = paint
