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
from scenelib import config as C, layout
for m in (C, layout):
    importlib.reload(m)


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--out', default=os.path.join(HERE, 'scene.blend'))
    p.add_argument('--stage', default='greybox')
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


def main():
    a = parse()
    sc = reset()
    root = bpy.data.collections.new('Set')
    sc.collection.children.link(root)
    info = layout.build(root)
    if a.stage == 'greybox':
        greybox_world(sc)
    bpy.ops.file.pack_all() if False else None
    bpy.ops.wm.save_as_mainfile(filepath=a.out, relative_remap=True, compress=True)
    print('SAVED', a.out)


main()
