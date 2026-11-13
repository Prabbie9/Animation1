"""Pre-script for render.py: render only a border region of the full-resolution frame.
blender -b scene.blend -P tools/crop_border.py -P render.py -- --frame N --samples S --out DIR
Region from env CROP='x0 x1 y0 y1' (fractions; y measured from the BOTTOM, as in Blender)."""
import os, bpy
x0, x1, y0, y1 = (float(v) for v in os.environ['CROP'].split())
r = bpy.context.scene.render
r.use_border = True; r.use_crop_to_border = True
r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y = x0, x1, y0, y1
print('[crop] border', x0, x1, y0, y1)
