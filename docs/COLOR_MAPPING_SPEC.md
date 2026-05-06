# Bubsy 3D Texture Injector — Color Semantic Mapping Specification

## Polygon Color → Surface Type Mapping

Bubsy 3D uses flat-shaded polygons where the RGB color encodes the surface material type.
The injector scans polygon colors and maps them to appropriate textures from the selected pack.

### Color Detection Strategy

Colors are matched using a **fuzzy RGB clustering** approach with tolerance ranges:
- PS1 uses 15-bit color (5 bits per channel = 0-31 range per channel)
- We normalize to 8-bit (0-255) for matching
- Tolerance: ±20 RGB values per channel
- Priority: Exact match → Closest cluster → User override

### Surface Type Color Map

| Surface Type | PS1 Color Range (RGB) | Hex Approx | Description |
|--------------|----------------------|------------|-------------|
| **Grass** | R:0-60, G:120-255, B:0-80 | #2D8B1E | Green polygons = grass/vegetation |
| **Water** | R:0-40, G:40-120, B:120-255 | #1E6B8B | Blue polygons = water pools/rivers |
| **Lava** | R:180-255, G:0-80, B:0-40 | #B8381E | Red/orange polygons = lava/hazard |
| **Rock/Ground** | R:80-160, G:60-120, B:40-80 | #8B7355 | Brown/gray polygons = rock, dirt, ground |
| **Sand/Dirt** | R:180-255, G:140-220, B:60-120 | #DEB887 | Tan/beige polygons = sand, desert ground |
| **Snow/Ice** | R:200-255, G:200-255, B:200-255 | #F0F0F0 | White/very light = snow, ice surfaces |
| **Metal/Tech** | R:120-180, G:120-180, B:120-180 | #A0A0A0 | Mid-gray = metal platforms, tech surfaces |
| **Wood** | R:120-180, G:80-120, B:20-60 | #A0522D | Brown with warmth = wooden platforms |
| **Sky/Void** | R:0-40, G:0-60, B:80-160 | #00308B | Dark blue = skybox, background |
| **Checkerboard** | Alternating pattern | N/A | Special: The infamous checkerboard floor pattern |

### Multi-Level Mapping

For levels with distinct themes, the color mapping can be **level-aware**:

```json
{
  "level_overrides": {
    "claws_for_alarm": {
      "grass": { "r": [0,50], "g": [150,255], "b": [0,60] },
      "water": { "r": [0,30], "g": [50,100], "b": [150,255] }
    },
    "woolie_bully": {
      "lava": { "r": [200,255], "g": [0,60], "b": [0,30] }
    }
  }
}
```

### Texture Assignment Strategy

1. **Scan Phase**: Parse TMD files, extract polygon colors
2. **Cluster Phase**: Group polygons by color ranges into surface types
3. **Map Phase**: Assign texture from pack based on surface type
4. **UV Generation**: Create UV coordinates for flat-shaded polygons being converted
5. **Atlas Phase**: Pack textures into PS1-compliant TIM layout (256x256 pages)

### PS1 Texture Constraints for Mapping

- Texture size: 64x64, 128x128, or 256x256 (powers of 2)
- Color depth: 16-bit direct color (recommended for quality)
- Atlas packing: Multiple textures can share a 256x256 texture page
- UV coordinates: 8-bit values (0-255) relative to texture page
- Clut (palette) required for 4-bit and 8-bit modes

## Texture Pack Manifest Format

Each texture pack is a folder containing:
```
pack_name/
  manifest.json      # Pack metadata + texture assignments
  textures/
    grass_01.png     # Source textures (any size, converted to TIM)
    grass_02.png
    water_01.png
    lava_01.png
    rock_01.png
    sand_01.png
    metal_01.png
    wood_01.png
    checker_01.png
```

### manifest.json Structure

```json
{
  "pack_name": "Tiny Texture Enhanced",
  "author": "Screaming Brain Studios",
  "version": "1.0",
  "license": "CC0",
  "description": "480 textures mapped to Bubsy 3D surface types",
  "color_map": {
    "grass": {
      "color_range": { "r": [0,60], "g": [120,255], "b": [0,80] },
      "textures": ["grass_01.png", "grass_02.png", "grass_03.png"],
      "randomize": true,
      "scale": 1.0
    },
    "water": {
      "color_range": { "r": [0,40], "g": [40,120], "b": [120,255] },
      "textures": ["water_01.png", "water_02.png"],
      "randomize": true,
      "scale": 1.0,
      "animated": false
    },
    "lava": {
      "color_range": { "r": [180,255], "g": [0,80], "b": [0,40] },
      "textures": ["lava_01.png", "lava_02.png"],
      "randomize": true,
      "scale": 1.0,
      "glow": true
    },
    "rock": {
      "color_range": { "r": [80,160], "g": [60,120], "b": [40,80] },
      "textures": ["rock_01.png", "rock_02.png", "rock_03.png"],
      "randomize": true,
      "scale": 1.0
    },
    "sand": {
      "color_range": { "r": [180,255], "g": [140,220], "b": [60,120] },
      "textures": ["sand_01.png", "sand_02.png"],
      "randomize": true,
      "scale": 1.0
    },
    "snow": {
      "color_range": { "r": [200,255], "g": [200,255], "b": [200,255] },
      "textures": ["snow_01.png"],
      "randomize": false,
      "scale": 1.0
    },
    "metal": {
      "color_range": { "r": [120,180], "g": [120,180], "b": [120,180] },
      "textures": ["metal_01.png", "metal_02.png"],
      "randomize": true,
      "scale": 1.0
    },
    "wood": {
      "color_range": { "r": [120,180], "g": [80,120], "b": [20,60] },
      "textures": ["wood_01.png"],
      "randomize": false,
      "scale": 1.0
    },
    "checkerboard": {
      "pattern": "checker",
      "textures": ["checker_01.png"],
      "randomize": false,
      "scale": 1.0
    }
  },
  "level_overrides": {},
  "global_settings": {
    "texture_size": 128,
    "color_depth": 16,
    "atlas_pack": true,
    "mipmaps": false
  }
}
```

## UV Generation for Flat-Shaded Polygons

When converting flat-shaded polygons to textured:

1. **Quad polygons (4 vertices)**: Map to full texture UVs (0,0), (255,0), (255,255), (0,255)
2. **Triangle polygons (3 vertices)**: Map to triangular UV space (0,0), (255,0), (127,255)
3. **Repeating patterns**: For large surfaces, UV repeat (wrap) by scaling UV values
4. **World-space UVs**: Optional — compute UVs based on world position for seamless tiling

## Injection Strategy

### Method A: TMD Primitive Modification (Preferred)
- Find flat-shaded polygon primitives (code 0x20-0x23)
- Change primitive type to texture-mapped (code 0x24-0x27)
- Add UV coordinates to vertex data
- Add texture page reference

### Method B: Color Replacement in Place
- Keep polygon flat-shaded but modify color to more pleasing palette
- Quick wins without changing primitive type

### Method C: Texture Atlas Injection
- Build TIM atlas from pack textures
- Inject atlas into ROM
- Modify polygons to reference atlas textures

## Known Bubsy 3D Level Color Themes

Based on level descriptions and screenshots:

| Level | Expected Dominant Colors | Texture Needs |
|-------|-------------------------|---------------|
| Claws For Alarm | Green (grass), Blue (water) | Grass, Water, Rock |
| Clawstrophobic | Green, Brown (dirt) | Grass, Dirt, Rock |
| Catatomic Catastrophe | Gray (metal), Red (lava) | Metal, Lava, Rock |
| Woolie Bully | Red (lava), Brown (ground) | Lava, Rock, Ground |
| Missing Lynx | Green (jungle), Blue (water) | Grass, Water, Wood |
| Dome Sweet Dome | Gray (metal), Green | Metal, Grass |
| Das Bobcat | Brown (desert), Yellow | Sand, Rock |
| Domicidal Maniac | Dark (cave), Gray | Rock, Metal |
| Crimson Hide | Red (lava), Dark | Lava, Rock |
| Dome Home | Gray, Blue | Metal, Water |
| Mortal Bobkat | Green, Brown | Grass, Dirt |
| Zzzotz Nice | Blue, Green | Water, Grass |
| Daze of Thunder | Yellow, Brown | Sand, Rock |
| Woolieville Horror | Dark, Purple | Rock, Metal |
| Runaway Woolie | Gray, Brown | Metal, Ground |
| Bright Light Big Woolies | Bright, Multi | All types |
| Escape from Wool.A. | Gray, Red | Metal, Lava |
| The Final Stretch | Multi, Gold | All types |

## Implementation Notes

1. **Color tolerance must be configurable** — different emulators/rips may have color shifts
2. **Multiple textures per surface type** — random selection prevents repetition
3. **Preview mode essential** — show before/after color mapping before injection
4. **Backup original** — always create .bak before patching
5. **Incremental packs** — allow mixing base pack + level-specific add-ons
