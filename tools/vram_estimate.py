"""Estimate peak GPU memory for a 4K Cycles render of scene.blend (no GPU needed).
blender -b scene.blend -P tools/vram_estimate.py -- [frame]

Model (deliberately conservative):
  * image textures: Cycles GPU keeps full-resolution textures, no mipmaps: 8-bit -> 4 B/px
    (uchar4), float (EXR/HDR) -> 16 B/px (float4)
  * geometry: per unique evaluated triangle ~200 B (vertices, normals, UVs, attributes, BVH;
    HIP-RT BVHs are larger than BVH2), per instance ~256 B (+ motion-blur transforms)
  * render buffers at 3840x2160: ~24 floats/px (combined, denoising albedo+normal, adaptive
    sampling aux, sample count, light-path debug-free)
  * OpenImageDenoise on the GPU at 4K: ~2 GB working memory (tiled)
  * HIP context, kernels, misc: ~1 GB
"""
import sys, bpy
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
frame = int(argv[0]) if argv else 96
sc = bpy.context.scene
sc.frame_set(frame)
MB = 1024 * 1024

tex = []
for im in bpy.data.images:
    if im.users == 0 or im.size[0] == 0 or im.type != 'IMAGE':
        continue
    w, h = im.size
    bpp = 16 if im.is_float else 4
    tex.append((w * h * bpp, im.name, w, h, 'float' if im.is_float else 'byte'))
tex.sort(reverse=True)
tex_total = sum(t[0] for t in tex)

dg = bpy.context.evaluated_depsgraph_get()
uniq = {}
inst = 0
for oi in dg.object_instances:
    ob = oi.object
    if ob.type != 'MESH' or not ob.visible_camera and not ob.visible_diffuse and not ob.visible_glossy:
        continue
    inst += 1
    key = ob.data.name if ob.data else ob.name
    if key not in uniq:
        try:
            me = ob.data
            me.calc_loop_triangles()
            uniq[key] = len(me.loop_triangles)
        except Exception:
            uniq[key] = 0
tris = sum(uniq.values())
geo = tris * 200 + inst * 256
W, H = 3840, 2160
buffers = W * H * 24 * 4
oidn = 2048 * MB
misc = 1024 * MB
total = tex_total + geo + buffers + oidn + misc
print('=== VRAM estimate (frame %d, 3840x2160) ===' % frame)
print(f'textures: {len(tex)} images, {tex_total / MB:8.1f} MB')
for b, n, w, h, kind in tex[:8]:
    print(f'    {b / MB:7.1f} MB  {w}x{h} {kind:5s} {n}')
print(f'geometry: {tris / 1e6:.2f} M unique triangles in {len(uniq)} meshes, {inst} instances -> {geo / MB:8.1f} MB')
print(f'render buffers (24 floats/px): {buffers / MB:8.1f} MB')
print(f'OIDN on GPU (4K, tiled): {oidn / MB:8.1f} MB')
print(f'HIP context / kernels / misc: {misc / MB:8.1f} MB')
print(f'TOTAL ~ {total / MB / 1024:.2f} GB  (budget 12 GB of the 7800 XT\'s 16 GB)')
