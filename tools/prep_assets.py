"""Turn raw downloads (assets/sketchfab/*/model.glb) into clean, metric, portable library files:
assets/lib/<key>.blend, each holding one collection 'A_<key>' whose objects are parented to an
empty '<key>_root' at the origin. Conventions:
  * metres, Z up, object sits on z=0, centred in XY
  * vehicles face +Y; wheels are separate objects named '*_wheel_FL/FR/RL/RR' with the origin at
    the hub so they can be rotated about their local X axis
  * textures unpacked to assets/lib/textures/<key>_*, longest side capped at 2048 px
Usage: blender -b --factory-startup -P tools/prep_assets.py -- [key ...]
"""
import os, sys, math, bpy, bmesh
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'assets', 'lib')

# yaw (deg) is applied after import to make the vehicle face +Y. Determined from check renders.
SPECS = {
    'taxi_cvpi':   dict(src='taxi_cvpi', kind='vehicle', length=5.39, yaw=0, split='wheels_and_parts'),
    'camry':       dict(src='camry', kind='vehicle', length=4.885, yaw=0, split='AUTO'),
    'car_sedan':   dict(src='car_pack', node='Sedan Body', kind='vehicle', length=4.6, yaw=0),
    'car_hatch':   dict(src='car_pack', node='Hatchback Body', kind='vehicle', length=4.2, yaw=0),
    'car_wagon':   dict(src='car_pack', node='Wagon Body', kind='vehicle', length=4.8, yaw=0),
    'car_suv':     dict(src='car_pack', node='SUV Body', kind='vehicle', length=5.0, yaw=0),
    'car_minivan': dict(src='car_pack', node='minivan body', kind='vehicle', length=5.1, yaw=0),
    'car_pickup':  dict(src='car_pack', node='Pickup Body', kind='vehicle', length=5.3, yaw=0),
    'hydrant':     dict(src='hydrant', kind='prop', height=0.80, keep_largest_cluster=True),
    'newsbox':     dict(src='newsbox', kind='prop', strip_ground=0.03),
    'trash':       dict(src='cityprops2', node='trash', kind='prop'),
    'manhole':     dict(src='cityprops2', node='manhole_cover0', kind='prop'),
    'ped_umbrella': dict(src='ped_winter_umbrella', kind='prop', height=None),
    'ped_coat':    dict(src='ped_gent_umbrella', kind='prop', height=None),
}
# Overrides from tools/asset_orient.json (yaw, height) if present
import json
_o = os.path.join(LIB, 'orient.json')
if os.path.exists(_o):
    for k, v in json.load(open(_o)).items():
        SPECS.setdefault(k, {}).update(v)


def world_bbox(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def realize(objs):
    """Make meshes single-user, unparent keeping transforms, apply transforms."""
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in objs:
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)


def separate_loose(o):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.mesh.separate(type='LOOSE')
    return [x for x in bpy.context.selected_objects]


def set_origin(o, p):
    o.data.transform(Matrix.Translation(-p))
    o.location = p


def split_wheels(objs, key, split):
    """Find the four wheels. Returns dict corner->[objects]."""
    cand = [o for o in objs if split == 'AUTO' or o.name.startswith(split) or split in o.name]
    parts = []
    for o in cand:
        parts += separate_loose(o)
    allobjs = [o for o in objs if o not in cand] + parts
    lo, hi = world_bbox(allobjs)
    # Tyres: roughly round in YZ, diameter 0.55-0.85 m, near the floor, near the sides
    tyres = []
    for o in parts:
        a, b = world_bbox([o])
        d = b - a
        if 0.5 < d.z < 0.9 and abs(d.y - d.z) < 0.08 and a.z < lo.z + 0.08 and d.x < 0.45:
            tyres.append(o)
    hubs = {}
    for o in tyres:
        a, b = world_bbox([o])
        c = (a + b) / 2
        corner = ('F' if c.y > (lo.y + hi.y) / 2 else 'R') + ('R' if c.x > (lo.x + hi.x) / 2 else 'L')
        if corner not in hubs or (b - a).z > hubs[corner][1]:
            hubs[corner] = (c, (b - a).z)
    wheels = {k: [] for k in hubs}
    for o in parts:
        a, b = world_bbox([o])
        c = (a + b) / 2
        for k, (h, dia) in hubs.items():
            if (Vector((c.x, c.y, c.z)) - h).length < dia * 0.45 and (b - a).z <= dia + 0.02 \
                    and (b - a).y <= dia + 0.02:
                wheels[k].append(o)
                break
    return wheels, hubs, allobjs


def main():
    keys = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = keys or list(SPECS)
    os.makedirs(os.path.join(LIB, 'textures'), exist_ok=True)
    for key in keys:
        sp = SPECS[key]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, 'assets', 'sketchfab', sp['src'], 'model.glb'))
        bpy.context.view_layer.update()
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        if 'node' in sp:
            node = bpy.data.objects[sp['node']]
            meshes = [o for o in node.children_recursive if o.type == 'MESH'] + \
                     ([node] if node.type == 'MESH' else [])
            if sp['kind'] == 'vehicle':   # car_pack wheels are siblings: take the 4 nearest
                lo, hi = world_bbox(meshes)
                c = (lo + hi) / 2
                bodies = [o for o in bpy.data.objects if o.type == 'EMPTY' and
                          o.name.lower().endswith(' body')]
                bc = {}
                for bo in bodies:
                    ms = [m for m in bo.children_recursive if m.type == 'MESH']
                    l2, h2 = world_bbox(ms)
                    bc[bo.name] = (l2 + h2) / 2
                def ctr(o):
                    l2, h2 = world_bbox([o])
                    return (l2 + h2) / 2
                def dxy(a, b):
                    return ((a - b) * Vector((1, 1, 0))).length
                wheel_objs = []
                for o in bpy.data.objects:
                    if o.type == 'MESH' and o.name.startswith('Wheel') and o not in meshes:
                        cc = ctr(o)
                        near = min(bc, key=lambda n: dxy(bc[n], cc))
                        if near == sp['node']:
                            wheel_objs.append(o)
                meshes += wheel_objs
        else:
            wheel_objs = []
        # drop helper geometry
        meshes = [o for o in meshes if not o.name.lower().startswith(('icosphere', 'sample_ground'))]
        node_yaw = 0.0
        if 'node' in sp:
            node_yaw = -bpy.data.objects[sp['node']].matrix_world.to_euler().z
        realize(meshes)
        for o in list(bpy.data.objects):
            if o not in meshes:
                bpy.data.objects.remove(o, do_unlink=True)
        # yaw so the vehicle faces +Y
        R = Matrix.Rotation(math.radians(sp.get('yaw', 0)) + node_yaw, 4, 'Z')
        for o in meshes:
            o.data.transform(R)
        if sp.get('strip_ground'):
            for o in meshes:
                bm = bmesh.new(); bm.from_mesh(o.data)
                zmin = min(v.co.z for v in bm.verts)
                kill = [f for f in bm.faces if all(v.co.z < zmin + sp['strip_ground'] for v in f.verts)]
                bmesh.ops.delete(bm, geom=kill, context='FACES')
                bm.to_mesh(o.data); bm.free()
            # drop small floating scan fragments (< 2% of the faces of the largest piece)
            parts = []
            for o in meshes:
                parts += separate_loose(o)
            big = max(len(p.data.polygons) for p in parts)
            meshes = []
            for p in parts:
                if len(p.data.polygons) < big * 0.02:
                    bpy.data.objects.remove(p, do_unlink=True)
                else:
                    meshes.append(p)
        if sp.get('keep_largest_cluster'):
            # e.g. the hydrant file has two hydrants side by side: keep the one nearest x-min
            parts = []
            for o in meshes:
                parts += separate_loose(o)
            lo, hi = world_bbox(parts)
            midx = (lo.x + hi.x) / 2
            keep = [p for p in parts if (world_bbox([p])[0].x + world_bbox([p])[1].x) / 2 < midx]
            for p in parts:
                if p not in keep:
                    bpy.data.objects.remove(p, do_unlink=True)
            meshes = keep
        # scale
        lo, hi = world_bbox(meshes)
        d = hi - lo
        s = 1.0
        if sp.get('length'):
            s = sp['length'] / d.y
        elif sp.get('height'):
            s = sp['height'] / d.z
        elif d.z > 20:      # centimetre-unit files
            s = 0.01
        T = Matrix.Translation(Vector((-(lo.x + hi.x) / 2 * s, -(lo.y + hi.y) / 2 * s, -lo.z * s))) @ \
            Matrix.Scale(s, 4)
        for o in meshes:
            o.data.transform(T)
        wheels = {}
        if sp['kind'] == 'vehicle':
            if sp.get('split'):
                wheels, hubs, meshes = split_wheels(meshes, key, sp['split'])
                for corner, objs in wheels.items():
                    bpy.ops.object.select_all(action='DESELECT')
                    for o in objs:
                        o.select_set(True)
                    bpy.context.view_layer.objects.active = objs[0]
                    if len(objs) > 1:
                        bpy.ops.object.join()
                    w = bpy.context.view_layer.objects.active
                    w.name = f'{key}_wheel_{corner}'
                    a, b = world_bbox([w])
                    set_origin(w, (a + b) / 2)
                    wheels[corner] = [w]
                # join the remaining body loose parts back per material for a lighter scene
            else:
                lo, hi = world_bbox(meshes)
                cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
                for o in wheel_objs:
                    a, b = world_bbox([o])
                    c = (a + b) / 2
                    corner = ('F' if c.y > cy else 'R') + ('R' if c.x > cx else 'L')
                    wheels.setdefault(corner, []).append(o)
                for corner, objs in wheels.items():
                    bpy.ops.object.select_all(action='DESELECT')
                    for o in objs:
                        o.select_set(True)
                    bpy.context.view_layer.objects.active = objs[0]
                    if len(objs) > 1:
                        bpy.ops.object.join()
                    w = bpy.context.view_layer.objects.active
                    w.name = f'{key}_wheel_{corner}'
                    a2, b2 = world_bbox([w])
                    set_origin(w, (a2 + b2) / 2)
                    wheels[corner] = [w]
        # join body parts (everything that is not a wheel) into one object
        wheel_set = {w for ws in wheels.values() for w in ws}
        body = [o for o in bpy.data.objects if o.type == 'MESH' and o not in wheel_set]
        bpy.ops.object.select_all(action='DESELECT')
        for o in body:
            o.select_set(True)
        bpy.context.view_layer.objects.active = body[0]
        if len(body) > 1:
            bpy.ops.object.join()
        b = bpy.context.view_layer.objects.active
        b.name = f'{key}_body'
        # collection + root
        col = bpy.data.collections.new(f'A_{key}')
        bpy.context.scene.collection.children.link(col)
        root = bpy.data.objects.new(f'{key}_root', None)
        col.objects.link(root)
        for o in [b] + list(wheel_set):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            o.parent = root
        lo, hi = world_bbox([b] + list(wheel_set))
        root['size'] = list(hi - lo)
        root['wheels'] = sorted(wheels)
        print(f'PREP {key}: size=({(hi-lo).x:.2f},{(hi-lo).y:.2f},{(hi-lo).z:.2f}) wheels={sorted(wheels)} '
              f'body_tris={len(b.data.polygons)}')
        # textures: cap at 2048, write next to the library
        out = os.path.join(LIB, f'{key}.blend')
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        for im in bpy.data.images:
            if im.size[0] == 0:
                continue
            if max(im.size) > 2048:
                f = 2048 / max(im.size)
                im.scale(int(im.size[0] * f), int(im.size[1] * f))
            ext = '.jpg' if im.file_format == 'JPEG' else '.png'
            safe = ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in im.name)
            path = os.path.join(LIB, 'textures', f'{key}_{safe}{ext}')
            im.filepath_raw = path
            im.save()
            if im.packed_file:
                im.unpack(method='REMOVE')
            im.filepath = bpy.path.relpath(path)
            im.reload()
        bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True, compress=True)
        if os.path.exists(out + '1'):
            os.remove(out + '1')


main()
