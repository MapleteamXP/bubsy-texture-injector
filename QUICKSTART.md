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

## 📦 Adding Texture Packs

### Step 1: Download Tiny Texture Pack 2 (FREE!)
- Visit: https://screamingbrainstudios.itch.io/tiny-texture-pack-2
- Click **"Download Now"** (Name your own price = $0 for free)
- Choose **128x128.zip** or **256x256.zip**

### Step 2: Extract Textures
```
packs/tiny_texture_pack_2/textures/
  grass_01.png
  grass_02.png
  water_01.png
  lava_01.png
  rock_01.png
  sand_01.png
  snow_01.png
  metal_01.png
  wood_01.png
  dirt_01.png
```

### Step 3: Run the Injector!
The color mapper will automatically detect polygon colors and apply textures:
- **Green polygons** → Grass textures
- **Red/Orange polygons** → Lava textures
- **Blue polygons** → Water textures
- **Brown/Gray polygons** → Rock/Dirt textures
- **White polygons** → Snow textures

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
| "No textures found" | Download Tiny Texture Pack 2 and extract to `packs/tiny_texture_pack_2/textures/` |
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
