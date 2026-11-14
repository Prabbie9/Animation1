# Improvement round (while waiting for the GPU)

CPU test renders only; render presets unchanged. All timings were taken on this 4-vCPU container
with nothing else running.

## 1. Hero asset textures
Sketchfab offers a "source" download for all four assets (taxi 55 MB, Camry 15 MB, hydrant
30 MB, newsboxes 14 MB). Inspected after download:
* the **source** archives hold the authors' original files (FBX/GLB plus textures), but their
  textures are the **same resolution** as the glTF archive's (taxi 2048, hydrant 2048, newsbox
  8192 → capped);
* the **glTF archive** keeps the originals and imports cleanly, whereas only the **GLB**
  download had been downscaled to 1024 px.

So the prep now imports the glTF archive (`assets/sketchfab/<key>/gltf/`, fetched by
`tools/fetch_assets.py` when `gltf_full_res` is set in the manifest) and falls back to the GLB.
Results after `tools/prep_assets.py` (geometry, scale and orientation unchanged):

| asset | before | after |
|---|---|---|
| taxi | 21 maps @ 1024 | 21 maps @ **2048** |
| Camry | 8 @ 1024 | 6 @ **2048**, 2 @ 1024 (the author's originals are 1024) |
| hydrant | 3 @ 1024 | 3 @ **2048** |
| newspaper boxes | 1 @ 1024 | 1 @ **2048** (original 8192, capped by the 2K texture rule) |

4K 1:1 crop of the taxi, frame 96, 128 spp, final denoise (`4K_taxi_crop_*`): the "Yellow Cab"
sticker is now legible (before: a smudge), the "555-2489-222" lettering and plate edges are
crisp, and the bumper/trim shows grime and detail. The panels are sharper but still clean: the
model's paint texture simply has little detail. **Improved, but not "fully detailed": the
asset's own limit.**

VRAM (`tools/vram_estimate.py`): textures 0.90 → **1.27 GB**, total **4.9 → 5.2 GB**, well under
12 GB.

## 2. Splash crowns
Geometry Nodes, on the shared clock: 3000 impact sites on the visible road and sidewalk (none
under the stationary cars). Each site fires every 0.5–1.4 s, and a crown (16-segment open ring
with 8 spikes, 24 triangles) lives 0.1 s: it rises and widens from 0.6 to 2.5 cm, then
collapses. **~340 crowns alive in any frame** (measured at f10/f50/f120). Thin-water shader
fading with distance; camera-visible only (not in reflections/shadows); no motion blur, since the
streak shutter logic applies.

Checked in a 24-frame clip at 960×540 (`splash_clip_*`) and a 12-frame 4K crop of the road
(`splash_4K_crop_*`):
* **at 960×540 they are sub-pixel**: they don't read, and nothing looks wrong;
* **at 4K they read as brief bright blips** where they catch light (two in the crop between f104
  and f105, see the difference image): sparse, plausible, not distracting.

Kept. Render-time cost: see below.

## 3. Lens drops: tested, rejected
Two drops landing on the lens at f150 and f170, modelled as fully defocused discs (blurred copy
of the frame through a soft animated mask; the mask was verified to animate correctly).
Physically correct for f/2 focused at ~11 m, but over this dark, low-contrast frame the effect is
**invisible** (`lens_drop_test_rejected.png`: f149 vs f150, no visible change). Making it visible
would need a bright rim or a refraction smear, which looks fake. **Skipped, as allowed.** The
function stays in `scenelib/lighting.py`, unused.

**Bug found on the way:** the existing vignette set the ellipse node's *editor* width instead of
its mask size, and used a 100× too small blur (the relative blur factor is a percentage). Every
earlier frame therefore had a uniform 12 % darkening with a faint small bright ellipse at the
centre instead of a corner fall-off. Fixed: a soft ~12 % corner vignette. Compositor cost
at 4K is ~1 s either way (measured: 52.1 s without the compositor vs 52.8 s with it, at 1 spp).

## 4. Volumetric light shafts: cost estimate only (not added)
`tools/volume_cost.py`: frame 96, 480×270, 32 spp, adaptive sampling off (identical samples),
single scattering, density 0.004 /m, anisotropy 0.7:

| run | time |
|---|---|
| no volume (two runs) | 30.2 s, 27.7 s |
| volume box over the street | 39.7 s |
| world volume | 39.8 s |

→ **+34 % per frame at equal samples.** Volumes also add noise of their own (visible in
`volumetric_cost_test_none_vs_box.png`), so to match today's noise level expect roughly
**+50 % to +100 %** per frame. That is a substantial cost against an already tight budget. If
you want them after the benchmark, use a low density (~0.001 /m: the 0.004 test is far too
hazy) and limit the medium to the near street.

## Render-time impact of this round (measured)
A/B on frame 96 (960×540, 48 spp), the polish-pass build vs this build, alternated twice:
polish-pass build 143.5 s / 132.0 s; this build 141.5 s / 134.8 s. **No measurable change**
(< run-to-run noise). Splash crowns alone: 28.0 s vs 27.5 s without (volume test settings): ~1–2 %.
