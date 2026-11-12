"""Test-render helper (CPU, small stills). Not the production renderer.

blender -b scene.blend -P tools/still.py -- --frame 1 --res 960 540 --samples 32 --out x.png
  [--plan]  top-down orthographic plan view   [--cam X Y Z RX RY RZ] free camera
"""
import sys, argparse, math, bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
p = argparse.ArgumentParser()
p.add_argument('--frame', type=int, default=1)
p.add_argument('--res', type=int, nargs=2, default=(960, 540))
p.add_argument('--samples', type=int, default=32)
p.add_argument('--out', required=True)
p.add_argument('--plan', action='store_true')
p.add_argument('--cam', type=float, nargs=6)
p.add_argument('--lens', type=float, default=35)
p.add_argument('--nodof', action='store_true')
p.add_argument('--engine', default='CYCLES')
a = p.parse_args(argv)

sc = bpy.context.scene
sc.frame_set(a.frame)
r = sc.render
r.engine = a.engine
r.resolution_x, r.resolution_y = a.res
r.resolution_percentage = 100
r.filepath = a.out
r.image_settings.file_format = 'PNG'
r.image_settings.color_depth = '8'
if a.engine == 'CYCLES':
    sc.cycles.device = 'CPU'
    sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.use_adaptive_sampling = True
r.threads_mode = 'AUTO'
if a.plan or a.cam:
    cd = bpy.data.cameras.new('TestCam')
    co = bpy.data.objects.new('TestCam', cd)
    sc.collection.objects.link(co)
    if a.plan:
        cd.type = 'ORTHO'
        cd.ortho_scale = 90
        co.location = (0, 10, 300)
        co.rotation_euler = (0, 0, 0)
        cd.clip_end = 1000
    else:
        co.location = a.cam[:3]
        co.rotation_euler = [math.radians(v) for v in a.cam[3:]]
        cd.lens = a.lens
        cd.clip_end = 3000
    sc.camera = co
if a.nodof and sc.camera:
    sc.camera.data.dof.use_dof = False
bpy.ops.render.render(write_still=True)
print('WROTE', a.out)
