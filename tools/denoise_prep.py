"""Diagnostics for the denoise test: also write the raw (noisy) and denoised beauty passes,
pre-compositor, as EXR next to the frame. Use before render.py:
blender -b scene.blend -P tools/denoise_prep.py -P render.py -- --frame 1 --samples 128 --scale 50 --out DIR"""
import os, sys, bpy
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[argv.index('--out') + 1] if '--out' in argv else 'renders/bench'
sc = bpy.context.scene
sc.view_layers[0].cycles.denoising_store_passes = True
t = sc.node_tree
rl = next(n for n in t.nodes if n.type == 'R_LAYERS')
fo = t.nodes.new('CompositorNodeOutputFile')
fo.base_path = os.path.abspath(out)
fo.format.file_format = 'OPEN_EXR'
fo.format.color_depth = '32'
fo.file_slots.clear()
fo.file_slots.new('noisy_')
fo.file_slots.new('denoised_')
t.links.new(rl.outputs['Noisy Image'], fo.inputs[0])
t.links.new(rl.outputs['Image'], fo.inputs[1])
print('[denoise_prep] writing noisy/denoised EXRs to', fo.base_path)
