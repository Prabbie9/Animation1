# Lighting stage: review log

Test renders: 960×540, CPU Cycles, 32 spp + OIDN (the denoiser smears fine detail at this
sample count, so judge light levels and placement, not texture). Exposure is physical: the
lamps, windows and signals are set in real photometric units (see `scenelib/lighting.py`), and
the camera is then exposed for the wet asphalt.

## Pre-fix: Camry "yellow blotches"
`camry_chrome_defect.png`: the imported Camry paint had metallic = 1 everywhere (its
metal/rough map's blue channel is 255 across the whole body), so it rendered as bare chrome. The
irregular yellow patches were the taxi, mirrored in chrome. Fix: a proper automotive paint, i.e.
a dark pigment base with metallic flake under a glossy clear coat (IOR 1.5). It is verified in
round 2 and later.

## Round 1: `round1_f001.png`
| # | Defect | Cause | Fix |
|---|---|---|---|
| L1 | Taxi and Camry glow pink/white all over | tail-lamp mask (R − max(G,B)) also passes yellow paint in linear colour; headlight mask (bright texels at the front) passes yellow paint | red mask in HSV (hue ±0.04 of red, S > 0.6); headlight emission only on dedicated `Optics` lens materials |
| L2 | Road, sidewalk and facades all read as mirrors ("glass city") | water clear coat applied to every surface at roughness 0.04 | water film only on near-horizontal surfaces (normal-based), coat 0.35 × porosity, coat roughness 0.07; vertical surfaces only darken and gloss slightly |
| L3 | Overexposed (windows and shop interiors blown) | +7.5 EV | +6.5 EV |
| L4 | Too much standing water | puddle threshold too low, gutter band 0.65 m | thresholds raised, gutter band 0.45 m |
| L5 | Taxi roof sign unlit | – | back-lit at 250 cd/m² |
| L6 | Flat blue-grey sky | HDRI orientation/tint | (round 2/3) |
| L7 | No atmospheric depth | – | deferred to the polish pass (depth haze) |
| – | Newspaper boxes glow | glTF "unlit" material (emission) from the photoscan | rebuilt as lit surfaces |

## Round 2: `round2_f001_f096_f192.png`
Working: the signal cycle (cross street green at f1 → amber at f96 → avenue green at f192, with
the green reflected in the wet road); red tail-lamp streaks in the asphalt; about 1/3 of
windows lit, in mixed colours.

| # | Defect | Fix |
|---|---|---|
| R2-1 | Taxi brake lamps blow out to large white discs, losing their red | brake 450 cd/m², tail 70 cd/m², pure-red emission (AgX desaturates anything ~5 stops over) |
| R2-2 | Sidewalk is a sharp mirror of the shop windows | concrete: film porosity 0.55, coat roughness 0.22 |
| R2-4 | Upper facades evenly lit: lamps throw light sideways | 130° cone, i.e. full cut-off (real cobra heads put ~0 lm above 70° from nadir) |
| R2-5 | Shop interiors are flat white boxes | 300 lx (open) / 60 lx (after hours); darker interior surfaces; shelving to come in the materials stage |
| R2-6 | No sky glow at the end of the avenue; the HDRI has a hot lamp (~350× the sky) | HDRI clamped and rotated so the town glow sits due north; normalised to a median of 0.15 cd/m² |
| R2-8 | Cool-white windows clip to plain white | window luminance 45 → 28 cd/m² |
| R2-10 | Southbound cars (facing the camera) have no headlights | optics mask thresholds were above the headlamp texels' luminance (0.1–0.3 linear) |

## Round 3: `round3_f001_f096_f192.png`
Better: the southbound sedan's headlights now show, with a streaked reflection running towards
the camera; the sidewalk reflections are blurred; there is a warm sky glow down the avenue.

| # | Defect | Fix |
|---|---|---|
| R3-1 | Taxi brake lamps still pink-white discs. At a physical ~450–1000 cd/m² they sit 6+ stops over the road exposure, and AgX bleaches anything that far over to white. Real sensors keep narrow-band red sources reading red. | brake set to 140 cd/m² (tail 35). **A deliberate departure from physical values**, recorded for the final report |
| R3-2 | Upper facades evenly lit, too bright for a night street | isolated with "one source only" renders (`round3_isolation_*.png`: sky / street lamps / shops / emissives). The sky alone is correctly dark and the lamps light the street and lower floors. **The shops were the culprit**: 51 lit shops at ~11 000 lm each (correct for 300 lx), i.e. more than half of all shopfronts lit at 11 pm. Fix: weekday-11-pm mix (mostly closed, the odd deli or bar open) and 30 lx after-hours security lighting. On the way, the lamp lens meshes were found emitting from all six faces and being light-sampled; they are now down-facing quads with emission sampling off (camera-visible only). |
| R3-3 | Black SUV's headlights faint | to check in round 4 |
| R3-4 | Road reads a little like polished concrete | partly the denoiser at 32 spp; the rest (patches, tyre polish, oil, grime) is materials-stage work |

## Round 4: `round4_f001_f096_f192.png`
The upper facades now fall off into darkness; brake lamps read red with a hot core; the
reflections carry their sources' colour (red behind the taxi, green at f192).

| # | Defect | Fix |
|---|---|---|
| R4-0 | (process) the whole city reshuffled between rounds: one RNG stream fed every building, so changing the shop mix changed every lot | per-lot RNG seeded from the lot name; edits now stay local |
| R4-2 | Open shops (SLICE) are blank white boxes, obviously CG | procedural shelving with mixed product colours; open shops 220 lx |
| R4-3 | Black SUV headlights weak | verified in a close-up (`round5_southbound_headlights_closeup.png`): low beams and fog lamps are lit and reflect correctly; it is simply small and partly hidden at the far stop line |
| R4-5 | End of the avenue is a black void; the skyline is still grey-box blocks | skyline towers get a procedural window grid (~25 % lit, 2800–5000 K) and steady-red aviation lights on the 5 tallest |
| R4-6 | No atmospheric depth; lamps just stop | mist-pass haze in the compositor: quadratic from 25 m, full at 600 m, max 55 %, colour ~2600 K at 0.35 cd/m² (scattered sodium/LED light in drizzle) |

## Round 5: `round5_f001_f096_f192.png` (end of the lighting stage)
- Exposure is set for the wet asphalt. The road reads through its reflections: long red tail-
  and brake-lamp streaks under the taxi and Camry, a green streak along the kerb once the
  avenue turns green (f192), and lamp glints receding down the avenue.
- Light sources: avenue LED 4000 K (cobra heads, 12 000 lm; 15 000 lm on the four mast-pole
  luminaires over the intersection); cross street HPS 2050 K, visible left and right of the
  intersection; ~1/3 of windows lit in mixed colour temperatures; a few late shops; signals; car
  lamps; and the orange-grey sky glow with haze.
- The signal cycle is visible: cross-street green (f1) → amber (f96) → avenue green (f192).

Remaining, carried forward:
| # | Item | Stage |
|---|---|---|
| R5-1 | Sky and haze slightly too saturated/orange; mix in a little grey | polish |
| R5-2 | Taxi brake lamps are still large pink-white discs (a large lens area; the other cars read red) | polish (bloom will help; possibly a darker lens texture) |
| R5-3 | Foreground SE sidewalk is a uniform bright grey under the mast-pole luminaire | materials (grime, slab variation) |
| R5-4 | Road surface reads clean/uniform: needs patches, tar seams, tyre polish and oil | materials |
| R5-5 | No rain yet (streaks, ripples, splashes) | rain stage |
