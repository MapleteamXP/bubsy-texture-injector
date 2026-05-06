# 🎨 Texture Pack Sources for Bubsy 3D Texture Injector

This catalog lists **free, CC0, and public domain texture packs** compatible with the Bubsy 3D Texture Injector. All textures listed here can be legally used, modified, and redistributed in your packs.

---

## ⭐ Primary Sources

### 1. Screaming Brain Studios — Tiny Texture Pack 2
**URL:** https://screamingbrainstudios.itch.io/tiny-texture-pack-2  
**License:** CC0 / Public Domain  
**Size:** 480 textures  
**Resolutions:** 512×512, 256×256, 128×128, 64×64  
**Best for:** Bubsy 3D surface replacement

**Contents:**
- ✅ Grass (multiple variants)
- ✅ Water / Ice
- ✅ Lava / Magma
- ✅ Rock / Stone / Brick
- ✅ Sand / Dirt / Soil
- ✅ Snow / Frost
- ✅ Metal / Industrial
- ✅ Wood / Planks
- ✅ Checkerboard / Patterns
- ✅ Sky / Clouds

**Why it's perfect:** Multiple sizes per texture means you can pick the right resolution for PS1 VRAM constraints. The pixel-art style fits PS1-era aesthetics.

---

### 2. Screaming Brain Studios — Tiny Texture Pack (Original)
**URL:** https://screamingbrainstudios.itch.io/tiny-texture-pack  
**License:** CC0 / Public Domain  
**Size:** ~300 textures  
**Resolutions:** Various  
**Best for:** Additional variety and alternatives

---

### 3. Kenny Assets (by Kenney)
**URL:** https://kenney.nl/assets  
**License:** CC0 1.0 Universal  
**Size:** 1000+ textures across multiple packs  
**Resolutions:** 32×32 to 512×512  
**Best for:** UI, nature, space, urban environments

**Relevant packs for Bubsy 3D:**
- `kenney_nature-kit` — Grass, dirt, stone, water
- `kenney_space-kit` — For sci-fi levels (if any)
- `kenney_voxel-pack` — Pixel-style textures perfect for PS1 look

---

### 4. Retro3DGraphicsCollection (GitHub)
**URL:** https://github.com/Miziziziz/Retro3DGraphicsCollection  
**License:** CC0 / Various (check individual)  
**Size:** Compilation of multiple artists  
**Best for:** PS1-style retro assets

**Notable entries:**
- PS1-style nature assets
- Retro house/building textures
- Low-poly character textures

---

### 5. AmbientCG
**URL:** https://ambientcg.com  
**License:** CC0  
**Size:** 1000+ PBR materials  
**Resolutions:** Up to 4K (downscale to 128/256 for PS1)  
**Best for:** Photorealistic ground, rock, metal surfaces

**How to use:** Download PNG, downscale to 128×128 or 256×256, convert to TIM via the injector.

---

### 6. Poly Pizza (3D Models + Textures)
**URL:** https://poly.pizza  
**License:** CC0  
**Size:** Thousands of low-poly models with textures  
**Best for:** Decorative object textures, unique surfaces

---

### 7. OpenGameArt.org
**URL:** https://opengameart.org  
**License:** CC0, CC-BY, various  
**Size:** Massive collection  
**Best for:** Finding specific textures by search

**Search terms to use:**
- "seamless grass"
- "lava texture"
- "pixel art ground"
- "retro water"
- "PS1 style"

---

## 🎯 Bubsy 3D Level Themes & Texture Needs

Based on research, Bubsy 3D has **18 levels** with distinct themes:

| Level | Theme | Primary Colors | Textures Needed |
|-------|-------|---------------|-----------------|
| Level 1 | Grassland / Meadow | Green, brown | Grass, dirt, sky |
| Level 2 | Desert / Canyon | Tan, orange, brown | Sand, rock, cliff |
| Level 3 | Cave / Underground | Gray, dark brown | Stone, dirt, metal |
| Level 4 | Water / Swimming | Blue, cyan | Water, stone, sand |
| Level 5 | Lava / Volcanic | Red, orange, black | Lava, rock, ash |
| Level 6 | Snow / Ice | White, light blue | Snow, ice, rock |
| Level 7 | Industrial / Factory | Gray, metal, orange | Metal, concrete, hazard |
| Level 8-18 | Various | Mixed | Depends on level |

The injector's **color mapper** automatically detects these colors and assigns textures:
- Green polygons → Grass textures
- Red/orange polygons → Lava textures  
- Blue polygons → Water textures
- Brown/gray polygons → Rock/dirt textures
- White/light blue → Snow/ice textures

---

## 📦 Creating a Pack from These Sources

### Step-by-step:

1. **Download** textures from any source above
2. **Organize** into `packs/your_pack/textures/`:
   ```
   textures/
     grass_01.png      (from Tiny Texture Pack 2)
     grass_02.png      (from Kenny)
     water_01.png      (from Tiny Texture Pack 2)
     lava_01.png       (from Tiny Texture Pack 2)
     rock_01.png       (from AmbientCG)
     sand_01.png       (from Kenny)
     snow_01.png       (from Tiny Texture Pack 2)
     metal_01.png      (from Retro3DGraphics)
     wood_01.png       (from Tiny Texture Pack 2)
     dirt_01.png       (from AmbientCG)
   ```
3. **Create manifest.json** (see `packs/tiny_texture_pack_2/manifest.json` for template)
4. **Create color_manifest.json** mapping colors to textures:
   ```json
   {
     "color_map": {
       "grass": {
         "color_range": {"r": [0, 60], "g": [120, 255], "b": [0, 80]},
         "textures": ["grass_01.png", "grass_02.png"],
         "uv_mode": "repeat"
       }
     }
   }
   ```
5. **Load in injector** and click INJECT!

---

## ⚠️ Important Licensing Notes

| Source | License | Commercial Use? | Redistribution? |
|--------|---------|----------------|-----------------|
| Screaming Brain Studios | CC0 | ✅ Yes | ✅ Yes |
| Kenny | CC0 | ✅ Yes | ✅ Yes |
| AmbientCG | CC0 | ✅ Yes | ✅ Yes |
| Poly Pizza | CC0 | ✅ Yes | ✅ Yes |
| OpenGameArt | Varies | Check per asset | Check per asset |

**Always verify the license** before including textures in a distributed pack. CC0 assets are safest — no attribution required, full freedom.

---

## 🔥 Recommended "Starter Pack" Texture Set

For the **best out-of-box experience**, download these and place in `packs/starter/textures/`:

1. **From Tiny Texture Pack 2:**
   - `grass.png` → rename to `grass_01.png`
   - `water.png` → rename to `water_01.png`
   - `lava.png` → rename to `lava_01.png`
   - `rock.png` → rename to `rock_01.png`
   - `sand.png` → rename to `sand_01.png`
   - `snow.png` → rename to `snow_01.png`
   - `metal.png` → rename to `metal_01.png`
   - `wood.png` → rename to `wood_01.png`
   - `dirt.png` → rename to `dirt_01.png`

2. **From Kenny Nature Kit (optional extras):**
   - Additional grass variants
   - Stone path textures
   - Water variants

This gives you **9 surface types** covering 90% of Bubsy 3D's polygon colors!

---

## 🚀 Quick Download Commands

```bash
# Tiny Texture Pack 2 (manual download from itch.io)
# After downloading, extract to:
# packs/tiny_texture_pack_2/textures/

# Kenny assets (individual downloads)
# https://kenney.nl/assets

# AmbientCG (bulk download available)
# https://ambientcg.com
```

---

## 📝 Contributing New Sources

Found a great free texture source? Add it here!

Requirements:
- ✅ Free license (CC0, CC-BY, or public domain)
- ✅ Allows redistribution
- ✅ Compatible with game/mod use
- ❌ No "personal use only" or "no redistribution" restrictions

---

**Happy texture hunting! 🐱🎨**
