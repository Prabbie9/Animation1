"""Production renderer for scene.blend (Blender 4.5 LTS, Cycles).

Run from the repository root:
    blender -b scene.blend -P render.py -- [options]

Options
    --quality {final,balanced,fast,draft}   speed/quality ladder (default: final), see README
    --preview              1920x1080, 'draft' sampling, writes to renders/preview/
    --frame N              render one frame (benchmark: prints time and a full-shot estimate)
    --range A B            render frames A..B inclusive (default: the scene's 1..192)
    --samples S            override max samples
    --scale P              resolution percentage (e.g. 75 renders 2880x1620)
    --device {auto,HIP,OPTIX,CUDA,ONEAPI,METAL,CPU}   (default auto: HIP first)
    --no-hiprt             disable HIP-RT (hardware ray tracing) even if available
    --out DIR              output folder (default renders/frames or renders/preview)
    --overwrite            re-render frames that already exist
    --png8                 8-bit PNG instead of 16-bit

Resuming: frames are written as <out>/frame_####.png via a temporary file that is renamed only
after Blender has finished writing it, so a frame that exists is complete. Re-running the same
command skips existing frames, so an interrupted render resumes where it stopped.
"""
import argparse
import os
import sys
import time

import bpy

QUALITY = {
    #            samples  noise-thr  max  diff gloss trans  clamp-ind  caustics
    'final':    (512,     0.010,     8,   3,   4,    8,     3.0,       False),
    'balanced': (320,     0.015,     8,   3,   4,    8,     3.0,       False),
    'fast':     (192,     0.025,     6,   2,   3,    6,     3.0,       False),
    'draft':    (64,      0.050,     4,   2,   2,    4,     3.0,       False),
}


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(prog='render.py')
    p.add_argument('--quality', choices=QUALITY, default='final')
    p.add_argument('--preview', action='store_true')
    p.add_argument('--frame', type=int)
    p.add_argument('--range', type=int, nargs=2, metavar=('A', 'B'))
    p.add_argument('--samples', type=int)
    p.add_argument('--scale', type=int)
    p.add_argument('--device', default='auto')
    p.add_argument('--no-hiprt', action='store_true')
    p.add_argument('--out')
    p.add_argument('--overwrite', action='store_true')
    p.add_argument('--png8', action='store_true')
    return p.parse_args(argv)


def setup_device(want, hiprt=True):
    """Enable every GPU of the first available backend; fall back to CPU."""
    sc = bpy.context.scene
    prefs = bpy.context.preferences.addons['cycles'].preferences
    order = ['HIP', 'OPTIX', 'CUDA', 'ONEAPI', 'METAL'] if want == 'auto' else [want]
    for backend in order:
        if backend == 'CPU':
            break
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.refresh_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if not gpus:
            continue
        for d in prefs.devices:
            # GPU only: mixing the CPU in usually slows a strong GPU down
            d.use = d.type == backend
        if backend == 'HIP' and hasattr(prefs, 'use_hiprt'):
            prefs.use_hiprt = hiprt
        sc.cycles.device = 'GPU'
        names = ', '.join(d.name for d in gpus)
        extra = ''
        if backend == 'HIP':
            extra = f" (HIP-RT {'on' if getattr(prefs, 'use_hiprt', False) else 'off'})"
        print(f'[render] device: {backend}{extra}: {names}')
        return backend
    sc.cycles.device = 'CPU'
    print('[render] device: CPU (no supported GPU backend found). This will be slow.')
    return 'CPU'


def apply_quality(a):
    sc = bpy.context.scene
    cy = sc.cycles
    q = 'draft' if a.preview and a.quality == 'final' else a.quality
    samples, thr, maxb, diff, gloss, trans, clamp, caustics = QUALITY[q]
    cy.samples = a.samples or samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = thr
    cy.adaptive_min_samples = 0
    cy.max_bounces = maxb
    cy.diffuse_bounces = diff
    cy.glossy_bounces = gloss
    cy.transmission_bounces = trans
    cy.volume_bounces = 0
    cy.transparent_max_bounces = 8
    cy.sample_clamp_direct = 0.0
    cy.sample_clamp_indirect = clamp
    cy.caustics_reflective = caustics
    cy.caustics_refractive = caustics
    cy.blur_glossy = 1.0                      # filter glossy: fewer fireflies off wet asphalt
    cy.use_denoising = True
    cy.denoiser = 'OPENIMAGEDENOISE'
    cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    cy.denoising_prefilter = 'ACCURATE'
    if hasattr(cy, 'denoising_quality'):
        cy.denoising_quality = 'HIGH'
    if hasattr(cy, 'denoising_use_gpu'):
        cy.denoising_use_gpu = True
    cy.use_light_tree = True
    sc.render.use_persistent_data = True     # keep BVH/textures between frames
    r = sc.render
    if a.preview:
        r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
    else:
        r.resolution_x, r.resolution_y = 3840, 2160
        r.resolution_percentage = a.scale or 100
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.color_depth = '8' if a.png8 else '16'
    r.image_settings.compression = 15
    # glare halo size is in pixels (octaves): keep it the same fraction of the frame at any
    # resolution (looks were set at 960 px wide with size 5)
    if sc.use_nodes and sc.node_tree:
        import math
        g = sc.node_tree.nodes.get('GLARE')
        if g is not None:
            w = r.resolution_x * r.resolution_percentage / 100
            g.size = max(5, min(9, 5 + round(math.log2(w / 960))))
    r.use_file_extension = True
    return q


def frame_ok(path):
    """A frame counts as done if it is a complete PNG (ends with the IEND chunk)."""
    try:
        if os.path.getsize(path) < 1024:
            return False
        with open(path, 'rb') as f:
            f.seek(-12, os.SEEK_END)
            return f.read()[4:8] == b'IEND'
    except OSError:
        return False


def fmt(sec):
    sec = int(sec)
    return f'{sec // 3600:d}h{sec % 3600 // 60:02d}m{sec % 60:02d}s'


def main():
    a = parse()
    sc = bpy.context.scene
    blend_dir = os.path.dirname(bpy.data.filepath) or os.getcwd()
    backend = setup_device(a.device, hiprt=not a.no_hiprt)
    q = apply_quality(a)
    out = a.out or os.path.join(blend_dir, 'renders', 'preview' if a.preview else
                                ('bench' if a.frame is not None else 'frames'))
    os.makedirs(out, exist_ok=True)
    if a.frame is not None:
        frames = [a.frame]
    elif a.range:
        frames = list(range(a.range[0], a.range[1] + 1))
    else:
        frames = list(range(sc.frame_start, sc.frame_end + 1))
    r = sc.render
    print(f'[render] quality={q} samples={sc.cycles.samples} '
          f'res={r.resolution_x * r.resolution_percentage // 100}x{r.resolution_y * r.resolution_percentage // 100} '
          f'frames={frames[0]}..{frames[-1]} ({len(frames)}) out={out}')
    todo = [f for f in frames if a.overwrite or a.frame is not None or
            not frame_ok(os.path.join(out, f'frame_{f:04d}.png'))]
    skipped = len(frames) - len(todo)
    if skipped:
        print(f'[render] resuming: {skipped} frame(s) already done, {len(todo)} to go')
    times = []
    t_start = time.time()
    for i, f in enumerate(todo):
        final = os.path.join(out, f'frame_{f:04d}.png')
        tmp = os.path.join(out, f'.tmp_frame_{f:04d}.png')
        sc.frame_set(f)
        r.filepath = tmp
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        if not frame_ok(tmp):
            print(f'[render] ERROR: frame {f} was not written correctly', flush=True)
            continue
        os.replace(tmp, final)
        times.append(dt)
        # ETA from the median of the last 8 frames (robust to the slow first frame)
        recent = sorted(times[-8:])
        per = recent[len(recent) // 2]
        left = len(todo) - i - 1
        print(f'[render] frame {f:4d} done in {fmt(dt)} | {i + 1}/{len(todo)} | '
              f'ETA {fmt(per * left)} (at {per:.1f} s/frame)', flush=True)
    total = time.time() - t_start
    print(f'[render] finished {len(times)} frame(s) in {fmt(total)} on {backend}')
    if a.frame is not None and times:
        n = sc.frame_end - sc.frame_start + 1
        print(f'[render] BENCHMARK frame {a.frame}: {times[0]:.1f} s '
              f'-> full shot ({n} frames) ~ {fmt(times[0] * n)} '
              '(the first frame includes BVH build / texture upload; later frames are usually faster)')


main()
