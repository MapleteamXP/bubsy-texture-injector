# 🐱 Bubsy 3D Texture Injector

**A Windows GUI tool for injecting high-quality textures into PS1 Bubsy 3D ROMs.**

Transform Bubsy 3D's infamous bare naked flat-shaded polygons into beautifully textured environments using smart color-based semantic mapping and CC0 texture packs.

---

## 🔥 What This Does

Bubsy 3D (1996) used flat-shaded colored polygons for its level geometry instead of textures. The colors were semantic:
- **Green** = grass
- **Red/Orange** = lava
- **Blue** = water
- **Brown/Gray** = rock/ground
- **Tan** = sand/dirt

**This tool reads those colors and maps them to real textures!**

1. **Scans your ROM** — Parses the ISO/BIN/CUE disc image
2. **Finds TMD geometry files** — Bubsy 3D uses Sony's TMD format
3. **Analyzes polygon colors** — Clusters polygons by their flat-shade color
4. **Maps to textures** — Grass-green polygons get grass textures, lava-red gets lava textures
5. **Converts PNG→TIM** — Textures become PS1-native TIM format
6. **Injects into ROM** — Patches the disc image with enhanced geometry
7. **Outputs playable ROM** — Load in emulator or burn to disc!

---

## 🚀 Quick Start

### Option A: Download Pre-built .exe (Coming Soon)
1. Download `Bubsy3D_TextureInjector.exe`
2. Double-click to run
3. Load your Bubsy 3D ROM
4. Select a texture pack
5. Click **INJECT TEXTURES!**

### Option B: Build from Source
```bash
# Install Python 3.10+
pip install -r requirements.txt

# Build .exe
build.bat

# Or run directly
python main.py
```

---

## 📦 Texture Packs

Packs live in the `packs/` folder. Each pack contains:

```
packs/my_pack/
  manifest.json       # Pack metadata + texture assignments
  textures/
    grass_01.png      # Source textures (any resolution)
    water_01.png
    lava_01.png
    rock_01.png
    sand_01.png
    ...
```

### Included Pack: Tiny Texture Pack 2

The default pack uses **Screaming Brain Studios' Tiny Texture Pack 2** (CC0/Public Domain):
- 480 textures at 512×512, 256×256, 128×128
- Grass, water, lava, rock, sand, snow, metal, wood, dirt
- Free for any use!
- Source: https://screamingbrainstudios.itch.io/tiny-texture-pack-2

### Creating Your Own Pack

1. Create a folder in `packs/`
2. Add textures to `textures/`
3. Create `manifest.json` following the schema in `docs/`
4. Optionally create `color_manifest.json` for smart color mapping

---

## 🎨 Color Mapping System

The smart injection engine uses **color semantic analysis**:

```json
{
  "color_map": {
    "grass": {
      "color_range": { "r": [0, 60], "g": [120, 255], "b": [0, 80] },
      "textures": ["grass_01.png", "grass_02.png"],
      "uv_mode": "repeat"
    },
    "lava": {
      "color_range": { "r": [180, 255], "g": [0, 80], "b": [0, 40] },
      "textures": ["lava_01.png"],
      "uv_mode": "repeat"
    }
  }
}
```

### How It Works

1. **Scan TMD** — Read all flat-shaded polygon primitive packets
2. **Extract color** — Get RGB color from each polygon
3. **Classify** — Match color against defined ranges (with tolerance)
4. **Assign texture** — Pick appropriate texture from pack
5. **Upgrade polygon** — Convert flat-shaded → texture-mapped with UVs
6. **Pack atlas** — Build TIM texture atlas for PS1 VRAM constraints

---

## 🛠️ Technical Details

### Supported Input Formats
- `.iso` — Raw ISO 9660 disc image
- `.bin` — Raw sector image (2352 bytes/sector)
- `.cue` — CUE sheet (resolves to associated BIN)

### Supported Texture Formats
- PNG, JPEG, BMP → Converted to PS1 TIM format
- TIM modes: 4bpp, 8bpp (with CLUT), 16bpp (direct color)
- Recommended: **16bpp** for best visual quality

### PS1 Constraints Handled
- Texture page alignment (64×256 word boundaries)
- VRAM positioning
- UV coordinate generation (8-bit 0-255 range)
- Polygon primitive type conversion (flat → textured)

### File Formats Understood
- **ISO 9660** — Full filesystem parser with 2048/2352 sector support
- **TMD** — Sony Transformed Model Data (objects, vertices, normals, primitives)
- **TIM** — Sony Texture Image Format (with CLUT support)

---

## 🎮 Usage Guide

### Step 1: Load ROM
- Click **Browse** and select your Bubsy 3D ROM
- Supported: `.iso`, `.bin`, `.cue`
- Tool auto-detects game version

### Step 2: Select Pack
- Choose from available texture packs
- Preview shows pack details and compatibility

### Step 3: Configure Options
- **Dry Run** — Preview changes without modifying ROM (recommended first time!)
- **Backup** — Creates `.bak` of original ROM
- **Texture Size** — 64, 128, or 256 (higher = better quality, more VRAM)
- **Color Depth** — 4bpp/8bpp/16bpp (16bpp recommended)

### Step 4: Preview Color Map
- Click **Preview Color Map** to see:
  - How many polygons detected
  - What surface types identified
  - Which textures will be applied

### Step 5: Inject!
- Click **🚀 INJECT TEXTURES**
- Progress bar shows status
- Log window displays detailed output
- Result: Patched ROM in `output/` folder

---

## 🧪 Dry Run Mode

**Always run dry run first!**

Dry run analyzes the ROM and reports:
- Files found on disc
- TMD/TIM files detected
- Polygon color clusters
- Planned texture assignments
- Expected changes

No files are modified. Review the log, then run for real.

---

## 🔄 Backup & Restore

The tool automatically creates `.bak` files:
```
your_rom.iso      → patched version
your_rom.iso.bak  → original (safe!)
```

To restore: Delete patched ROM, rename `.bak` to original.

---

## 📝 Project Structure

```
bubsy_texture_injector/
  main.py              # GUI application entry point
  gui.py               # tkinter UI (embedded in main.py)
  rom_parser.py        # ISO 9660 / BIN / CUE parser
  tmd_parser.py        # Sony TMD format parser + primitive decoder
  tim_handler.py       # TIM read/write + PNG→TIM conversion
  injector.py          # Texture injection orchestrator
  pack_manager.py        # Pack loading + validation
  color_mapper.py      # Smart color→texture semantic mapping
  config.py            # Build detection + game version configs
  
  packs/
    tiny_texture_pack_2/
      manifest.json     # Pack metadata
      textures/         # PNG source textures
  
  docs/
    COLOR_MAPPING_SPEC.md  # Full color mapping specification
  
  requirements.txt     # Python dependencies
  build.bat            # PyInstaller build script
```

---

## 🧰 For Developers

### Adding New Game Support

Edit `config.py`:
```python
KNOWN_BUILDS["my_game"] = BuildConfig(
    name="my_game",
    gamecode="SLUS-12345",
    exe_name="SLUS_123.45;1",
)
```

### Adding New Surface Types

Edit `color_mapper.py` — add to `DEFAULT_COLOR_MAP`:
```python
"ice": {
    "color_range": {"r": [180,255], "g": [220,255], "b": [240,255]},
    "textures": ["ice_01.png"],
}
```

### Texture Pack Manifest Schema

See `packs/tiny_texture_pack_2/manifest.json` for full example.

Key sections:
- `color_map` — Color-to-surface mapping
- `level_overrides` — Per-level color adjustments
- `global_settings` — Texture size, color depth, UV mode

---

## ⚠️ Important Notes

### Legal
- **This tool does NOT redistribute copyrighted game assets**
- You must provide your own legally obtained Bubsy 3D ROM
- All included textures are CC0/Public Domain from Screaming Brain Studios
- Tool only produces patch files — original game data required

### Technical Limitations
- PS1 VRAM is limited (~1MB for textures)
- Large textures may cause slowdown on real hardware
- Emulators may handle oversized textures better
- Some polygon types may not be convertible (rare edge cases)

### Compatibility
- Tested with: DuckStation, PCSX-Redux, ePSXe, Mednafen/Beetle
- Real hardware: Should work if VRAM constraints respected
- Version support: NTSC-U, PAL, NTSC-J (auto-detected)

---

## 🙏 Credits

### Textures
- **Screaming Brain Studios** — Tiny Texture Pack 2 (CC0)
  - https://screamingbrainstudios.itch.io/tiny-texture-pack-2
  - https://screamingbrainstudios.com

### Technical Research
- PS1 TMD/TIM format documentation from Sony SDK
- PSXDEV.net community reverse-engineering notes
- Bubsy 3D uses Sony libGS + TMD format (confirmed by TMD rippers)

### Tools
- Python + tkinter — GUI framework
- Pillow — Image processing
- PyInstaller — .exe packaging

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Could not detect ISO 9660" | Ensure ROM is a valid PS1 disc image |
| "TMD files not found" | Some rips rename files — check Analysis output |
| "Out of VRAM" in emulator | Use smaller texture size (64 or 128) |
| Textures look wrong | Adjust color tolerance in color manifest |
| Injection fails | Try Dry Run first to see what's detected |

---

## 🗺️ Roadmap

- [x] ISO/BIN/CUE parser
- [x] TMD format decoder
- [x] TIM read/write + PNG conversion
- [x] Color semantic mapping
- [x] tkinter GUI
- [x] Pack system
- [ ] Real-time preview renderer
- [ ] Automatic texture atlas optimization
- [ ] Level-specific override editor
- [ ] Animated texture support (water, lava)
- [ ] Community pack repository integration

---

## 📜 License

**Tool code**: MIT License — free to use, modify, distribute.

**Textures**: CC0 / Public Domain (Screaming Brain Studios).

**Game assets**: You must provide your own legally obtained Bubsy 3D ROM.

---

## 🔥 Made with love for retro gaming preservation!

Bubsy 3D deserves better textures. Let's give it some! 🐱🎮

**GitHub**: https://github.com/MapleteamXP/starlightinn  
*(This tool is part of the Starlight Inn game preservation project)*
