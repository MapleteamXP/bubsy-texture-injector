"""
pack_manager.py — ROM pack selection, validation, and manifest management.

A "ROM pack" is a folder containing:
  • manifest.json — describes the pack, color mappings, texture assignments
  • textures/ — PNG/JPEG/BMP replacement textures

Manifest schema (ACTUAL format used by the injector):
{
  "pack_name": "Tiny Texture Pack 2 - Bubsy 3D Edition",
  "author": "Screaming Brain Studios (CC0)",
  "version": "1.0.0",
  "license": "CC0 / Public Domain",
  "description": "480 CC0 textures from Tiny Texture Pack 2, mapped for Bubsy 3D",
  "source_url": "https://screamingbrainstudios.itch.io/tiny-texture-pack-2",
  "color_map": {
    "grass": {
      "color_range": { "r": [0, 60], "g": [120, 255], "b": [0, 80] },
      "tolerance": 25,
      "textures": ["textures/grass_01.png", "textures/grass_02.png"],
      "randomize": true,
      "scale": 1.0,
      "uv_mode": "repeat",
      "priority": 1
    },
    ...
  },
  "level_overrides": { ... },
  "global_settings": {
    "texture_size": 128,
    "color_depth": 16,
    "uv_mode": "world_space"
  },
  "metadata": { ... }
}
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path


@dataclass
class PackInfo:
    """Information about a texture pack."""
    pack_name: str = "Unnamed Pack"
    name: str = ""  # Alias for pack_name (backward compat)
    version: str = "0.0.0"
    author: str = "Unknown"
    license: str = "Unknown"
    description: str = ""
    source_url: str = ""
    manifest_path: str = ""
    base_dir: str = ""
    manifest: dict = field(default_factory=dict)
    valid: bool = False
    errors: List[str] = field(default_factory=list)
    
    # Color mapping info
    color_map: dict = field(default_factory=dict)
    level_overrides: dict = field(default_factory=dict)
    global_settings: dict = field(default_factory=dict)
    
    # Texture count
    texture_count: int = 0


def load_pack(pack_dir: str) -> PackInfo:
    """Load and validate a texture pack directory."""
    manifest_path = os.path.join(pack_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        # Try auto-generating from textures folder
        manifest = auto_generate_manifest(pack_dir)
        if manifest:
            # Re-check now that manifest exists
            manifest_path = os.path.join(pack_dir, "manifest.json")
        else:
            return PackInfo(
                base_dir=pack_dir,
                valid=False,
                errors=["manifest.json not found (and no textures/ folder to auto-generate from)"],
            )

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        return PackInfo(
            base_dir=pack_dir,
            manifest_path=manifest_path,
            valid=False,
            errors=[f"Invalid JSON in manifest.json: {e}"],
        )
    except Exception as e:
        return PackInfo(
            base_dir=pack_dir,
            manifest_path=manifest_path,
            valid=False,
            errors=[f"Error reading manifest.json: {e}"],
        )

    # Read fields from the actual manifest schema
    info = PackInfo(
        pack_name=manifest.get("pack_name", manifest.get("name", "Unnamed Pack")),
        name=manifest.get("pack_name", manifest.get("name", "Unnamed Pack")),
        version=manifest.get("version", "0.0.0"),
        author=manifest.get("author", "Unknown"),
        license=manifest.get("license", "Unknown"),
        description=manifest.get("description", ""),
        source_url=manifest.get("source_url", ""),
        manifest_path=manifest_path,
        base_dir=pack_dir,
        manifest=manifest,
        color_map=manifest.get("color_map", {}),
        level_overrides=manifest.get("level_overrides", {}),
        global_settings=manifest.get("global_settings", {}),
    )

    # Validation
    # 1. Must have a pack_name
    if not info.pack_name or info.pack_name == "Unnamed Pack":
        info.errors.append("Missing 'pack_name' in manifest")

    # 2. Must have textures defined somewhere
    has_textures = False
    for surface_name, surface_def in info.color_map.items():
        textures = surface_def.get("textures", [])
        if textures:
            has_textures = True
            # Verify texture files exist
            for tex_path in textures:
                abs_path = os.path.join(pack_dir, tex_path)
                if not os.path.exists(abs_path):
                    info.errors.append(f"Missing texture file: {tex_path} (for surface '{surface_name}')")
    
    if not has_textures:
        info.errors.append("No textures defined in color_map — pack has nothing to inject!")

    # 3. Check if textures/ folder exists (optional but good practice)
    textures_dir = os.path.join(pack_dir, "textures")
    if os.path.isdir(textures_dir):
        png_count = len([f for f in os.listdir(textures_dir) if f.lower().endswith(".png")])
        info.texture_count = png_count
    
    info.valid = len(info.errors) == 0
    return info


def list_available_packs(packs_root: str) -> List[PackInfo]:
    """Scan a directory containing pack subfolders and return validated pack infos."""
    packs = []
    if not os.path.isdir(packs_root):
        return packs
    
    for entry in sorted(os.listdir(packs_root)):
        pack_dir = os.path.join(packs_root, entry)
        if os.path.isdir(pack_dir):
            info = load_pack(pack_dir)
            packs.append(info)
    
    # Sort: valid packs first, then by name
    packs.sort(key=lambda p: (not p.valid, p.pack_name.lower()))
    return packs


def list_valid_packs(packs_root: str) -> List[PackInfo]:
    """Return only valid packs."""
    return [p for p in list_available_packs(packs_root) if p.valid]


def auto_generate_manifest(pack_dir: str, pack_name: str = None) -> dict:
    """Auto-generate a manifest.json by scanning textures/ folder.
    
    Looks at filenames to guess surface types:
      grass_*.png → grass
      rock_*.png  → rock
      dirt_*.png  → dirt
      lava_*.png  → lava
      sand_*.png  → sand
      snow_*.png  → snow
      water_*.png → water
      wood_*.png  → wood
      metal_*.png → metal
      etc.
    """
    textures_dir = os.path.join(pack_dir, "textures")
    if not os.path.isdir(textures_dir):
        return None
    
    # Collect all image files
    image_files = []
    for f in os.listdir(textures_dir):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
            image_files.append(f)
    
    if not image_files:
        return None
    
    # Categorize by filename keywords
    categories = {
        "grass": [], "rock": [], "stone": [], "dirt": [], "ground": [],
        "lava": [], "fire": [], "sand": [], "snow": [], "ice": [],
        "water": [], "wood": [], "metal": [], "brick": [], "checker": [],
        "sky": [], "cloud": [], "wall": [], "floor": [], "roof": [],
    }
    
    # Default fallback for anything that doesn't match
    uncategorized = []
    
    for img in sorted(image_files):
        lower = img.lower()
        matched = False
        for keyword, file_list in categories.items():
            if keyword in lower:
                file_list.append(f"textures/{img}")
                matched = True
                break
        if not matched:
            uncategorized.append(f"textures/{img}")
    
    # Build color_map from categories
    color_map = {}
    
    # Predefined color ranges for common surfaces
    color_ranges = {
        "grass":  {"color_range": {"r": [0, 60],   "g": [120, 255], "b": [0, 80]},   "tolerance": 25},
        "rock":   {"color_range": {"r": [80, 160], "g": [60, 120],  "b": [40, 80]},   "tolerance": 20},
        "stone":  {"color_range": {"r": [100, 180],"g": [100, 180], "b": [100, 180]},"tolerance": 20},
        "dirt":   {"color_range": {"r": [100, 180],"g": [60, 120],  "b": [20, 60]},   "tolerance": 20},
        "ground": {"color_range": {"r": [80, 160], "g": [60, 120],  "b": [20, 80]},   "tolerance": 20},
        "lava":   {"color_range": {"r": [180, 255],"g": [40, 120],  "b": [0, 40]},    "tolerance": 30},
        "fire":   {"color_range": {"r": [180, 255],"g": [40, 120],  "b": [0, 40]},    "tolerance": 30},
        "sand":   {"color_range": {"r": [180, 255],"g": [160, 220], "b": [100, 160]}, "tolerance": 20},
        "snow":   {"color_range": {"r": [200, 255],"g": [200, 255], "b": [200, 255]}, "tolerance": 15},
        "ice":    {"color_range": {"r": [150, 220],"g": [180, 240], "b": [200, 255]}, "tolerance": 15},
        "water":  {"color_range": {"r": [0, 60],   "g": [60, 140],  "b": [140, 255]}, "tolerance": 20},
        "wood":   {"color_range": {"r": [120, 180],"g": [80, 140],  "b": [20, 60]},   "tolerance": 20},
        "metal":  {"color_range": {"r": [140, 200],"g": [140, 200], "b": [140, 200]}, "tolerance": 15},
        "brick":  {"color_range": {"r": [160, 220],"g": [60, 100],  "b": [20, 60]},   "tolerance": 20},
        "checker":{"color_range": {"r": [0, 255],  "g": [0, 255],   "b": [0, 255]},   "tolerance": 50},
        "sky":    {"color_range": {"r": [0, 80],   "g": [80, 180],  "b": [140, 255]}, "tolerance": 25},
        "cloud":  {"color_range": {"r": [200, 255],"g": [200, 255], "b": [200, 255]}, "tolerance": 15},
        "wall":   {"color_range": {"r": [120, 200],"g": [100, 160], "b": [60, 120]},  "tolerance": 20},
        "floor":  {"color_range": {"r": [100, 180],"g": [80, 140],  "b": [40, 100]},  "tolerance": 20},
        "roof":   {"color_range": {"r": [100, 180],"g": [40, 80],   "b": [20, 60]},   "tolerance": 20},
    }
    
    for keyword, textures in categories.items():
        if textures:
            entry = {
                "textures": textures,
                "randomize": True,
                "scale": 1.0,
                "uv_mode": "repeat",
                "priority": 1,
            }
            if keyword in color_ranges:
                entry.update(color_ranges[keyword])
            color_map[keyword] = entry
    
    # Dump uncategorized into a generic "default" entry
    if uncategorized:
        color_map["default"] = {
            "color_range": {"r": [0, 255], "g": [0, 255], "b": [0, 255]},
            "tolerance": 100,
            "textures": uncategorized,
            "randomize": True,
            "scale": 1.0,
            "uv_mode": "repeat",
            "priority": 0,
        }
    
    # Build manifest
    if pack_name is None:
        pack_name = os.path.basename(os.path.normpath(pack_dir))
    
    manifest = {
        "pack_name": pack_name,
        "author": "Auto-Generated",
        "version": "1.0.0",
        "license": "Unknown",
        "description": "Auto-generated manifest from texture filenames.",
        "source_url": "",
        "color_map": color_map,
        "level_overrides": {},
        "global_settings": {
            "texture_size": 128,
            "color_depth": 16,
            "uv_mode": "world_space"
        },
        "metadata": {
            "total_textures": len(image_files),
            "categories": list(color_map.keys()),
            "auto_generated": True,
            "created_date": "2026-05-08"
        }
    }
    
    # Write manifest.json
    manifest_path = os.path.join(pack_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    
    return manifest


def create_sample_manifest(
    pack_dir: str,
    pack_name: str = "My Texture Pack",
    author: str = "Modder",
) -> str:
    """Generate a sample manifest.json in the given directory. Returns path."""
    manifest = {
        "pack_name": pack_name,
        "author": author,
        "version": "1.0.0",
        "license": "CC0 / Public Domain",
        "description": "Sample texture pack for Bubsy 3D.",
        "source_url": "",
        "color_map": {
            "grass": {
                "color_range": {"r": [0, 60], "g": [120, 255], "b": [0, 80]},
                "tolerance": 25,
                "textures": ["textures/grass_01.png"],
                "randomize": False,
                "scale": 1.0,
                "uv_mode": "repeat",
                "priority": 1
            },
            "rock": {
                "color_range": {"r": [80, 160], "g": [60, 120], "b": [40, 80]},
                "tolerance": 20,
                "textures": ["textures/rock_01.png"],
                "randomize": False,
                "scale": 1.0,
                "uv_mode": "repeat",
                "priority": 2
            }
        },
        "level_overrides": {},
        "global_settings": {
            "texture_size": 128,
            "color_depth": 16,
            "uv_mode": "world_space"
        },
        "metadata": {
            "total_textures": 2,
            "categories": ["grass", "rock"],
            "created_date": "2026-01-01",
            "requires_injector_version": ">=1.0.0"
        }
    }
    os.makedirs(pack_dir, exist_ok=True)
    os.makedirs(os.path.join(pack_dir, "textures"), exist_ok=True)
    path = os.path.join(pack_dir, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path
