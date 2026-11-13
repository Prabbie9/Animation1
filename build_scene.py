"""Regenerates scene.blend from scratch.

Usage:  blender -b --factory-startup -P build_scene.py -- [--out scene.blend] [--stage greybox]
"""
import os
import sys
import argparse
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import importlib
import scenelib
from scenelib import (config as C, util, materials, signals, layout, assets, dressing, buildings,
                      lighting, surfaces, vehicle_paint, rain, traffic)
for m in (C, util, materials, signals, layout, assets, dressing, buildings, lighting, surfaces, vehicle_paint, rain, traffic):
    importlib.reload(m)


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', default=os.path.join(HERE, 'scene.blend'))
    p.add_argument('--stage', default='lighting')
    p.add_argument('--refs', action='store_true', help='keep the scale reference figures visible')
    return p.parse_args(argv)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = 'Intersection'
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = C.FPS
    sc.frame_start, sc.frame_end = C.FRAME_START, C.FRAME_END
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sc.render.engine = 'CYCLES'
    return sc


def greybox_world(sc):
    """Neutral overcast daylight, only for judging layout and scale."""
    w = bpy.data.worlds.new('GB_World')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.8, 0.85, 0.95, 1)
    bg.inputs['Strength'].default_value = 1.0
    sc.world = w
    sun = bpy.data.lights.new('GB_Sun', 'SUN')
    sun.energy = 2.5
    sun.angle = 0.3
    so = bpy.data.objects.new('GB_Sun', sun)
    so.rotation_euler = (0.9, 0.2, 2.3)
    sc.collection.objects.link(so)


def night(sc, root, vehicles):
    lighting.world(sc)
    lighting.street_lights(root)
    lighting.skyline()
    road = surfaces.apply(root)
    vehicle_paint.apply()
    sizes = {k: assets.size(k) for k in lighting.VEHICLE_LAMPS}
    lighting.vehicles(root, vehicles, sizes)
    signals.animate_cycle()
    rain.build(root, sc.camera, vehicles, road, buildings.AWNING_EDGES)
    materials.set_wetness(1.0)
    lighting.colour_management(sc, exposure=C.EXPOSURE_EV)
    lighting.haze_compositor(sc)
    lighting.glare(sc, threshold=6.0, mix=-0.92, size=5)
    cy = sc.cycles
    cy.sample_clamp_indirect = 3.0
    cy.blur_glossy = 1.0
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces, cy.transmission_bounces = 8, 3, 4, 8
    cy.use_light_tree = True


def main():
    a = parse()
    sc = reset()
    root = bpy.data.collections.new('Set')
    sc.collection.children.link(root)
    info = layout.build(root, greybox=(a.stage == 'greybox'))
    if a.stage != 'greybox':
        buildings.build(root)
    vehicles = dressing.build(root)
    specs = traffic.avenue_specs(vehicles)
    if a.stage not in ('greybox', 'assets', 'facades'):
        specs.update(traffic.add_cross_traffic(root, vehicles))
    if a.stage != 'greybox' and not a.refs:
        bpy.data.collections['Reference'].hide_render = True
        for o in bpy.data.collections['Reference'].objects:
            o.hide_viewport = True
    # Frame-1 phase: avenue (NB/SB) red, cross street (EB/WB) green.
    for ap, st in (('NB', 'red'), ('SB', 'red'), ('EB', 'green'), ('WB', 'green')):
        signals.set_state(ap, st)
    if a.stage in ('greybox', 'assets', 'facades'):
        greybox_world(sc)
    else:
        night(sc, root, vehicles)
        traffic.animate(vehicles, specs)
    bpy.ops.file.pack_all() if False else None
    bpy.ops.wm.save_as_mainfile(filepath=a.out, relative_remap=True, compress=True)
    print('SAVED', a.out)


main()
