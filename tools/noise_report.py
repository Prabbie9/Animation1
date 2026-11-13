"""Compare noisy vs denoised EXRs from tools/denoise_prep.py.
blender -b scene.blend -P tools/noise_report.py -- DIR
Prints residual-noise stats per region and writes view-transformed PNGs (noisy/denoised)."""
import sys, os, glob, bpy, numpy as np
d = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
def load(prefix):
    f = sorted(glob.glob(os.path.join(d, prefix + '*.exr')))[-1]
    im = bpy.data.images.load(f)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]   # top row first
    im.save_render(os.path.join(d, prefix + 'view.png'), scene=sc)
    return a
nz, dn = load('noisy_'), load('denoised_')
h, w, _ = nz.shape
lum = lambda a: a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
regions = {   # (x0, y0, x1, y1) as fractions of the frame (top-left origin)
    'wet road, tail-lamp reflections': (0.25, 0.78, 0.70, 0.98),
    'kerb / gutter streak':            (0.62, 0.70, 0.75, 0.98),
    'dark facade (upper left)':        (0.02, 0.05, 0.30, 0.35),
    'sky':                             (0.60, 0.02, 0.75, 0.12),
    'sidewalk foreground right':       (0.78, 0.75, 0.98, 0.98),
}
for name, (x0, y0, x1, y1) in regions.items():
    sl = (slice(int(y0 * h), int(y1 * h)), slice(int(x0 * w), int(x1 * w)))
    Ln, Ld = lum(nz[sl]), lum(dn[sl])
    res = Ln - Ld
    print(f'NOISE {name:34s} mean={Ld.mean():.5f}  residual rms={res.std():.5f}  '
          f'relative={res.std() / max(Ld.mean(), 1e-9):6.2%}  fireflies(>10x mean)={(Ln > 10 * max(Ld.mean(),1e-9)).mean():.4%}')
