# Rain-Soaked Intersection: Master Prompt

Paste everything inside the fenced block into a new Opus 5.5 session on this repo.

````
# TASK
Create a photorealistic 8-second, 4K (3840×2160), 24 fps animation of a rain-soaked urban
intersection at night. It should be convincing enough to pass as live-action footage. Quality
and correctness beat scope: one flawless shot, no extras.

# ENVIRONMENT AND SPLIT WORKFLOW
- You are in a cloud container with Blender 4.5 LTS (headless), ffmpeg 6.1 (libx264/libx265),
  Python 3 with numpy/Pillow, ImageMagick (`convert`), Node 22, 4 CPU cores, 15 GB RAM and NO GPU.
  Re-verify this at the start rather than assuming.
- Asset APIs are reachable: Sketchfab (api.sketchfab.com/v3/, auth is injected by the proxy, so
  use no API key) and Poly Haven (api.polyhaven.com).
- The final render will run on the user's PC: AMD Radeon RX 7800 XT (16 GB VRAM), Ryzen 7 CPU,
  Blender 4.5 LTS, Cycles with the HIP backend + HIP-RT. You cannot run it. So:
  1. Build and test everything here on CPU using small stills (e.g. 960×540, 32–64 samples)
     and a few-frame clips.
  2. Make the project fully portable: relative paths, all assets and textures inside the repo
     (or fetched by a script that is documented and re-runnable), no absolute paths.
  3. Write `render.py` (run as `blender -b scene.blend -P render.py -- [options]`) that:
     detects HIP/HIP-RT and falls back to CPU, renders PNG (16-bit if sensible) frame
     sequences, SKIPS already-rendered frames so interrupted renders resume, supports
     `--frame N`, `--range A B`, and `--preview` (1080p, low samples), and prints per-frame
     time and an ETA.
  4. Write `encode.sh` for ffmpeg: H.264, CRF ≤ 16, yuv420p, 24 fps, plus a ProRes/H.265
     option.
  5. Commit to branch `claude/relaxed-noether-9tl87k` (push with `git push -u origin <branch>`).
     Don't open a PR unless asked.
- Budget: aim for ≤ 2 min/frame at 4K on the 7800 XT (≈ 6.5 h total). Because you cannot
  measure GPU speed, add a documented benchmark mode (`--frame N`) so the user can time one
  frame, and give them a settings ladder (samples, light bounces, denoise, resolution
  scale) to trade quality for speed. Keep VRAM under ~12 GB: instance repeated assets,
  cap texture sizes (mostly 2K, 4K only for hero surfaces), and use the adaptive sampling
  and the OpenImageDenoise denoiser.

# THE SHOT
Four-way urban intersection, about 11 pm, late autumn, steady light rain, ~8 °C.
Camera: 35 mm, f/2.0, starts at 1.7 m eye height on a street corner, slow 3 m dolly forward
along the kerb with subtle handheld sway (noise-driven, ≤ 1° amplitude, no perfectly smooth
motion). Slight low-contrast filmic look, cinematic but natural.
Leave composition decisions to your judgment, but: strong leading lines, a clear subject
(e.g. a taxi or bus stopped at the red light), foreground/mid/background depth, and sky
glow behind the buildings.

# 1. SCALE AND GEOMETRY
- Model in metres. Lane 3.0–3.5 m, kerb height 15 cm, traffic-light head ~5 m, car 4.2–5 m,
  storey 3–3.5 m, sidewalk 3 m+. Wrong scale is the fastest giveaway: check it with a
  reference human figure and car in a test render.
- Build only what the camera sees: hero block (full detail), mid-ground (simplified, textured),
  distant skyline (cards/low-poly with emissive window textures behind atmospheric haze). Use
  instancing and collections.
- Break up repetition: decals, grime, patched asphalt, tar seams, manhole covers, drains,
  worn lane markings, graffiti, posters, stickers, cracks. Vary window lighting, curtains,
  signage, and facade materials. No identical buildings side by side.

# 2. ASSETS
- Search Sketchfab for downloadable CC0 or CC-BY models: sedan, taxi, bus, traffic lights,
  street lamps, bus shelter, bins, bollards, fire hydrant, newspaper box, street signs,
  pedestrians. Use `downloadable=true`, check license, polycount, scale, PBR maps, and reject
  baked lighting or flat low-poly looks. Record every attribution in CREDITS.md.
- Poly Haven for the night HDRI (urban, overcast/low light), asphalt, concrete, brick and
  metal PBR textures. Fall back to procedural materials when no suitable asset exists.
- Inspect each asset on a neutral background first. Fix its normals, scale, pivot, and
  materials. Any asset that can't be made to look real gets replaced or hidden in darkness
  or depth of field.
- Materials must be physically plausible: correct IOR (glass 1.5, water 1.33), roughness
  variation, dirt, wear, edge scratches, dust. Nothing uniformly clean.

# 3. LIGHTING (every source justified, consistent)
- Light sources: sodium or LED street lamps (choose one colour temperature per street and stay
  consistent), traffic signals on a correct cycle, shop signs, lit windows with varied
  colour temperatures and random on/off, headlights (correct beam cutoff), brake lights,
  and orange-grey sky glow as ambient.
- Wet asphalt: low roughness (~0.1–0.3), puddles lower still, Fresnel-correct reflections,
  roughness variation from oil and tyre marks. Reflections must match what is actually
  above them: lamps, signs and cars should appear mirrored in the right place.
- Control bounce and noise: use light portals or a light-linked environment where useful,
  clamp indirect light to cut fireflies, and use area lights with realistic sizes.
- Atmosphere: light volumetric haze only where physically sensible; keep it cheap.
- Camera look: physical exposure, depth of field from the f-stop, hexagonal or round bokeh, subtle
  bloom/glare, vignette, chromatic aberration and film grain. Subtle, because if the
  viewer notices them, dial them back.

# 4. RAIN AND WATER
- Rain streaks are visible mostly where backlit by lights. Use a cheap, convincing
  approach (particle or procedural streak layer, composite pass, or both) that avoids
  millions of render-time raindrops.
- Splash rings and ripples on puddles (animated normal/displacement), drips off awnings and
  signs, water along gutters toward the drains, droplets and runoff on the car windscreen with
  wipers running, steam from a grate if it suits the scene.
- Wet surfaces everywhere: darker, glossier diffuse; umbrellas shiny; lamp posts and signs wet.

# 5. TRAFFIC AND PEOPLE (logic)
- Choose a country and drive on the correct side. Cars stay in lane, obey a
  green → amber → red cycle with correct cross-traffic pairing, decelerate and accelerate
  smoothly (ease-in/out, no teleporting), brake lights respond to braking, wheels
  rotate at the right speed for the car's velocity, suspension dips slightly under braking.
- Pedestrians: if you can't make them look real, keep them small, distant, and silhouetted
  or backlit under umbrellas. Walking speed 1.2–1.5 m/s, waiting at kerbs on red, no
  clipping. Never let one weak figure dominate the frame.
- All motion is time-consistent: signal cycle, traffic flow and rain run by the same clock.

# 6. VERIFICATION LOOP (mandatory)
Work in stages and look at actual rendered images at every stage; don't assess from code.
1. Layout and scale pass (grey-box, correct metres, camera path).
2. Asset pass (each hero asset in situ).
3. Lighting pass: stills at three points in the shot.
4. Wet surfaces and rain pass.
5. Traffic and motion pass: contact sheet every 8th frame, plus a 24-frame low-res clip.
6. Polish pass: grain, bloom, grade, camera shake.
After each stage, act as a hostile supervisor: write a defect list (scale, lighting
inconsistency, material that looks CG, tiling, clipping, flicker, fireflies, wrong reflections,
physically wrong motion), fix it, re-render, and repeat. Minimum 3 full iterations of the
lighting and materials. Also diff consecutive frames to check flicker and temporal stability.
Don't move on while a known flaw is unfixed. Remove or hide what you can't make convincing.

# 7. DELIVERABLES
- `scene.blend` (or a Python scene-builder that regenerates it), `render.py`, `encode.sh`,
  `README.md` (setup on Windows with AMD, how to run the benchmark frame, the quality/speed
  ladder, how to resume), `CREDITS.md`, a preview contact sheet, and a low-res preview mp4
  rendered here.
- An honest final report: what is convincing, what is still weak, estimated render time on
  a 7800 XT with how you derived it, and what you'd improve. Don't claim photorealism you
  haven't verified visually.
````

## Notes
- Real GPU speed is the one unknown: after delivery, run the benchmark frame on the 7800 XT and report the time back so settings can be tuned.
- Windows/AMD setup: latest Adrenalin driver, then Blender > Edit > Preferences > System > Cycles Render Devices > HIP, tick the 7800 XT (and HIP-RT).
