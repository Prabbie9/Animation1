# Final report: rain-soaked intersection at night

**Scope:** an 8 s, 4K, 24 fps shot, built in Blender 4.5 LTS / Cycles in a CPU-only cloud
container. The final 4K render has not been run (it needs the 7800 XT). Everything below was
judged from CPU test renders: 960×540 stills and clips, 1080p and 4K-crop tests at 128 samples,
and a 960×540 preview of the whole shot. Stage-by-stage evidence is in `docs/stages/*/REVIEW.md`.

## What is convincing (seen in renders, not assumed)
* **Scale and layout.** US intersection in metres: 3.3 m lanes, 15 cm kerbs, 4.5 m corner
  radii, MUTCD markings, signal heads ~5.2 m up on far-side mast arms facing the right
  approaches (checked with close-ups from both directions), 1.75 m reference figure and true-size
  cars in the grey-box pass.
* **Light is physically sourced and in real units.** LED 4000 K avenue lamps vs HPS 2050 K on the
  cross street; ~1/3 of windows lit with mixed colour temperatures; a few late shops lit at
  realistic illuminance; signals at ITE intensities with visor-like beams; SAE-like brake/tail
  photometry; an orange-grey cloud base brighter towards the horizon; exposure set for the wet
  asphalt.
* **Wet road.** Reflections sit where they should (taxi/Camry lamps as compact red streaks, the
  avenue's green at the end, lamp glints receding down the avenue). Standing water follows the
  road's logic: gutters, ruts, the settled trench patch. Rain rings in the puddles are verified in
  motion. Noise in the reflections was cut 14× by making small emitters camera-only, with matching
  lights.
* **Facades with real depth.** Recessed windows, sills, lintels, cornices, setbacks, fire
  escapes, water tanks, typed shopfronts and interiors; brick holds at 4K 1:1 (near building).
* **Traffic logic.** One clock for signals, cars and rain. The Camry stops from 8 m/s over
  12.2 m at a peak of 0.39 g, with brake lamps from the first frame of braking, a nose dip and
  rebound, and no wheel slip. Cross traffic legally clears on amber, one car stops for it, nobody
  enters on red, and the oncoming cars wait. `tools/motion_check.py` re-measures all of this on
  every frame and finds no overlaps, floating, kerb-mounting or red-light entries.
* **Camera.** 3 m dolly with smooth Perlin hand-held sway (< 0.6° range, max step 0.018°),
  f/2 depth of field on the taxi, 180° motion blur on the cars, light glare, faint CA, a soft corner
  vignette (fixed in the improvement round; it had been mis-set) and grain.

## What is still weak (honest list)
1. **Asset texture resolution.** The taxi, Camry, hydrant and newspaper boxes now use the
   authors' full-resolution textures (2048 px; Sketchfab's GLB download had downscaled them to
   1024, the glTF archive keeps the originals). At 4K 1:1 the taxi's decals and sticker are now
   legible, but its panels remain plain: the model's paint texture has little detail
   (`docs/stages/08_improvements/4K_taxi_crop_zoom_before_after.png`). The pedestrians and
   background cars are still 1024 px.
2. **Background cars are low-poly** (~5 k triangles). They pass at their distance and in the dark,
   but would not survive a close-up.
3. **Pedestrians are static**, posed scans. They are kept small and backlit at the NW corner as
   the brief allows; nobody walks.
4. **Rain** is a convincing cheap layer. Splash crowns (~340 alive per frame) were added, but
   they only read at 4K, as brief bright blips. Lens drops were tested and rejected: on this
   dark frame a correctly defocused drop is invisible, and a visible one looks fake. Near streaks
   against dark walls read slightly "dashy" at 4K 1:1 (correct for a 180° shutter, but some
   viewers read short streaks as snow).
5. **The Camry's right flank picks up the taxi's brake light** as it pulls alongside: physically
   right, still noticeable.
6. **Shop interiors** are procedural textures on box rooms: fine through wet glass at 10–30 m,
   not for close inspection.
7. **The skyline** is box towers with procedural windows behind haze: fine as silhouettes, flat if
   you look for detail.
8. **Water is a shading effect.** There is no real displacement: puddle edges have no meniscus,
   and the gutter runoff is a moving normal pattern, not a flowing surface.
9. **Temporal stability** is only measured at CPU sample counts. Denoiser flicker was small
   (0.6/255 at 256 spp, static test), but it must be confirmed on GPU frames by diffing a few
   consecutive 4K frames.
10. **Glare** was judged at 960 px and on 4K crops, not on full 4K frames.

## Render-time estimate for the RX 7800 XT
**Bottom line: at the `final` preset, expect roughly 5.5–13 min per 4K frame on the 7800 XT
(central estimate ~8 min, i.e. ~24–28 h for 192 frames). That is well over the 2 min/frame
target. `--quality fast --scale 75` should land around 1.5–2.5 min/frame (~6–8 h).** This is an
estimate built from CPU measurements and one published GPU result; the `--frame 96` benchmark
replaces it.

How it was derived:

1. **This scene on this CPU (measured).** 4-vCPU Xeon @ 2.1 GHz; `render.py --quality final
   --samples 128 --scale 50` (1920×1080, final denoise) took **1134 s** per frame (three runs,
   1079–1134 s). Motion blur, added later, costs roughly +10 %, so ~1250 s. 4K has 4× the pixels:
   **~5000 s at 128 spp**. The 4K crops (960×540 regions of frame 96 at 128 spp) took 145–353 s
   each, consistent with that.
2. **From 128 to the `final` cap of 512 spp.** Adaptive sampling (threshold 0.01) stops clean
   pixels early, but this is a dark, reflective, noisy scene, so most pixels will use a lot of the
   cap. Assumed effective cost 2.3–3.5× the 128 spp time: **~11 500–17 500 s per 4K frame on
   this CPU**.
3. **CPU → RX 7800 XT ratio (measured on a reference scene).** The standard Blender benchmark
   scene BMW27 (`bmw27_gpu.blend`, 960×540, 1225 spp) took **531.9 s** on this CPU. Phoronix /
   OpenBenchmarking report **17.3 s** for an RX 7800 XT with Cycles HIP in Blender 4.2
   (openbenchmarking.org result 2408080-NE-BLENDERTE19). **Correction (improvement round):**
   the container was restarted between the scene timings (step 1) and the BMW27 run, and the new
   host is ~15 % slower (frame 96 at 960×540/48 spp: 118 s before, 132–144 s after). On the
   step-1 machine BMW27 would take ~460 s, so the ratio is ≈ **27×** (not 31×). Blender Open Data
   lists ~2400 samples/min for the 7800 XT, which is in line. Our scene has hundreds of lights, a
   lot of transparency (rain, glass) and textures, which GPUs handle a little less efficiently
   than BMW27, so I use a ratio range of 22–34×. HIP-RT may add 10–25 % on top.
4. **Result.** 11 500–17 500 s ÷ 22–34 ≈ **340–800 s (5.5–13 min) per frame at `final`**.
   Per-preset estimates:

| preset | est. min/frame (4K) | with `--scale 75` | 192 frames |
|---|---|---|---|
| `final` | 5.5–13 (≈8) | 3.5–7.5 | 24–28 h (100 %) / ~14 h (75 %) |
| `balanced` | 3.5–8 (≈5) | 2–4.5 | ~16 h / ~9 h |
| `fast` | 2.3–5.5 (≈3.5) | 1.4–3.2 (≈2) | ~11 h / **~6.5 h** |

Recommended procedure: run `blender -b scene.blend -P render.py -- --frame 96` (final). If it
is above ~3 min, try `--quality balanced --scale 75 --frame 96`, then `--quality fast --scale 75`.
Pick the first that looks clean at 100 % on a 4K monitor. The first frame includes BVH build and
texture upload; later frames with persistent data are usually 10–30 % faster.

Peak VRAM is estimated at **~5.2 GB** (`tools/vram_estimate.py`; 4.9 GB before the
full-resolution hero textures), comfortably under 12 GB at every preset.

**Render-time impact of the improvement round:** none measurable. On an A/B of frame 96, the
build before vs after (full-res hero textures, splash crowns, vignette fix) gave 143.5/132.0 s vs
141.5/134.8 s. The splash crowns alone cost ~1–2 %.

**Optional volumetric light shafts (not added):** measured at **+34 % per frame at equal
samples** (`tools/volume_cost.py`). Because volumes add noise, matching today's noise level
likely needs **+50 % to +100 %** per frame, i.e. `final` would move to roughly 8–26 min/frame.
Decide after the benchmark; see `docs/stages/08_improvements/REVIEW.md`.

## What I would improve with more compute
* Run the `--frame 96` benchmark, then choose the cheapest preset/scale that still looks clean at
  4K, and diff ~10 consecutive GPU frames for flicker.
* A more detailed taxi paint texture (repaint or bake grime/scratches at 4K) and a
  higher-poly sedan/SUV for the oncoming queue.
* Real displacement for the deepest puddle.
* One or two walking pedestrians under umbrellas (rigged scans), if they can be made convincing.
* Volumetric light shafts around the nearest lamps (true scattering in the rain) instead of only
  the compositor haze, if the benchmark leaves room (cost measured above), and a light-path-guided render of the wet road at higher samples to remove
  the last reflection noise.
