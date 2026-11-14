"""Pre-script for tools/clip.py: render a border region of the full 3840x2160 frame (env CROP as
'x0 x1 y0 y1', y from the bottom). blender -b scene.blend -P tools/crop_clip.py -P tools/clip.py -- ..."""
import os, bpy
x0, x1, y0, y1 = (float(v) for v in os.environ['CROP'].split())
r = bpy.context.scene.render
r.use_border = True; r.use_crop_to_border = True
r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y = x0, x1, y0, y1
