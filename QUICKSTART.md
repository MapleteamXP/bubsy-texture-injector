# 🚀 Quick Start Guide

## Get Bubsy 3D Texture Injector Running in 5 Minutes!

### Option A: Download Pre-built Release (Easiest)

1. **Download** the latest release from GitHub:
   ```
   https://github.com/MapleteamXP/bubsy-texture-injector/releases
   ```

2. **Extract** the ZIP file

3. **Run** `Bubsy3D_TextureInjector.exe`

4. **Load your ROM**, select a texture pack, click **INJECT!**

---

### Option B: Build from Source (Developer)

1. **Clone the repo:**
   ```bash
   git clone https://github.com/MapleteamXP/bubsy-texture-injector.git
   cd bubsy-texture-injector
   ```

2. **Run the setup script:**
   ```bash
   setup.bat
   ```
   This will:
   - Check Python installation
   - Install dependencies
   - Download texture packs (or guide you)
   - Build the .exe

3. **Or manually:**
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

---

## 📦 Texture Packs (Built-In!)

**Good news:** The injector includes **28 PS1-style textures** out of the box!

Everything works immediately — no downloads needed. The built-in pack covers:
- 🌿 Grass, 💧 Water, 🔥 Lava, 🪨 Rock, 🏖️ Sand, ❄️ Snow, 🔩 Metal, 🪵 Wood, 🟫 Dirt

### Want More/Higher Quality Textures?

Download **Tiny Texture Pack 2** from itch.io (FREE, CC0):
- Visit: https://screamingbrainstudios.itch.io/tiny-texture-pack-2
- Click **"Download Now"** (Name your own price = $0 for free)
- Choose **128x128.zip** or **256x256.zip**
- Extract and copy textures to `packs/tiny_texture_pack_2/textures/`

### How It Works
The color mapper automatically detects polygon colors and applies textures:
- **Green polygons** → Grass textures
- **Red/Orange polygons** → Lava textures  
- **Blue polygons** → Water textures
- **Brown/Gray polygons** → Rock/Dirt textures
- **White polygons** → Snow textures
- **Grey checkered** → Stone platforms

---

## 🎮 Using the Injector

### Main Window Layout:
```
┌─────────────────────────────────────────┐
│  🐱 Bubsy 3D Texture Injector           │
├─────────────────────────────────────────┤
│  Step 1: Load ROM                       │
│  [Browse...] [Analyze]                 │
├─────────────────────────────────────────┤
│  Step 2: Select Texture Pack            │
│  [Tiny Texture Pack 2]                  │
├─────────────────────────────────────────┤
│  Step 3: Color Mapping Preview          │
│  [Preview Color Map] [Configure]        │
├─────────────────────────────────────────┤
│  Manual Override (Optional)             │
│  [Scan TMD Files] [Assign Texture]      │
├─────────────────────────────────────────┤
│  Options: ☑ Dry Run  ☑ Backup .bak      │
│  Texture Size: [128x128]               │
│  Color Depth: [16bpp]                  │
├─────────────────────────────────────────┤
│  [🚀 INJECT TEXTURES]                   │
├─────────────────────────────────────────┤
│  Progress: [████████░░░░░░░░░] 67%      │
│  Log: Injected grass_01 into LEVEL1.TMD │
└─────────────────────────────────────────┘
```

### Recommended First-Time Workflow:
1. ✅ **Check "Dry Run"** (preview without modifying)
2. ✅ **Check "Backup"** (creates .bak of original ROM)
3. Click **"Preview Color Map"** to see what will be changed
4. Click **"🚀 INJECT TEXTURES"**
5. Review the log output
6. If everything looks good, **uncheck Dry Run** and run again for real!

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| "Python not found" | Install Python 3.10+ from python.org, check "Add to PATH" |
| "No textures found" | Built-in textures should work immediately. If you deleted them, re-download the release or regenerate with `python generate_textures.py` |
| "TMD files not detected" | Make sure your ROM is a valid PS1 disc image (.iso, .bin, .cue) |
| "Injection failed" | Try Dry Run first. Check log for specific errors. |
| "Textures look wrong" | Use Manual Override to assign specific textures |
| "Out of VRAM" in emulator | Use smaller texture size (64x64 or 128x128) |

---

## 📝 Creating Custom Texture Packs

1. Create a folder: `packs/my_custom_pack/`
2. Add textures to `packs/my_custom_pack/textures/`
3. Create `manifest.json` (copy from `packs/tiny_texture_pack_2/`)
4. Optional: Create `color_manifest.json` for custom color mapping
5. Reload the injector — your pack appears in the list!

---

## 🔗 Useful Links

| Resource | URL |
|----------|-----|
| **This Tool** | https://github.com/MapleteamXP/bubsy-texture-injector |
| **Tiny Texture Pack 2** | https://screamingbrainstudios.itch.io/tiny-texture-pack-2 |
| **Tiny Texture Pack 1** | https://screamingbrainstudios.itch.io/tiny-texture-pack |
| **Tiny Texture Pack 3** | https://screamingbrainstudios.itch.io/tiny-texture-pack-3 |
| **Bubsy Wiki** | https://bubsy.fandom.com/wiki/Bubsy_3D |
| **PS1 Emulators** | DuckStation, PCSX-Redux, ePSXe |

---

**Ready to make Bubsy 3D beautiful? Let's go! 🐱🔥**
