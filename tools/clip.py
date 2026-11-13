"""Render a frame range in one session (CPU test clips).
blender -b scene.blend -P tools/clip.py -- --start A --end B [--step N] --res W H --samples S --out DIR
  [--norain] hide rain/drip streaks (for denoiser-flicker analysis)  [--cam X Y Z RX RY RZ --lens L]"""
import sys, os, math, argparse, time, bpy
a = argparse.ArgumentParser()
a.add_argument('--start', type=int); a.add_argument('--end', type=int); a.add_argument('--step', type=int, default=1)
a.add_argument('--res', type=int, nargs=2, default=(960, 540)); a.add_argument('--samples', type=int, default=32)
a.add_argument('--out'); a.add_argument('--norain', action='store_true')
a.add_argument('--cam', type=float, nargs=6); a.add_argument('--lens', type=float, default=35)
o = a.parse_args(sys.argv[sys.argv.index('--') + 1:])
sc = bpy.context.scene
r = sc.render
r.resolution_x, r.resolution_y = o.res; r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '8'
cy = sc.cycles
cy.device = 'CPU'; cy.samples = o.samples; cy.use_adaptive_sampling = True
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
sc.render.use_persistent_data = True
if o.norain:
    for ob in bpy.data.objects:
        if ob.name in ('RainNear', 'RainFar', 'AwningDrips'):
            ob.hide_render = True
if o.cam:
    cd = bpy.data.cameras.new('ClipCam'); co = bpy.data.objects.new('ClipCam', cd)
    sc.collection.objects.link(co); co.location = o.cam[:3]
    co.rotation_euler = [math.radians(v) for v in o.cam[3:]]; cd.lens = o.lens; sc.camera = co
os.makedirs(o.out, exist_ok=True)
for f in range(o.start, o.end + 1, o.step):
    t0 = time.time()
    sc.frame_set(f)
    r.filepath = os.path.join(o.out, f'f{f:04d}.png')
    bpy.ops.render.render(write_still=True)
    print(f'[clip] f{f} {time.time() - t0:.1f}s', flush=True)
