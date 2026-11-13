# Materials + rain stage: review log

Test renders are 960×540 CPU stills (32–48 spp + OIDN) unless noted.

## Brake lamps (note 1)
The 140 cd/m² patch is gone. Lamps now run at **physical** luminance (SAE J586/J585: brake
80–185 cd from ~0.03 m² → peak ~4000 cd/m²; tail ~250 cd/m²). The emission is **concentrated in
hotspots** that follow each lens texture's brightness (bulb/LED cores behind the diffuser), so
the emitting area is much smaller than the whole red lens. The colour is the sRGB gamut-edge
red (real lamp red is even more saturated).

`brake_round1_*.png` (1080p crop, 64 spp):
A = AgX, no glare: bright but mostly white cores with a thin red rim.
B = AgX + glare and C = Khronos PBR Neutral + glare: red halos read "bright red lamp" immediately,
but the glare was far too strong (oncoming headlights became fog balls).
D = old 140 cd/m² patch, for reference: pink and weak.

`brake_round2_*.png`: subtle glare (Fog Glow, threshold 6 over exposure, mix −0.88). Both
transforms now give red, bright lamps. **Kept AgX**: PBR Neutral's lamps are marginally more
saturated, but it shifts the whole frame warmer and higher-contrast and blooms the street
lamps more; AgX keeps the low-contrast filmic look the brief asks for. Final glare mix −0.9.

## Lighting carry-overs (notes 2–5)
- Sky (note 3): rebuilt as a gradient: horizon 0.22 cd/m² warm grey (cloud base lit by the city),
  zenith 0.08 cd/m² cool grey. The HDRI now contributes cloud texture only (desaturated,
  normalised), so its colour and lamps no longer leak in. Haze uses the horizon colour.
- NW shop interior (note 4): the multicoloured grid is replaced by per-type interiors. Shelving
  (deli/pharmacy) stops at 2.1 m with muted stock, gaps above each row and shelf lips; there is
  also a bar (wood, back-lit bottle band), a laundromat (front-loaders, dryers above) and a
  pizzeria (white subway tile, steel counter, lit menu boards).
- Window spread (note 5): brightness multipliers narrowed to 0.45–0.85 (were 0.25–1.15),
  curtain/blind ranges tightened, base 24 cd/m².
- Kerb streak (note 2): see M1/MR2 and the 128 spp test below.

## Round M1 (materials): `M1_*.png`
Road: anti-tiled asphalt, ±12 % macro tone, polished darker wheel paths, oil in lane centres
(densest by the stop lines, faint thin-film sheen when wet), gutter grime, a trench patch with
tar seams, tar snakes, patchy puddles of varying size. Sidewalk: per-slab tone, stains, gum.
Facades: runoff streaks, wet splash zone, per-building tint/hue variation.

| # | Defect | Fix |
|---|---|---|
| M1-1 | Every interior is floor-to-ceiling shelving (the pizza shop looks like a library) | per-type interiors, fixtures ≤ 2.1 m |
| M1-2 | Crosswalk paint wear far too strong (camouflage pattern) | ~15 % worn through |
| M1-3 | Red kerb streak still continuous | gutter water roughness 0.02–0.08 (was 0.012–0.06), coverage broken up more |
| M1-4 | Oncoming headlight glare slightly large | glare mix −0.9 |

## Round MR2 (rain): `MR2_*.png`
Rain: Geometry Nodes streak instancer (6 m/s fall, 12.5 cm streaks = 180° shutter at 24 fps,
camera-facing, translucent + glossy water shader); puddle impact rings (two Voronoi layers, rings
at 0.22–0.25 m/s, 1.4 cm wavelength, fading in ~0.5 s, strong in standing water and faint on
the film); gutter runoff advected towards new kerb-inlet catch basins at each corner; 1346
awning drips in free fall (z = z0 − g t²/2, streak length from velocity); droplets and sliding
rivulets on all vehicle glass and beads on the clear coats; tandem wipers on the oncoming cars
(45 sweeps/min).

| # | Defect | Fix |
|---|---|---|
| RS-1 | Rain too dense and uniformly visible, including in front of dark facades: reads as a heavy downpour overlay, not light rain catching the lamps | streaks halved (22 k near, 18 k far); translucent albedo 0.85 → 0.35; opacity 0.45 → 0.3 (glossy glints kept) |
| RS-3 | Wipers invisible behind oncoming headlight glare at 25 m | none needed: correct for that distance; they exist and run on the clock |
| RS-4 | Puddle ripples faint at test resolution | judge at 128 spp |

## High-sample denoise test (note 8): 1920×1080, 128 spp, final denoise settings
Rendered with `render.py --quality final --samples 128 --scale 50 --frame 1` (OIDN, prefilter
Accurate, albedo + normal guides, adaptive threshold 0.01). `tools/denoise_prep.py` also saves the
raw (noisy) and denoised beauty passes as EXR before compositing, and `tools/noise_report.py`
measures the residual (noisy − denoised) luminance per region. CPU time: ~18–19 min per frame.

| Region | Test 1: mean / residual rms / fireflies | Test 2 (clamp 3, rain hidden from glossy, OIDN High) | Test 3 (+ camera-only lamp emitters with matching small lights) |
|---|---|---|---|
| wet road, tail-lamp reflections | 0.0120 / 0.0421 / 3.0 % | 0.0118 / 0.0420 / 3.0 % | 0.0017 / **0.0030** / 1.6 % |
| kerb / gutter | 0.0168 / 0.0154 / 1.4 % | 0.0168 / 0.0154 / 1.4 % | 0.0160 / 0.0153 / 1.6 % |
| dark facade | 0.00054 / 0.00080 / 3.1 % | same | 0.00053 / 0.00057 / 3.1 % |
| sidewalk | 0.00071 / 0.00155 / 1.1 % | 0.00070 / 0.00140 / 1.1 % | 0.00057 / 0.00096 / 0.9 % |

Findings:
* **Test 1 failed the hard case.** The raw road was a mass of speckle (residual ~3.5× the
  signal). After denoising, the reflections became soft, blotchy "watercolour" shapes, with a
  broad white smear under both cars (`denoise_test1_road_noisy_denoised_final.png`). That kind of
  reconstruction shimmers from frame to frame.
* **Test 2 changed nothing.** The noise was not indirect fireflies or the rain.
* **Cause:** direct reflections, in near-mirror water, of *small textured mesh emitters*: the
  brake/tail-lamp hotspot textures, the signal lenses, and the oncoming headlamp glass.
  Cycles samples these poorly.
* **Fix (test 3):** those emitters are now visible to camera rays only. Each gets a matching small
  analytic light that Cycles samples directly: brake/tail ~108 cd red spots placed at the lamp
  centroids (found by sampling the lamp textures through the UVs); signal lenses ~600 cd spots
  keyed on the same timeline; headlamps via the existing beam spots. Road residual noise fell 14×
  and fireflies halved. The reflections are now compact red streaks; the smear is gone
  (`denoise_test1_vs_test3_road_crops.png`).
* **No real banding.** The stepped rings seen around lamps in previews are a viewer quantisation
  artefact; the 16-bit frame's halo profile is smooth (252 levels).
* **Kerb streak (note 2):** at 128 spp it reads as tail-lamp light reflected in broken gutter
  water, not a glowing wall. The gutter water is now rougher (0.02–0.08) and patchier.
* **Remaining risk:** ~1.6 % fireflies on the road before denoising. At 4K, 512 adaptive samples
  roughly halve the per-pixel noise again. Temporal stability of the denoised reflections must be
  checked on the 24-frame clip (traffic stage), by diffing consecutive frames.
* The glare halo size is now resolution-aware (`render.py` sets it from the output width) and
  one step smaller.

## Round MR3: `MR3_*.png`
Rain visibility restored to "light rain" (translucent 0.6, opacity 0.4, 40 k streaks): visible
where it catches the lamps and faintly against dark facades. Awning drips under the right-hand
awning. Puddle ripples are subtle in stills (`MR3_ripples_closeup.png`); judge them in motion.
