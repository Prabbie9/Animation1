# Rain-soaked intersection at night: 8 s, 4K, 24 fps (Blender 4.5 LTS, Cycles)

A US four-way intersection at about 11 pm on a late-autumn night in steady light rain. The
camera dollies 3 m along the kerb towards a taxi waiting at a red light, while the cross street's
signal runs out its amber.

> **Status:** built and verified with CPU test renders; the final 4K render is pending a GPU
> benchmark. Preview of the whole shot (960×540, 12 spp, CPU):
> `docs/preview/preview_full_960x540.mp4`, plus `docs/preview/contact_sheet_every8.jpg`. The honest assessment and the
> render-time estimate are in `REPORT.md`; per-stage review renders are in `docs/stages/`.

## 1. Quick start

You need **Blender 4.5 LTS**. Everything else (assets, textures, HDRI) is in this repository.
All paths are relative, so the project works from any folder on Windows, macOS or Linux.

### Step 1: generate `scene.blend`
`scene.blend` is **not stored in git**. It is generated from the Python scene builder, which
takes about 10 seconds:

```
blender -b --factory-startup -P build_scene.py
```

This writes `scene.blend` next to `build_scene.py`. Run it again after any `git pull`.
On Windows, `blender` is usually
`"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"`, so either use that full path
or add the folder to `PATH`. Run the command from the repository folder.

### Step 2: benchmark one frame on your GPU
```
blender -b scene.blend -P render.py -- --frame 96
```
This prints the device it found (it should say `HIP (HIP-RT on): AMD Radeon RX 7800 XT`), the
time for the frame, and an estimate for the whole shot. The frame is written to
`renders/bench/`. Please report the time back so the settings can be tuned.

### Step 3: render the shot
```
blender -b scene.blend -P render.py
```
This writes 16-bit PNGs to `renders/frames/frame_0001.png` … `frame_0192.png`, printing the
time per frame and an ETA.

**Resuming:** if the render is interrupted (crash, reboot, Ctrl+C), run the same command again.
Finished frames are skipped. Every frame is written to a temporary file and renamed only once it
is complete, so a half-written file is never mistaken for a finished frame. Use `--overwrite`
to force a re-render, or `--range A B` to render part of the shot (for example on two machines).

### Step 4: encode
```
./encode.sh            # H.264 CRF 14, yuv420p, 24 fps     -> renders/intersection_h264.mp4
./encode.sh prores     # ProRes 422 HQ 10-bit (grading)   -> renders/intersection_prores.mov
./encode.sh h265       # HEVC 10-bit CRF 16                -> renders/intersection_h265.mp4
```
On Windows, run it from Git Bash or WSL. Alternatively, run the equivalent ffmpeg command in
PowerShell:
```
ffmpeg -framerate 24 -i renders/frames/frame_%04d.png -c:v libx264 -preset slow -crf 14 -tune film -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 renders/intersection_h264.mp4
```

## 2. Windows + AMD GPU setup (RX 7800 XT)

1. Install the latest **AMD Software: Adrenalin Edition** driver. HIP in Blender 4.5 needs a
   recent driver.
2. Blender > Edit > Preferences > System > Cycles Render Devices > **HIP**. Tick the
   RX 7800 XT and **Enable HIP RT** (hardware ray tracing).
   `render.py` selects HIP and HIP-RT automatically in background mode, so the preferences only
   matter for interactive use.
3. If HIP-RT gives artefacts or crashes with your driver, run with `--no-hiprt`. This is
   typically 10–25 % slower but very stable.
4. Leave the CPU unticked: mixing the CPU into a GPU render usually makes it slower.

## 3. Quality / speed ladder

All presets render 3840×2160 unless you add `--scale`. All use adaptive sampling (minimum
samples automatic), OpenImageDenoise with **prefilter Accurate, albedo + normal guides, quality
High, on the GPU**, indirect clamp 3.0, glossy filter 1.0, light tree on, persistent data on, a
180° motion-blur shutter, and 16-bit PNG output. Only the sampling and bounce limits change:

| `--quality` | max samples | adaptive noise threshold | bounces: total / diffuse / glossy / transmission | expected time vs `final`* | what you give up |
|---|---|---|---|---|---|
| `final` (default) | 512 | 0.010 | 8 / 3 / 4 / 8 | 1.0× | nothing: the reference |
| `balanced` | 320 | 0.015 | 8 / 3 / 4 / 8 | ~0.6–0.65× | slightly softer fine grain in the darkest areas (shadowed facades, the road under the cars); the denoiser fills in a little more. Hard to see in motion. |
| `fast` | 192 | 0.025 | 6 / 2 / 3 / 6 | ~0.35–0.45× | visibly smoother, slightly "painted" texture in dark regions; reflections of the small lamps in the wet road can soften and shimmer a little between frames; one fewer diffuse bounce makes the deepest corners (shop interiors, under awnings) a touch darker |
| `draft` | 64 | 0.050 | 4 / 2 / 2 / 4 | ~0.15× | blotchy denoising, unstable reflections: layout/animation checks only |

\*Time scales roughly with the sample cap, but adaptive sampling stops many pixels early, so the
real ratios on the 7800 XT are unknown until the `--frame 96` benchmark is run. Treat these as
estimates.

Resolution is the other big lever:

| `--scale` | resolution | pixels vs 4K | what you give up |
|---|---|---|---|
| 100 | 3840×2160 | 1.0× | – |
| 75 | 2880×1620 | 0.56× | a slight softening after upscaling to 4K; rain streaks and brick texture lose some crispness. Generally less visible than dropping from `final` to `fast`. |
| 50 | 1920×1080 | 0.25× | a 1080p deliverable |

Suggested order if the benchmark is over budget (2 min/frame): first `--quality balanced`,
then `--scale 75`, then both, then `--quality fast`. `--samples N` overrides the cap of any
preset.

Noise notes: small emitters (street-lamp lenses, signal lenses, brake lamps, headlamp glass)
are visible to the camera only, and matching small lights do the lighting and the
reflections. This cut the noise in the wet-road reflections 14× (see
`docs/stages/05_materials_rain/REVIEW.md`). The remaining temporal variation on the road is
the intended ripple/runoff animation (`docs/stages/06_traffic/REVIEW.md`).

### VRAM
Estimated peak at 4K: **~4.9 GB** (run `blender -b scene.blend -P tools/vram_estimate.py`).
That covers textures 0.9 GB (102 images, no mipmaps on GPU; the three 4K asphalt maps are the
largest at 64 MB each), geometry 0.24 GB (1.24 M unique triangles, 30 k instances including
the rain), 4K render buffers 0.76 GB, GPU OIDN ~2 GB, and runtime overhead ~1 GB. Repeated
assets are instanced and textures are capped at 2K (asphalt excepted). If you ever hit
out-of-memory errors: first `--scale 75`, then set the OIDN denoiser to the CPU, then reduce
the two scanned pedestrians and the newspaper-box scan (0.7 M triangles together).

## 4. `render.py` options

```
blender -b scene.blend -P render.py -- [options]
  --quality {final,balanced,fast,draft}
  --preview              1920x1080 draft settings -> renders/preview/
  --frame N              benchmark one frame (prints time and full-shot estimate)
  --range A B            render frames A..B
  --samples S  --scale P  --device {auto,HIP,OPTIX,CUDA,ONEAPI,METAL,CPU}  --no-hiprt
  --out DIR  --overwrite  --png8
```

## 5. Repository layout

| Path | What |
|---|---|
| `build_scene.py` | builds `scene.blend` from scratch (layout, assets, buildings, lights, animation) |
| `scenelib/config.py` | all dimensions (metres), camera, signal timing (the single clock) |
| `scenelib/layout.py` | roads, kerbs, US (MUTCD) markings, poles, signal masts, camera |
| `scenelib/buildings.py` | procedural facades with real depth, shopfronts, fire escapes |
| `scenelib/lighting.py` | sky glow, street lamps, vehicle lamps, exposure (photometric units) |
| `scenelib/surfaces.py`, `materials.py` | asphalt with puddles and gutter water, shared wetness model |
| `scenelib/signals.py` | signal heads and the signal cycle |
| `scenelib/traffic.py` | vehicle motion (analytic, one clock), wheel spin, brake lamps, suspension pitch |
| `scenelib/rain.py` | rain streaks (Geometry Nodes), ripples, runoff, drips, wet vehicles, wipers |
| `render.py`, `encode.sh` | production render and encode |
| `assets/lib/` | prepared assets (metric, oriented, textures ≤2K) used by the builder |
| `assets/polyhaven/` | Poly Haven textures and HDRI (CC0) |
| `assets/manifest.json` | source, licence and author of every asset; `CREDITS.md` is generated from it |
| `tools/` | asset fetch/prep scripts and test-render helpers used during development |
| `docs/stages/` | review renders from each stage of the verification loop |

### Re-creating the assets from source (optional)
The prepared assets are committed, so this step is not needed. To rebuild them, download the
raw files (Poly Haven needs no key; for Sketchfab, set `SKETCHFAB_TOKEN` to your API token) and
then re-run the prep script:
```
python3 tools/fetch_assets.py
blender -b --factory-startup -P tools/prep_assets.py
```

## 6. Traffic timeline (what moves, when, and why)

One clock drives everything: `t = (frame - 1) / 24` s (frame 1 = 0.0 s, frame 192 = 7.96 s).
Country: USA, right-hand traffic. Positions are in metres from the intersection centre
(+Y = north, +X = east). All motion is computed analytically in `scenelib/traffic.py` and
baked one key per frame. `tools/motion_check.py` re-measures it from the evaluated scene
(speeds, decelerations, stopping distances, wheel slip, ground contact, overlaps, stop-line
crossings versus signal state).

**Signals** (`scenelib/config.py`):

| t (s) | frame | Avenue (NB/SB, our direction) | Cross street (EB/WB) |
|---|---|---|---|
| 0.0 | 1 | red | green |
| 3.0 | 73 | red | **amber** (3.0 s) |
| 6.0 | 145 | red | red (all-red clearance 1.5 s) |
| 7.5 | 181 | **green** | red |

**Vehicles**

| Vehicle | Lane | Behaviour | Key times |
|---|---|---|---|
| Taxi (Crown Victoria) | NB kerb lane, first at the stop line | stopped all shot, brake lamps on | at green (7.5 s), a ~1 s reaction means it cannot move before the shot ends |
| Camry (dark grey) | NB inner lane, passes the camera on its left | 8.0 m/s (29 km/h); brakes from **t = 1.0 s (f25)**: brake lamps on, nose dips (pitch spring 1.4 Hz, ζ 0.45); smoothstep speed profile, peak 3.84 m/s² (0.39 g) | stops at **t ≈ 4.1 s (f98)** after 12.5 m, front 0.7 m behind the taxi's front; small nose rebound after stopping |
| SB queue: SUV, gold sedan, minivan | SB lanes, far stop line | stopped, headlights on (varied output and colour temperature), wipers 45/min | stay stopped through f192 (same reaction-time argument) |
| WB pickup (wb1) | WB lane (north half of the cross street) | through on green at 11 m/s (25 mph) | crosses its stop line at f2 (green), passes the centre at 1.3 s |
| EB wagon (eb2) | EB lane (south half) | through on green, 11 m/s | crosses its stop line at f26 (green), passes the centre at 2.3 s |
| WB hatchback (wb3) | WB lane | 4.1 m from its stop line at amber onset; stopping comfortably (3.4 m/s²) would need 17.8 m, so it **legally proceeds on amber** | enters at f83 (3.4 s, amber), clears the far crosswalk before the all-red at 6.0 s |
| EB minivan (eb4) | EB lane | 32.6 m back at amber onset: 0.9 s reaction, then brakes (peak 4.0 m/s², 22.5 m) | brake lamps from f96 (3.9 s); stops **0.8 m behind its stop line** at ~f191; never enters |
| Parked cars | cross-street parking lanes | parked, lights off | – |
| Pedestrians (2) | NW corner, facing south | waiting at the kerb to cross the cross street (DON'T WALK: the parallel avenue phase is red) | static |

**Camera:** 3 m dolly north along the east kerb (y −29 → −26 m, constant 0.375 m/s) at 1.85 m
(1.7 m eye height above the 15 cm kerb). Hand-held sway from smooth Perlin noise: yaw ±0.39°,
pitch ±0.25°, roll ±0.23° (all < 1°), ~1–2 cm positional drift. Measured largest frame-to-frame
step: 0.018°.

## 7. Credits
See [CREDITS.md](CREDITS.md). The CC BY assets require attribution when the film is published.
