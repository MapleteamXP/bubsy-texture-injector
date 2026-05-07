# 📦 Texture Pack Guide

## How to Add Your Own Texture Packs

Adding custom texture packs to the Bubsy 3D Texture Injector is **easy**! Here's everything you need to know.

---

## Where to Put Texture Packs

All texture packs go in the **`packs/`** folder:

```
bubsy_texture_injector/
  packs/
    tiny_texture_pack_2/          ← Built-in pack (comes with the tool)
    my_custom_pack/               ← Your new pack goes here
    screaming_brain_hd/           ← Another pack
    ...
```

**Each pack is just a folder inside `packs/`** — that's it!

---

## Folder Structure of a Pack

Every pack folder must contain at least:

```
packs/my_custom_pack/
  manifest.json              ← REQUIRED: tells the injector what this pack is
  textures/                  ← REQUIRED: where all .png textures live
    grass_01.png
    water_01.png
    lava_01.png
    ...
  color_manifest.json        ← OPTIONAL: custom color-to-surface mappings
```

### Required Files

#### 1. `manifest.json`

This is the **pack description file**. Copy this template and modify it:

```json
{
  "pack_name": "My Awesome Pack",
  "author": "Your Name",
  "version": "1.0.0",
  "license": "CC0 / Public Domain / MIT",
  "description": "A brief description of your pack",
  "source_url": "https://your-website.com",
  
  "color_map": {
    "grass": {
      "color_range": { "r": [0, 60], "g": [120, 255], "b": [0, 80] },
      "tolerance": 25,
      "textures": [
        "textures/grass_01.png",
        "textures/grass_02.png"
      ],
      "randomize": true,
      "scale": 1.0,
      "uv_mode": "repeat",
      "priority": 1
    },
    "water": {
      "color_range": { "r": [0, 40], "g": [40, 120], "b": [120, 255] },
      "tolerance": 20,
      "textures": [
        "textures/water_01.png",
        "textures/water_02.png"
      ],
      "randomize": true,
      "scale": 1.0,
      "uv_mode": "repeat",
      "priority": 1
    }
  },
  
  "global_settings": {
    "texture_size": 128,
    "color_depth": 16,
    "uv_mode": "world_space"
  }
}
```

**Important fields:**
- `pack_name` — Shows up in the injector's dropdown menu
- `color_map` — Links polygon colors to your textures
- `textures` — Paths relative to the pack folder (must start with `textures/`)

#### 2. `textures/` folder

Put all your **.png** files here. The injector will convert them to PS1 TIM format automatically.

**Supported formats:** `.png`, `.jpg`, `.bmp`
**Recommended size:** 128×128 or 256×256 pixels
**Naming:** Use underscores, keep it simple:
```
textures/
  grass_01.png
  grass_02.png
  water_01.png
  lava_01.png
  rock_01.png
  sand_01.png
  ...
```

---

## Surface Types (What Gets Mapped)

These are the **surface types** the injector recognizes. Add at least one texture for each you want to cover:

| Surface Type | Bubsy 3D Color | Description |
|-------------|----------------|-------------|
| `grass` | Green polygons | Grass/ground |
| `water` | Blue polygons | Water/lakes |
| `lava` | Red/Orange/Black-White checkered | Lava/hot surfaces |
| `rock` | Brown/Grey | Rock walls, cliffs |
| `sand` | Tan/Yellow | Sand/dirt |
| `snow` | White | Snow/ice |
| `metal` | Grey/Silver | Metal platforms, machinery |
| `wood` | Brown | Wooden platforms |
| `dirt` | Dark brown | Dirt paths |
| `stone_platform` | Medium grey | Floating stone platforms |
| `checkerboard` | Checkered pattern | Special lava areas |

---

## Step-by-Step: Creating a New Pack

### Method A: Copy and Modify (Easiest)

1. **Copy** the built-in pack:
   ```
   packs/
     tiny_texture_pack_2/
   ```
   →
   ```
   packs/
     my_pack/
   ```

2. **Replace** the PNG files in `my_pack/textures/` with your own

3. **Edit** `my_pack/manifest.json`:
   - Change `pack_name`
   - Update texture file names if you renamed them
   - Adjust `color_map` if needed

4. **Restart** the injector — your pack appears in the dropdown!

### Method B: From Scratch

1. **Create** the folder structure:
   ```
   mkdir packs/my_pack
   mkdir packs/my_pack/textures
   ```

2. **Copy** the `manifest.json` from the built-in pack as a starting template

3. **Add** your textures to `packs/my_pack/textures/`

4. **Edit** the manifest to point to your textures

5. **(Optional)** Create `color_manifest.json` for custom color mappings

---

## Texture File Requirements

### Size Recommendations

| Size | VRAM Cost | Quality | Best For |
|------|-----------|---------|----------|
| 64×64 | Low | Basic | Testing, low-end emulators |
| 128×128 | Medium | Good | **Recommended default** |
| 256×256 | High | Great | High-end emulators |
| 512×512 | Very High | Excellent | Modern PCs only |

### PS1 Authenticity

For **true PS1-style** textures:
- Use **16 colors or 256 colors max** (4bpp or 8bpp)
- Add **Bayer dithering** for that retro look
- Keep pixel patterns visible (don't blur/smooth)
- Use strong contrast between pixels

The built-in `generate_textures.py` creates PS1-authentic textures automatically!

---

## Advanced: Color Manifest

If the automatic color detection doesn't work well for a specific level, create `color_manifest.json`:

```json
{
  "level_overrides": {
    "level_1_name": {
      "grass": {
        "color_range": { "r": [0, 80], "g": [140, 255], "b": [0, 100] },
        "tolerance": 30
      }
    }
  }
}
```

---

## Sharing Your Pack

To share with others:
1. Zip your pack folder (`my_pack/`)
2. Share the ZIP file
3. Others extract it to their `packs/` folder

**Or** submit it as a GitHub pull request to the main repo!

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Pack doesn't show up | Check `manifest.json` is valid JSON (use a JSON validator) |
| Textures not found | Make sure texture paths in manifest start with `textures/` |
| Wrong colors applied | Adjust `color_range` and `tolerance` in manifest |
| "No textures for surface X" | Add at least one texture for that surface type |
| Textures look stretched | Change `uv_mode` from `repeat` to `clamp` or adjust `scale` |

---

## Example: Minimal Working Pack

```
packs/minimal/
  manifest.json
  textures/
    grass.png
    rock.png
```

**manifest.json:**
```json
{
  "pack_name": "Minimal Pack",
  "version": "1.0.0",
  "color_map": {
    "grass": {
      "color_range": { "r": [0, 60], "g": [120, 255], "b": [0, 80] },
      "tolerance": 25,
      "textures": ["textures/grass.png"],
      "uv_mode": "repeat"
    },
    "rock": {
      "color_range": { "r": [80, 160], "g": [60, 120], "b": [40, 80] },
      "tolerance": 20,
      "textures": ["textures/rock.png"],
      "uv_mode": "repeat"
    }
  }
}
```

That's it! Two textures, one manifest, instant pack! 🔥

---

**Need more help?** Check the built-in `tiny_texture_pack_2/` for a full working example.
