"""Small helpers around bpy used by every builder module."""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj, col):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def mesh_object(name, verts, faces, col, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    return ob


def bm_to_object(bm, name, col, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for m in mat:
                me.materials.append(m)
        else:
            me.materials.append(mat)
    return ob


def box(name, col, size, loc, mat=None, rot_z=0.0):
    """Axis-aligned box. size=(sx,sy,sz); loc = centre of the BOTTOM face."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, 0, size[2] / 2)), verts=bm.verts)
    ob = bm_to_object(bm, name, col, mat)
    ob.location = loc
    ob.rotation_euler.z = rot_z
    return ob


def cylinder(name, col, radius, depth, loc, mat=None, segments=16, rot=(0, 0, 0)):
    """Cylinder whose base sits at loc (before rotation)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius, depth=depth)
    bmesh.ops.translate(bm, vec=Vector((0, 0, depth / 2)), verts=bm.verts)
    ob = bm_to_object(bm, name, col, mat)
    ob.location = loc
    ob.rotation_euler = rot
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def flat_mat(name, color, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (*color, 1.0)
    return m


def rounded_corner_polygon(x0, y0, x1, y1, r, seg=12):
    """Rectangle [x0,x1]x[y0,y1] in the +,+ quadrant with its (x0,y0) corner rounded (radius r).
    Returns CCW 2D points."""
    pts = []
    cx, cy = x0 + r, y0 + r
    # arc from (x0, y0+r) to (x0+r, y0)  (angles 180 -> 270 deg)
    for i in range(seg + 1):
        a = math.pi + (math.pi / 2) * i / seg
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts += [(x1, y0), (x1, y1), (x0, y1)]
    return pts


def extrude_polygon(name, col, pts2d, z0, z1, mat=None, flip=(1, 1)):
    """Extrude a 2D polygon between z0 and z1. flip mirrors x/y (keeps normals outward)."""
    sx, sy = flip
    pts = [(p[0] * sx, p[1] * sy) for p in pts2d]
    if sx * sy < 0:
        pts.reverse()
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bm.normal_update()
    return bm_to_object(bm, name, col, mat)


def keyframe_ease(obj, path, frames_values, interp='BEZIER'):
    for f, v in frames_values:
        setattr_path(obj, path, v)
        obj.keyframe_insert(data_path=path, frame=f)


def setattr_path(obj, path, v):
    setattr(obj, path, v)
