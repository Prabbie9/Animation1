"""Temporal-stability check on a rendered (denoised) frame sequence.
python3 tools/flicker.py DIR [DIR2 ...]
For every pixel: second temporal difference |I(t-1) - 2 I(t) + I(t+1)| (luminance, display values
0..1). Smooth motion (dolly, sway, moving cars) gives ~0; flicker/boiling gives high values.
Prints per-region statistics and writes DIR/flicker_heatmap.png (bright = flicker)."""
import sys, glob, os
import numpy as np
from PIL import Image

REGIONS = {   # fractions (x0, y0, x1, y1), top-left origin
    'road, tail-lamp reflections': (0.25, 0.72, 0.70, 0.98),
    'road, left lanes': (0.00, 0.72, 0.25, 0.98),
    'kerb / gutter': (0.62, 0.70, 0.75, 0.98),
    'sidewalk right': (0.78, 0.75, 0.98, 0.98),
    'facades upper left': (0.02, 0.05, 0.30, 0.35),
    'sky': (0.60, 0.02, 0.75, 0.12),
}
for d in sys.argv[1:]:
    files = sorted(glob.glob(os.path.join(d, 'f[0-9]*.png')))
    fr = np.stack([np.asarray(Image.open(f).convert('RGB'), dtype=np.float32) / 255 for f in files])
    lum = fr @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    d2 = np.abs(lum[:-2] - 2 * lum[1:-1] + lum[2:])          # (T-2, H, W)
    d1 = np.abs(lum[1:] - lum[:-1])
    h, w = lum.shape[1:]
    print(f'== {d}  ({len(files)} frames, {w}x{h})')
    for name, (x0, y0, x1, y1) in REGIONS.items():
        sl = (slice(None), slice(int(y0 * h), int(y1 * h)), slice(int(x0 * w), int(x1 * w)))
        a, b = d2[sl], d1[sl]
        print(f'  {name:28s} mean 2nd-diff {a.mean() * 255:5.2f}/255  p99 {np.percentile(a, 99) * 255:5.1f}  '
              f'mean frame-diff {b.mean() * 255:5.2f}/255  pixels >8/255 (2nd diff): {(a > 8 / 255).mean():.2%}')
    heat = d2.mean(0)
    heat = np.clip(heat / max(np.percentile(heat, 99.5), 1e-6), 0, 1)
    Image.fromarray((heat * 255).astype(np.uint8)).save(os.path.join(d, 'flicker_heatmap.png'))
    # per-frame curve over the road region to spot single-frame pops
    x0, y0, x1, y1 = REGIONS['road, tail-lamp reflections']
    road = d2[:, int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].mean((1, 2)) * 255
    print('  road 2nd-diff per frame:', ' '.join(f'{v:.1f}' for v in road))
