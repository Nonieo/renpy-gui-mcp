# MEDIA.md

Reference for what makes media **Ren'Py-compatible** and **VN-shaped**,
written so an agent (or a human) can produce assets that drop in
without rework. Provider-agnostic — fal, OpenRouter, ElevenLabs, Krita,
Photoshop, FL Studio, anything that can export the right bytes.

If you are an agent procuring assets, read this once before generating.
If you are a human, treat it as a checklist before commissioning.

This document covers **what to make** and **what shape it must be**.
For the code that wires it into a Ren'Py project, see
[AGENTS.md](AGENTS.md). For provider-specific generation pipelines, see
the `renpy-ai-assets` skill at `~/renpy-builder/renpy-ai-assets/`.

---

## The four invariants

Get any of these wrong and the asset has to be regenerated. They apply
to every visual or audio file dropped into a Ren'Py project.

1. **Format.**
   - Backgrounds / CGs: PNG (lossless) or JPG (smaller, slight quality
     loss but invisible at 1080p).
   - Sprites: **PNG with full alpha channel.** No background — the
     character must sit on transparency. JPG sprites are a bug.
   - GUI / UI assets: PNG with alpha (icons, buttons, panel chrome).
   - Music / BGM: **OGG Vorbis** strongly preferred. MP3 acceptable but
     has licensing quirks and slightly worse loop behavior. WAV only
     for very short SFX.
   - Voice: OGG Vorbis or MP3. One file per dialogue line (Ren'Py uses
     `voice "filename.ogg"` before a say-statement).
   - SFX: OGG Vorbis preferred for normal-length, WAV acceptable for
     <2 seconds.

2. **Dimensions.**
   - Backgrounds: match `config.screen_width × config.screen_height`
     exactly. The Ren'Py SDK template defaults to **1920 × 1080**.
     Anything smaller will be upscaled (blurry); anything larger will
     be wasted bytes.
   - Sprites: height equal to screen height (1080), width whatever the
     character needs centered on a transparent canvas. Don't pad; the
     PNG's alpha channel is the bounds.
   - CGs: same as backgrounds (1920 × 1080).
   - UI / icons: design at 2× target resolution and let Ren'Py
     downscale. Icons that need crispness at 32×32 should be drawn at
     64×64 minimum.

3. **Filename + auto-detection.**
   - Files in `game/images/` are auto-named: filename underscores
     become spaces. So `eileen_happy.png` becomes image
     `eileen happy`, shown via `show eileen happy`.
   - The first space-separated token is the **tag**; the rest are
     **attributes**. `mara worried angry.png` → tag `mara`, attributes
     `worried angry`. `show mara worried angry` works; so does
     `show mara` (uses the first matching set).
   - **Use spaces in attribute names, not hyphens** in the eventual
     image name. In the filename, an underscore becomes a space, so
     `eileen_happy.png` is fine. Avoid hyphens (`eileen-happy.png`
     becomes image `eileen-happy` — one token, useless).
   - **Avoid colons, semicolons, and quotes** anywhere in filenames.
     Ren'Py's distribute step rejects them.
   - Audio files have no naming magic. Pick something stable; reference
     by relative path: `play music "audio/harbor_theme.ogg"`.

4. **Directory.**
   - `game/images/` — backgrounds, sprites, CGs, image-tag assets.
   - `game/audio/` — music, voice, SFX. Optional sub-dirs (`audio/bgm/`,
     `audio/sfx/`, `audio/voice/`) are fine; reference them as
     `play music "audio/bgm/cafe.ogg"`.
   - `game/gui/` — UI chrome (button frames, panels, decorative icons).
     Already populated by the Ren'Py scaffold; replace files in place
     to retheme.

---

## Image specs

### Backgrounds

- 1920 × 1080, JPG (~50–200 KB) or PNG (~500 KB–2 MB) — JPG fine when
  the scene has no hard color edges.
- Treat as the establishing shot — characters layer on top.
- **No people in the background.** A figure painted into a background
  fights the sprites that load over it. Empty stages, empty interiors,
  empty streets.
- Strong horizon line and clear depth cues read better on small screens.
- Time-of-day / weather variants for one location: `bg_pier_dawn.jpg`,
  `bg_pier_dusk.jpg`, `bg_pier_storm.jpg`. Author them as the same
  base image with the lighting baked, not as separate compositions.

### Sprites

- 1080 px tall, transparent PNG.
- Character centered horizontally on a transparent canvas as wide as
  needed. Common widths: 600–900 px for a single figure.
- Body crop: half-figure (waist up) reads best for VN dialogue scenes.
  Full body works if the character has motion (running, fighting),
  but most VNs use waist-up.
- **Soft edges around hair / clothes.** Hard cutouts read as collage.
  Background-removal tools (e.g. fal-ai/bria/background/remove) handle
  this automatically.
- Keep the head in the upper third — Ren'Py centers sprites by anchor
  point, and head-in-upper-third matches typical VN composition.

#### Sprite hierarchy: tag, expression, outfit

For a single character, ship 3–6 sprite variants. Name them so Ren'Py
can navigate the variants automatically.

```
mara neutral.png       # default expression
mara happy.png
mara concerned.png
mara afraid.png
```

Multi-attribute (rarer; needed when you want the same expression with
different outfits):

```
mara neutral school.png
mara neutral casual.png
mara happy school.png
```

Author calls `show mara happy school`; if either attribute set has only
one option, the call shortens to `show mara happy`.

#### Sprite count per character

| Character role | Recommended sprites |
|---|---|
| Protagonist (often unseen, voice-only) | 0–1 |
| Romanceable / main cast | 4–6 expressions × 1 outfit |
| Secondary speaking role | 2–3 expressions |
| Walk-on / one-scene | 1 expression OR voice-only |
| Antagonist / mystery character | 2–3 + a variant for "reveal" |

**Five expressions cover most VN beats:** `neutral`, `happy`, `concerned`
or `worried`, `surprised`, `angry` or `firm`. Add `tearful` if the
character has a crying scene; `embarrassed` for romance routes; `thinking`
for puzzles or interrogations.

### CGs (cinematic moments)

- Same format and dimensions as backgrounds (1920 × 1080 PNG).
- Paint with the same characters that exist as sprites — consistency
  matters more than ambition. A CG of a character holding a sword
  should match the sprite's hair, eye color, outfit color exactly.
- Reserve for emotional beats (kisses, fights, reveals). One per major
  story moment is plenty; over-CG'ing dilutes their weight.

### UI / GUI

- Lives in `game/gui/`. Ren'Py's scaffold pre-populates it.
- Buttons / chrome typically 4× the visible size, downscaled by Ren'Py
  for crispness. Source-paint at 2× minimum.
- Stick to the project's accent palette — UI is the connective tissue
  between scenes. A jarring UI breaks immersion faster than a weak
  background.

---

## Audio specs

### Music (BGM)

- OGG Vorbis, 128–192 kbps. Mono if you have to choose; stereo
  preferred.
- **30–180 seconds per track**, designed to loop seamlessly. Ren'Py
  loops by default for `play music`. Make the last sample fade into
  the first.
- Quiet enough to sit *under* dialogue. If you mixed it for a music
  player, drop the mastered output by 6 dB before exporting for VN
  use.
- One leitmotif per major character (optional but powerful). One
  ambient palette per route.
- Silence is content. Don't fill every scene; let the moments after
  reveals breathe.

### Voice / TTS

- One file per dialogue line, OGG Vorbis or MP3.
- Normalize to roughly −16 LUFS (broadcast-radio loudness). Levels
  between voice and music must be balanced.
- Trim leading and trailing silence to ≤ 100 ms. Ren'Py won't trim
  for you, and the gap between line-ends and the next click is the
  player's experience.
- Filename pattern: `<character>_<line_id>.ogg`. The MCP tool to wire
  voice to a say-statement is upcoming; until then, `voice "..."`
  before each say-line is the manual path.

### Sound effects

- 0.3–3 seconds, OGG or WAV.
- No leading silence. Trim at the zero-crossing.
- Normalize peaks to −1 dBFS so they don't overwhelm dialogue.
- Categorize: `sfx_door_open.ogg`, `sfx_thud.ogg`, `sfx_chime.ogg`.
  Predictable filenames help when you need to scrub a scene later.

### Ambience

- Long-form (1–5 minute) low-volume background recordings: rain,
  ocean, café murmur, forest, traffic.
- Loop seamlessly like BGM. Lower the mix bus by another 3–6 dB
  beneath whatever music is playing.
- Use sparingly — three layers of ambience + music + dialogue is a mud
  pile.

---

## Style direction

### Pick one visual style and commit

Mixing styles breaks immersion faster than any individual style being
weak. The four common VN styles:

1. **Anime / cel-shaded.** High-contrast linework, flat-shaded color
   blocks, dramatic backgrounds. Most VN-coded; broad appeal. Think
   classic Type-Moon, Key, Spike Chunsoft.
2. **Painted / illustrative.** Soft edges, atmospheric backgrounds,
   character art with painterly shading. Slower to produce, more
   mature feel.
3. **Pixel art.** Limited palette, deliberate constraints. Pairs well
   with retro themes; very read-friendly on small screens.
4. **Photorealistic / 3DCG-rendered.** Pre-rendered Daz/Blender
   characters. Common for adult/horror VNs. Hard to make consistent
   without a pipeline.

A reference packet (3–5 pinned images) shared with whoever is producing
art keeps style drift bounded. Generate or commission three test images
before greenlighting the rest.

### Color palette per route

Each route or major story arc deserves its own color palette. Examples:

- **Mystery route:** desaturated blues and grays, single warm accent
  (a candle, a phone screen).
- **Romance route:** warm pastels, golden-hour skin tones, soft
  contrast.
- **Horror route:** unsaturated greens and ambers, hard shadows, rare
  pure black for menace.

Set the palette once. Apply it to backgrounds AND sprite outfits AND
UI accents AND music key. When all four agree, the route reads as one
piece.

### Lighting consistency

- Time-of-day discipline: a scene set at dusk has dusk lighting on
  every sprite shown in it. If you can't repaint sprites for each
  lighting condition, pick lighting that flatters the existing sprite
  art and stay close to it.
- Weather discipline: rain in the background means rain in the audio
  (`play sound "audio/rain_loop.ogg" loop`) and ideally damp clothes
  on sprites entering from outside.

---

## Naming conventions (with examples)

```
game/
├── images/
│   ├── bg_park_dawn.jpg          # → image `bg park dawn`
│   ├── bg_park_dusk.jpg          # → image `bg park dusk`
│   ├── eileen neutral.png        # space in filename = space in image name
│   ├── eileen happy.png
│   ├── eileen concerned.png
│   ├── mara_neutral.png          # underscore → space, same effect as above
│   ├── mara_neutral school.png   # multi-attribute (`mara neutral school`)
│   ├── cg_lighthouse_climb.png   # cinematic moment → image `cg lighthouse climb`
│   └── mc_silhouette.png         # MC sprite (silhouette only)
├── audio/
│   ├── bgm/
│   │   ├── harbor_theme.ogg
│   │   ├── cafe_warmth.ogg
│   │   └── lighthouse_storm.ogg
│   ├── sfx/
│   │   ├── door_open.ogg
│   │   ├── thud.ogg
│   │   └── seagull_distant.ogg
│   └── voice/
│       ├── eileen_001.ogg
│       └── eileen_002.ogg
└── gui/
    └── (Ren'Py scaffold contents)
```

---

## Creation depth checklist

Three production tiers. Pick the one that matches your scope; over-
producing one tier early is the most common way short VN projects
stall.

### Minimum viable VN (1–2 hour playtime)

- **Backgrounds:** 4–6 distinct locations. Day/night variants of one
  bring the count to 6–8. Total: 6–10 images.
- **Sprites:** 1 voiced/silhouetted protagonist + 2–3 NPCs × 4
  expressions each = 9–13 sprites.
- **CGs:** 2–3 cinematic moments tops. Save them for the climax and
  the romance high.
- **Music:** 3 BGM tracks (calm, tense, climactic) + 1 ambient loop.
- **SFX:** 5–10 small sounds (door, footsteps, chime, paper rustle,
  thud, distant noise).
- **UI:** stock Ren'Py GUI with palette tweaks.

### Polished short VN (3–5 hour playtime)

- **Backgrounds:** 10–15 locations. 2–3 day/night variants.
- **Sprites:** main cast of 4 × 5–6 expressions + 1–2 outfit variants
  per. Secondary cast of 2–3 × 2–3 expressions.
- **CGs:** 6–10 (per-route emotional beats + ending CGs).
- **Music:** 6–10 BGM tracks, one leitmotif per main-cast character.
- **SFX:** 15–25 sounds.
- **Voice:** optional but lifts perceived quality. Voice the main cast,
  leave protagonist silent.
- **UI:** custom palette, logo, title-screen art.

### Full-length VN (10+ hour playtime)

- **Backgrounds:** 25+ locations × variants. Dedicated background artist.
- **Sprites:** main cast of 5–7 × 8–10 expressions × 2–3 outfits.
  Secondary cast of 5+ × 4–5 expressions.
- **CGs:** 30–50.
- **Music:** 15–25 BGM tracks. Distinct routes get distinct musical
  palettes.
- **SFX:** 50+ sounds.
- **Voice:** strongly expected for the genre. Hire VAs.
- **UI:** fully custom GUI, animated transitions, branded title screen.

---

## Common mistakes to avoid

The four invariants above catch most asset-shape errors. A few that
aren't elsewhere:

- **Distributing without a slug-safe `build.name`.** Ren'Py rejects
  `build.directory_name` containing spaces, colons, or semicolons.
  The renpy-mcp scaffold slugifies automatically; if you author
  `options.rpy` by hand, use lowercase-underscore.
- **Generating one sprite per scene.** You'll end up redrawing the
  same character every chapter. Decide on the cast first; ship N
  expressions per character; reuse.

---

## What this document deliberately does NOT cover

- Specific generation providers (fal, OpenRouter, Stability, etc.) —
  see `~/renpy-builder/renpy-ai-assets/SKILL.md`.
- Specific paid commission pricing.
- Voice acting direction beyond level normalization. That's its own
  craft.
- Localization-specific image considerations (text-in-image, cultural
  differences). Localization is a separate project phase; the four
  invariants above hold across languages.

---

## Quick lookup table

| Asset | Format | Size | Naming | Where |
|---|---|---|---|---|
| Background | JPG/PNG | 1920×1080 | `bg_<location>[_<variant>].jpg` | `game/images/` |
| Sprite | PNG + alpha | 1080 tall | `<tag>_<expression>[_<outfit>].png` | `game/images/` |
| CG | PNG | 1920×1080 | `cg_<scene>.png` | `game/images/` |
| BGM | OGG | 30–180s | `<scene_or_mood>.ogg` | `game/audio/bgm/` |
| Voice | OGG/MP3 | per-line | `<character>_<lineId>.ogg` | `game/audio/voice/` |
| SFX | OGG/WAV | 0.3–3s | `sfx_<noun>.ogg` | `game/audio/sfx/` |
| Ambience | OGG | 1–5 min loop | `amb_<scene>.ogg` | `game/audio/` |
| UI chrome | PNG + alpha | 2–4× target | (Ren'Py defaults) | `game/gui/` |
