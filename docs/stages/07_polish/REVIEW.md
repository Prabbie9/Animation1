# Polish pass: review log

CPU test renders only; `render.py` quality presets unchanged.

## Changes
| Note | Change |
|---|---|
| 1 rain | 40 k → 23.5 k streaks (−40 % overall: near −30 %, far −55 %); opacity falls off with camera distance (×1.0 within 4 m → ×0.08 at 25 m, smoothstep); far streaks get a rougher (softer) glossy lobe |
| 2 green spill | the signal lights' intensity is unchanged (600 cd: in range for 300 mm LED heads per ITE VTCSH), but their beam now follows LED-signal photometry: a 44° cone with full falloff (~50 % at 10°), aimed 4° down like real heads. The awnings' near-mirror water film was the main culprit (blue at f1, green at f188); fabric now gets only a soft sheen (porosity 0.15) |
| 3 puddle | settled utility-trench patch across the NB lanes. The rutted wheel paths just north of it hold a puddle placed on the camera↔taxi-tail-lamp mirror line (computed reflection point (5.2, −20.4) → (5.2, −19.9) over the dolly), so it shows the red lamps. No moving tyre crosses it |
| 4 Camry | brake lamps follow SAE J586 falloff more closely (70° cone, full blend; only ~20–35 % required at 20° H), so the Camry no longer reads as a red car at f40 |
| 5 look | physical exposure (unchanged, +6.5 EV over photometric units); DOF f/2.0 with 6 blades; glare light and resolution-aware; chromatic aberration (Lens Distortion dispersion 0.004); vignette ~12 %; luminance-proportional film grain ±2.5 %, new each frame |
| 6 motion blur | 180° shutter (0.5 frame, centred) on cars, wheels (3 motion steps) and camera. Rain excluded: its streak length already models the shutter, and drops wrap back to the top of the rain volume between frames, so real motion blur would smear them into tall streaks |
| 7 grade | AgX "Medium Low Contrast", no colour-wash grade |

## Round P1 (`P1_f001_f040_f096_f188.png`)
* Reads well: lighter rain still visible; natural motion blur on the passing Camry and on the cross
  traffic (wheels blur rotationally); signal glows are not smeared (material animation is per frame); taxi
  yellow stays yellow; red/amber/green distinct; sky = warm grey glow low, cooler overhead.
* P1-1 the puddle read as a black hole: correct mirror, but it reflected dark facades and the
  taxi's underside. **Moved onto the tail-lamp mirror line.**
* P1-2 the right-hand awning turned blue (f1) / green (f188): the wet layer had given the fabric a
  mirror film. **Fixed** (see note 2).
* P1-3 Camry still reads red at f40. **Fixed** (see note 4).

## Round P2 (`P2_f001_f040_f188.png`)
Puddle shows the taxi's red lamps at the bottom of the frame in the first half of the shot (the
camera dollies past it later); awning dark red; Camry dark grey. Remaining green at f188 is the
signal *reflection* in the gutter water (physically placed), not spill.

## 4K detail check (note 9): 960×540 crops of the 3840×2160 frame 96, 128 spp, final denoise
Rendered with `render.py --quality final --samples 128` plus `tools/crop_border.py`.
CPU time: 2.5–6 min per crop.
* `4K_crop_right_building_brick_128spp.png`: **holds**. Brick courses, mortar, sill, mullions
  and the side-on signal head (amber) are crisp at 1:1 pixels.
* `4K_crop_taxi_road_128spp.png`: decals, plate and roof sign are legible and the road
  reflections are clean, but the **taxi body texture is soft**: every downloaded Sketchfab
  texture is only 1024 px (the GLB downloads arrive downscaled), the taxi included, so the panels
  and lower bumper look plain at 1:1. Same for the Camry, hydrant, newspaper boxes,
  pedestrians and pack cars. The Poly Haven surfaces (2K; 4K asphalt) hold up.
* `4K_crop_distant_rain_before_after.png`: **defect found and fixed**. Distant streaks read as
  bright "snow" against the dark wall at 4K; the stronger distance falloff and 35 % fewer far
  streaks removed it. The streaks left in that crop are near rain (5–15 m) catching the
  lamps: that is what 6 m/s drops look like through a 1/48 s shutter.

## VRAM (note 10): `tools/vram_estimate.py`
~4.9 GB peak at 4K, under the 12 GB budget: textures 0.9 GB (102 images; the 4K asphalt maps are
the largest), geometry 0.24 GB (1.24 M unique triangles, 30 k instances incl. rain), buffers
0.76 GB, OIDN ~2 GB, runtime ~1 GB. First reductions if needed: `--scale 75`, OIDN on the CPU,
lighter versions of the two scanned pedestrians and the newspaper-box scan (0.7 M triangles).

## Handoff checks (note 12), on a fresh `git clone` into a path containing a space
* `build_scene.py` rebuilt `scene.blend` from scratch in 8 s; 104 images, all relative, none
  missing; no external libraries or fonts.
* `render.py`: `--device HIP` on a machine without a HIP GPU falls back to CPU with a clear
  message; `--frame 96` writes `renders/bench/` and prints the full-shot estimate; `--range 1 3`
  writes three 16-bit PNGs; after truncating frame 2 (simulated crash), a rerun reported
  "2 already done, 1 to go" and re-rendered only frame 2; `--preview` writes 1920×1080 to
  `renders/preview/`.
* HIP itself cannot be exercised without AMD hardware. The device code enables only HIP devices
  and HIP-RT when Blender lists them.
* `encode.sh`: h264 (High, yuv420p, 24 fps), h265 (Main 10) and prores (422 HQ, 10-bit) all
  produced valid files.

## Round P3 (`P3_f096.png`) and the full preview
* f96 after the distant-rain fix: rain reads as steady light rain, visible but not dominant.
* Full shot preview, 192 frames at 960×540, 12 spp (CPU, ~30 s/frame): `docs/preview/
  preview_full_960x540.mp4`; contact sheet `docs/preview/contact_sheet_every8.jpg`. The
  timeline reads correctly from start to end.
* Flicker on two 24-frame preview windows (f100–123, f160–183): flat per-frame curves; the only
  spike is f179–181, where the avenue signals switch to green and the reflections change colour.
  The absolute levels include 12-spp noise, rain and camera motion, so they are not comparable
  with the static 256-spp test.

## Render-time reference measurement
Blender's standard BMW27 scene (`bmw27_gpu.blend`, 960×540, 1225 spp) took 531.9 s on this
CPU, against 17.3 s published for an RX 7800 XT with HIP in Blender 4.2 → ~31× ratio. Full
derivation in `REPORT.md`.
