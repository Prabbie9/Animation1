"""Measure the render-time cost of volumetric light shafts (NOT part of the build).
blender -b scene.blend -P tools/volume_cost.py -- MODE OUT.png   (MODE: none | box | world | nosplash)
Adds a homogeneous scattering medium for rain-haze light shafts:
  density 0.004 /m (visibility ~1 km), anisotropy 0.7 (forward scattering of drizzle),
  single scattering (volume_bounces 0, as render.py sets), step rate 1.0.
  'box'   : a 60 x 90 x 14 m domain over the visible street only (the usual, cheaper setup)
  'world' : the medium fills the whole world (most expensive upper bound)
Renders frame 96 at 480x270, 32 spp, adaptive sampling OFF so both runs trace identical samples."""
import sys, time, bpy
mode, out = sys.argv[sys.argv.index('--') + 1:][:2]
sc = bpy.context.scene
cy = sc.cycles
cy.device = 'CPU'; cy.samples = 32; cy.use_adaptive_sampling = False
cy.use_denoising = True
cy.volume_bounces = 0
cy.volume_step_rate = 1.0
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 480, 270, 100
sc.render.use_persistent_data = False
def medium():
    m = bpy.data.materials.new('Haze'); m.use_nodes = True
    n = m.node_tree.nodes; n.remove(n['Principled BSDF'])
    v = n.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = 0.004
    v.inputs['Anisotropy'].default_value = 0.7
    v.inputs['Color'].default_value = (0.9, 0.9, 0.9, 1)
    m.node_tree.links.new(v.outputs[0], n['Material Output'].inputs['Volume'])
    return m
if mode == 'nosplash':          # for measuring the splash crowns' own cost
    bpy.data.objects['SplashCrowns'].hide_render = True
elif mode == 'box':
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 5, 7))
    b = bpy.context.active_object; b.scale = (60, 90, 14); b.data.materials.append(medium())
    b.visible_shadow = False
elif mode == 'world':
    w = sc.world
    v = w.node_tree.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = 0.004; v.inputs['Anisotropy'].default_value = 0.7
    out_n = next(x for x in w.node_tree.nodes if x.type == 'OUTPUT_WORLD')
    w.node_tree.links.new(v.outputs[0], out_n.inputs['Volume'])
sc.frame_set(96)
sc.render.filepath = out
t0 = time.time()
bpy.ops.render.render(write_still=True)
print(f'[volume_cost] mode={mode} time={time.time() - t0:.1f}s')
