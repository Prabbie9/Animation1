# Traffic and motion stage: review log

All renders are CPU tests (render quality settings untouched until the GPU benchmark).
Motion is analytic (`scenelib/traffic.py`); `tools/motion_check.py` re-measures it from the
evaluated scene at every frame; `tools/flicker.py` measures temporal stability of rendered
(denoised) frames.

## Motion audit (tools/motion_check.py), all 192 frames
```
camry  v 8.00 -> 0.00 m/s, max decel 3.84 m/s^2 (0.39 g), braking from f25 (detected f27),
       stopped by f98, stopping distance 12.2-12.5 m, wheel slip 0.0 mm/frame, wheel bottoms z = 0.000
eb4    v 11.00 -> 0.01 m/s, max decel 4.00, braking from f96, stopped ~f191 after 22.5 m,
       never crosses its stop line (front stays 0.83 m behind it)
wb1/eb2  11.00 m/s constant, cross their stop lines at f2 / f26 on GREEN
wb3    11.00 m/s, crosses at f83 (3.42 s) on AMBER: 4.1 m from the line at amber onset, a
       comfortable stop needs 17.8 m -> proceeding is correct; clears before the all-red
taxi, sb0-2  stationary all shot (wheel contact z = 0.000-0.001 m)
overlaps: none (vehicle-vehicle, vehicle-pedestrian/pole/prop with 0.3 m margin, kerb mounting)
camera sway: yaw +-0.39 deg, pitch +-0.25, roll +-0.23 (< 1 deg), max step 0.018 deg/frame,
       max 2nd difference 0.0016 deg (smooth, no jitter/pops)
```

## Round T1
Renders: contact sheet every 8th frame (480×270, 16 spp); 24-frame clip f17–40 (960×540,
32 spp) covering the Camry's arrival and brake onset (`T1_clip_*.mp4`); the same clip with rain
hidden; a puddle close-up clip f60–71.

Reads correctly: the Camry enters from the left with its brake lamps lit and slows to a stop
beside the taxi; cross traffic flows on green; the yellow hatchback crosses on amber; the
eastbound minivan arrives on the left and stops; the avenue turns green at f185/192. The
oncoming headlights now vary in brightness, size and colour (halogen to LED).

| # | Defect | Cause / verdict | Fix |
|---|---|---|---|
| T1-1 | Camry's right flank turns orange-red as it pulls alongside the taxi (f40–49) | physically real: the taxi's brake lamps (100 cd, ~8 m, ~22° off-axis) light it | kept; partly reduced by T1-4 |
| T1-2 | f185–192: bright green column along the kerb (same family as the red one in note 2) | the camera's mirror image of the NB signal lands exactly on the gutter strip (computed: (6.57, −18.9)); the gutter water was a continuous near-mirror | gutter water: roughness ≥ 0.11 (flowing, rain-stirred), narrower and patchier; still puddles stay glossy |
| T1-3 | Rain hard to see at 960×540 | 1.6 mm streaks are sub-pixel at this size | 2 mm streaks (light rain is 1–2.5 mm), translucent 0.8, opacity 0.6 |
| T1-4 | Kerb face beside the taxi glows red ("glowing wall") | my lamp lights were 160° cones at uniform intensity, so the kerb 60–80° off-axis got full brake intensity; real SAE photometry drops to ~10–20 % there | 100° cone with a full soft falloff |
| T1-5 | Puddle ripples don't read in the close-up | 1.4 cm wavelength is sub-pixel at test resolution; the repair patch had no ripples | 2.2 cm wavelength, 0.7 mm amplitude; ripples added to the patch asphalt |
| T1-6 | Flicker metric high on the road (mean 2nd-diff ~10/255, ~40 % of pixels > 8/255) | **confounded**: the heatmap shows the high values sit on moving cars, edges moving under camera sway, and moving headlight reflections | re-measured with a static camera and stopped traffic (below) |

## Flicker: controlled measurement (note 10)
The moving-camera T1 numbers mix real motion with flicker, so the test was repeated on
frames 150–156 (all-red: Camry/taxi stopped, cross traffic gone except the eastbound minivan
creeping to its line), with the **camera locked** at its f153 pose and rain hidden. Each value is
the mean temporal 2nd difference of the *denoised* frames (480×270), in /255:

| Region | 32 spp | 256 spp | 256 spp + ripples/runoff frozen |
|---|---|---|---|
| road, tail-lamp reflections | 3.06 | 2.19 | **0.62** |
| road, left lanes (contains the creeping eb4 + its headlight reflections) | 3.36 | 2.62 | 1.92 |
| kerb / gutter | 2.75 | 2.17 | **0.13** |
| sidewalk | 0.31 | 0.19 | 0.15 |
| facades | 0.58 | 0.52 | 0.52 |
| sky | 0.03 | 0.02 | 0.02 |

* **Denoiser/sampling flicker** is small and falls with samples: road reflections 0.6/255 at
  256 spp (it will be lower at the final 512 spp / 4K). No region shows localised boiling, and
  the per-frame road curve is flat (no single-frame pops).
* **The remaining temporal variation on the wet road and in the gutter is the ripple/runoff
  animation**, i.e. intended water motion (kerb/gutter: 2.17 → 0.13 when frozen).
* In the real (moving) shot the metric is dominated by genuine motion (cars, camera sway,
  moving reflections) and, from T2 on, by the new rain streaks in each frame. The heatmap
  `T1_flicker_heatmap_moving_camera.png` shows where: car paths, edges under sway, headlight
  reflections. Nothing there is unexplained.
* Fixed during this test: `tools/flicker.py` globbed its own heatmap as an extra "frame";
  the numbers above are from the corrected tool.

## Round T2
Fresh motion audit: identical kinematics; **no problems**. New check: every car that enters
the intersection clears the far crosswalk before the cross-street red: wb1 f61, eb2 f84,
wb3 (amber) **f139**, red at f145.

| # | Item | Verdict |
|---|---|---|
| T1-4 kerb glow | gone: the kerb beside the taxi is neutral (`T2_clip_*`) | fixed |
| T1-3 rain in motion | clearly visible in every frame of the 24-frame clip at 960×540, and in `T2_f192_960.png` | fixed (note 8) |
| T1-2 green column | f192: now a broken streak in the gutter water. The camera stands east of the kerb, so it never sees the kerb face itself | fixed |
| T1-1 Camry red flank | still there as it pulls alongside: physical (taxi brake lamps ~20° off-axis keep ~60 % intensity per SAE) | kept |
| T2-1 | Puddle ripples now animate, but read as hammered metal: ~140 rings/m² at once (two dense layers, all cells active) | one layer, ~25 cells/m², half active per period (~12 visible rings/m², calm water between), 0.5 mm amplitude, film impacts weaker |

## Round T3
* **Ripples (note 10):** the T2 "hammered metal" close-up was not the ripples. The view was
  framed on wet *film* (rings weighted 8 % there), and the glints were the wet asphalt aggregate.
  `T3_water_mask_topdown.png` (debug render of the shader's water mask, 20 m wide, centred 18 m
  south of the intersection) locates the standing water: mostly the gutter strips, plus a few
  lane puddles. A clip aimed at the puddle at (3.3, −26.7) (`T3_puddle_ripples_clip.mp4`)
  shows the puddle as a near-mirror of the lamps and cars, and the frame-to-frame difference
  (`T3_puddle_ripples_frame_and_diff.png`, right) shows clean expanding concentric rings at the
  intended sparse light-rain density. In the beauty frame they read as faint rings catching the
  reflected lights. **Ripples verified in motion.**
* `T3_f096_960.png`: amber phase, Camry stopped beside the taxi, wb3 (yellow hatchback) crossing
  on amber, rain visible against the facades and lamps.
* **Glare (note 7), judged at 960 px:** tail-lamp halos are now light; signal halos small;
  oncoming headlights are varied in size/brightness. To re-judge at 4K in the polish pass (the
  glare size is resolution-aware).

## Remaining after this stage (for the polish pass)
1. The Camry's right flank picks up the taxi's brake light as it pulls alongside: physical, but
   noticeable. Could be softened by aiming the taxi lamps 2–3° inboard (still within SAE).
2. Rain density reads as "steady"; if it should read lighter, 30 % fewer streaks.
3. Most standing water is in the gutters; one or two more lane puddles in the foreground would
   show off the ripples, if wanted.
4. Final glare judgement at 4K.
