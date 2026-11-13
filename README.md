# Rain-soaked intersection at night: 8 s, 4K, 24 fps (Blender 4.5 LTS, Cycles)

A US four-way intersection at about 11 pm on a late-autumn night in steady light rain. The
camera dollies 3 m along the kerb towards a taxi waiting at a red light, while the cross street's
signal runs out its amber.

> **Status:** work in progress. See `docs/stages/` for the review renders of each stage and
> `REPORT.md` (written at the end) for the honest assessment.

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

| `--quality` | max samples | noise threshold | bounces (max/diff/gloss/trans) | use |
|---|---|---|---|---|
| `final` (default) | 512 | 0.010 | 8/3/4/8 | delivery |
| `balanced` | 320 | 0.015 | 8/3/4/8 | ~35 % faster, rarely distinguishable after denoising |
| `fast` | 192 | 0.025 | 6/2/3/6 | ~60 % faster, a little blotchy in dark corners |
| `draft` | 64 | 0.050 | 4/2/2/4 | layout and animation checks |

More levers, from the most effective:

1. `--scale 75` renders at 2880×1620 (0.56× the pixels). Upscale in the edit if needed.
2. `--quality balanced`.
3. `--samples N` to override the sample cap for any quality level.

Adaptive sampling stops early in clean areas, and OpenImageDenoise (High quality, on the GPU)
runs on every frame using albedo and normal passes. Indirect light is clamped (3.0) and glossy
filtering is on. Small emitters (lamp lenses, signals, brake lamps) are visible to the camera
only, with matching small lights doing the lighting and the reflections. This cut the
noise in the wet-road reflections 14× (see `docs/stages/05_materials_rain/REVIEW.md`).

Target: ≤ 2 min/frame at 4K on the 7800 XT (≈ 6.5 h for 192 frames). The estimate for this
scene is in `REPORT.md`, together with how it was derived.

### VRAM
Repeated assets are instanced, textures are capped at 2K (the 4K asphalt is the only
exception), and `use_persistent_data` keeps the BVH between frames. The expected VRAM use is
well below 12 GB. If you hit out-of-memory errors, use `--scale 75`.

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

## 6. Credits
See [CREDITS.md](CREDITS.md). The CC BY assets require attribution when the film is published.
