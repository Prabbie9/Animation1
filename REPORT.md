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
  f/2 depth of field on the taxi, 180° motion blur on the cars, light glare, faint CA, vignette
  and grain.

## What is still weak (honest list)
1. **Asset texture resolution.** Every Sketchfab model arrived with 1024 px textures (the GLB
   downloads are downscaled). At 4K 1:1 the **taxi body**, the Camry, the foreground hydrant
   and newspaper boxes, the pedestrians and the background cars look soft or plain
   (`docs/stages/07_polish/4K_crop_taxi_road_128spp.png`). Fix: fetch the "source" archives
   (full-resolution textures) for the hero assets and re-run `tools/prep_assets.py`.
2. **Background cars are low-poly** (~5 k triangles). They pass at their distance and in the dark,
   but would not survive a close-up.
3. **Pedestrians are static**, posed scans. They are kept small and backlit at the NW corner as
   the brief allows; nobody walks.
4. **Rain** is a convincing cheap layer, but it has no splash crowns where drops hit the ground,
   and no rain on the camera lens. Near streaks against dark walls read slightly "dashy" at 4K 1:1
   (correct for a 180° shutter, but some viewers read short streaks as snow).
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
**Bottom line: at the `final` preset, expect roughly 5–12 min per 4K frame on the 7800 XT
(central estimate ~7 min, i.e. ~20–25 h for 192 frames). That is well over the 2 min/frame
target. `--quality fast --scale 75` should land around 1.5–2 min/frame (~5–7 h).** This is an
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
   (openbenchmarking.org result 2408080-NE-BLENDERTE19). Ratio ≈ **31×**. Blender Open Data lists
   ~2400 samples/min for the 7800 XT, which is in line. Our scene has hundreds of lights, a lot of
   transparency (rain, glass) and textures, which GPUs handle a little less efficiently than
   BMW27, so I use a ratio range of 25–40×. HIP-RT may add 10–25 % on top.
4. **Result.** 11 500–17 500 s ÷ 25–40 ≈ **290–700 s (5–12 min) per frame at `final`**.
   Per-preset estimates:

| preset | est. min/frame (4K) | with `--scale 75` | 192 frames |
|---|---|---|---|
| `final` | 5–12 (≈7) | 3–6.5 | 20–25 h (100 %) / ~12 h (75 %) |
| `balanced` | 3–7 (≈4.5) | 1.8–4 | ~14 h / ~8 h |
| `fast` | 2–5 (≈3) | 1.2–2.8 (≈1.7) | ~10 h / **~5.5 h** |

Recommended procedure: run `blender -b scene.blend -P render.py -- --frame 96` (final). If it
is above ~3 min, try `--quality balanced --scale 75 --frame 96`, then `--quality fast --scale 75`.
Pick the first that looks clean at 100 % on a 4K monitor. The first frame includes BVH build and
texture upload; later frames with persistent data are usually 10–30 % faster.

Peak VRAM is estimated at **~4.9 GB** (`tools/vram_estimate.py`), comfortably under 12 GB at
every preset.

## What I would improve with more compute
* Run the `--frame 96` benchmark, then choose the cheapest preset/scale that still looks clean at
  4K, and diff ~10 consecutive GPU frames for flicker.
* Full-resolution textures for the taxi, the Camry and the foreground props; a higher-poly
  sedan/SUV for the oncoming queue.
* Splash crowns (short-lived Geometry Nodes instances), a faint raindrop on the lens for a few
  frames, and real displacement for the deepest puddle.
* One or two walking pedestrians under umbrellas (rigged scans), if they can be made convincing.
* Volumetric light shafts around the nearest lamps (true scattering in the rain) instead of only
  the compositor haze, and a light-path-guided render of the wet road at higher samples to remove
  the last reflection noise.
