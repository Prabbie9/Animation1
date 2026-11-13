"""Import a GLB on a neutral studio background, print structure/dimensions, render 3 views.
blender -b --factory-startup -P tools/inspect_asset.py -- model.glb out_prefix [filter_substring]"""
import sys, math, bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
path, out = a[0], a[1]
flt = a[2] if len(a) > 2 else None
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
sc = bpy.context.scene
meshes = [o for o in sc.objects if o.type == 'MESH']
roots = [o for o in sc.objects if o.parent is None]
print('ROOTS', [(r.name, r.type, tuple(round(s, 3) for s in r.scale)) for r in roots])
def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi
bpy.context.view_layer.update()
# group meshes by top-level ancestor
def top(o):
    while o.parent and o.parent.parent:
        o = o.parent
    return o
groups = {}
for m in meshes:
    groups.setdefault(top(m).name, []).append(m)
for g, objs in groups.items():
    lo, hi = bbox(objs)
    d = hi - lo
    print(f'GROUP {g:40s} n={len(objs):3d} size=({d.x:.2f},{d.y:.2f},{d.z:.2f}) min=({lo.x:.1f},{lo.y:.1f},{lo.z:.1f}) tris={sum(len(o.data.loop_triangles) or len(o.data.polygons) for o in objs)}')
for m in bpy.data.materials:
    nt = m.node_tree
    texs = [n.image.name + f'[{n.image.size[0]}]' for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image] if nt else []
    print('MAT', m.name, texs)
if flt:
    keep = [o for o in meshes if flt.lower() in top(o).name.lower() or flt.lower() in o.name.lower()]
    for o in meshes:
        if o not in keep:
            o.hide_render = True
    meshes = keep
lo, hi = bbox(meshes)
c = (lo + hi) / 2
r = (hi - lo).length
# studio
w = bpy.data.worlds.new('W'); w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
sc.world = w
bpy.ops.mesh.primitive_plane_add(size=200, location=(c.x, c.y, lo.z))
pm = bpy.data.materials.new('floor'); pm.use_nodes = True
pm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.35, 0.35, 1)
bpy.context.active_object.data.materials.append(pm)
for i, (az, el) in enumerate(((35, 18), (145, 15), (-90, 10))):
    sd = bpy.data.lights.new(f'k{i}', 'AREA'); sd.size = r; sd.energy = 400 * r * r
lk = bpy.data.objects.new('key', bpy.data.lights['k0']); sc.collection.objects.link(lk)
lk.location = c + Vector((r, -r, r * 1.2)); lk.rotation_euler = (math.radians(45), 0, math.radians(45))
cd = bpy.data.cameras.new('c'); cd.lens = 50
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 800, 450
for i, (az, el) in enumerate(((35, 15), (145, 12), (-90, 5))):
    d = Vector((math.cos(math.radians(az)) * math.cos(math.radians(el)),
                math.sin(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
    cam.location = c + d * r * 1.3
    cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f'{out}_{i}.png'
    bpy.ops.render.render(write_still=True)
