"""Print the normalised screen-space bounding box of objects matching a prefix, per frame.
blender -b scene.blend -P tools/frame_margin.py -- PREFIX F1 [F2 ...]"""
import sys, bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
args = sys.argv[sys.argv.index('--') + 1:]
prefix, frames = args[0], [int(f) for f in args[1:]]
sc = bpy.context.scene
for f in frames:
    sc.frame_set(f)
    xs, ys = [], []
    for ob in sc.objects:
        if ob.name.startswith(prefix) and ob.type == 'MESH':
            for c in ob.bound_box:
                v = world_to_camera_view(sc, sc.camera, ob.matrix_world @ Vector(c))
                xs.append(v.x); ys.append(v.y)
    print(f'MARGIN f{f}: left {min(xs):.3f} right {1-max(xs):.3f} bottom {min(ys):.3f} top {1-max(ys):.3f}')
