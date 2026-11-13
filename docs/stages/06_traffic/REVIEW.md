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
