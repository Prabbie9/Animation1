"""Render a prepared library asset from the front-right (+X,+Y), wheels tinted red, next to a
1.75 m reference column. blender -b --factory-startup -P tools/check_lib.py -- key out.png [az]"""
import sys, os, math, bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
key, out = a[0], a[1]
az = float(a[2]) if len(a) > 2 else 40
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(os.path.join(ROOT, 'assets/lib', key + '.blend')) as (src, dst):
    dst.collections = [f'A_{key}']
col = dst.collections[0]
bpy.context.scene.collection.children.link(col)
red = bpy.data.materials.new('red'); red.diffuse_color = (1, 0, 0, 1)
red.use_nodes = True; red.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 0, 0, 1)
for o in col.objects:
    if '_wheel_' in o.name:
        o.data.materials.clear(); o.data.materials.append(red)
size = Vector(col.objects[f'{key}_root']['size'])
bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=1.75, location=(size.x / 2 + 0.6, 0, 0.875))
bpy.ops.mesh.primitive_plane_add(size=60)
sc = bpy.context.scene
w = bpy.data.worlds.new('w'); w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.6, 0.6, 0.6, 1); sc.world = w
r = max(size.length, 2.5)
cd = bpy.data.cameras.new('c'); cd.lens = 40; cam = bpy.data.objects.new('c', cd)
sc.collection.objects.link(cam); sc.camera = cam
d = Vector((math.sin(math.radians(az)), math.cos(math.radians(az)), 0.45)).normalized()
c = Vector((0, 0, size.z / 2))
cam.location = c + d * r * 1.35
cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'CYCLES'; sc.cycles.samples = 16; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 640, 400
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
