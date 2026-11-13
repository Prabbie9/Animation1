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
