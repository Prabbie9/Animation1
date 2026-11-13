"""Places prepared library assets (assets/lib/<key>.blend, see tools/prep_assets.py).

* instance(): collection instance, for static repeated props / parked cars (cheap, shares data)
* copy():     linked-duplicate objects (shared mesh data) for things that animate, returning the
              root, body and wheel objects so traffic.py can drive them.
"""
import os
import math
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'assets', 'lib')


def _library_collection():
    col = bpy.data.collections.get('AssetLibrary')
    if col is None:
        col = bpy.data.collections.new('AssetLibrary')
        bpy.context.scene.collection.children.link(col)
        bpy.context.view_layer.layer_collection.children['AssetLibrary'].exclude = True
    return col


def load(key):
    name = f'A_{key}'
    col = bpy.data.collections.get(name)
    if col:
        return col
    path = os.path.join(LIB, key + '.blend')
    with bpy.data.libraries.load(path, link=False, relative=True) as (src, dst):
        dst.collections = [name]
    col = dst.collections[0]
    _library_collection().children.link(col)
    return col


def size(key):
    return tuple(load(key).objects[f'{key}_root']['size'])


def instance(key, name, col, loc, rot_z=0.0, scale=1.0):
    src = load(key)
    e = bpy.data.objects.new(name, None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = src
    e.location = loc
    e.rotation_euler.z = rot_z
    e.scale = (scale, scale, scale)
    e.empty_display_size = 0.5
    col.objects.link(e)
    return e


def copy(key, name, col, loc, rot_z=0.0):
    """Linked duplicate of every object in the asset; returns dict(root, body, wheels)."""
    src = load(key)
    mapping = {}
    for o in src.objects:
        n = o.copy()               # shares o.data (linked duplicate)
        n.name = o.name.replace(key, name, 1)
        col.objects.link(n)
        mapping[o] = n
    for o, n in mapping.items():
        if o.parent in mapping:
            n.parent = mapping[o.parent]
    root = mapping[src.objects[f'{key}_root']]
    root.location = loc
    root.rotation_euler.z = rot_z
    out = dict(root=root, body=None, wheels={})
    for o, n in mapping.items():
        if o.name.endswith('_body'):
            out['body'] = n
        elif '_wheel_' in o.name:
            out['wheels'][o.name.rsplit('_', 1)[1]] = n
    return out
