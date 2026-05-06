"""
pack_manager.py — ROM pack selection, validation, and manifest management.

A "ROM pack" is a folder containing:
  • manifest.json — describes the pack, target game builds, texture mappings
  • textures/ — PNG/JPEG/BMP replacement textures
  • preview/ (optional) — preview images

Manifest schema (v1):
{
  "name": "Tiny Texture Pack 2",
  "version": "1.0.0",
  "author": "Your Name",
  "target_game": "bubsy3d",
  "target_builds": ["bubsy3d_ntsc_u", "bubsy3d_pal"],
  "description": "High-res texture overhaul for Bubsy 3D",
  "textures": {
    "standalone_tim": {
      "DATA/TIM/LEVEL1.TIM;1": "textures/level1_overhaul.png",
      "DATA/TIM/BUBSY.TIM;1":   "textures/bubsy_skin.png"
    },
    "tmd_levels": {
      "level1": {
        "tmd_file": "DATA/TMD/LEVEL1.TMD;1",
        "polygon_groups": {
          "ground":   {"replacement": "textures/level1_ground.png",   "uv_map": "auto"},
          "walls":    {"replacement": "textures/level1_walls.png",    "uv_map": "auto"},
          "skybox":   {"replacement": "textures/level1_sky.png",      "uv_map": "auto"}
        }
      },
      "hub": {
        "tmd_file": "DATA/TMD/HUB.TMD;1",
        "polygon_groups": {
          "portal":   {"replacement": "textures/hub_portal.png"}
        }
      }
    }
  }
}
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path


@dataclass
class PackInfo:
    name: str
    version: str
    author: str
    target_game: str
    target_builds: List[str]
    description: str
    manifest_path: str
    base_dir: str
    manifest: dict = field(default_factory=dict)
    valid: bool = False
    errors: List[str] = field(default_factory=list)


def load_pack(pack_dir: str) -> PackInfo:
    """Load and validate a ROM pack directory."""
    manifest_path = os.path.join(pack_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return PackInfo(
            name="Unknown", version="", author="", target_game="",
            target_builds=[], description="", manifest_path=manifest_path,
            base_dir=pack_dir, valid=False, errors=["manifest.json not found"],
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    info = PackInfo(
        name=manifest.get("name", "Unnamed Pack"),
        version=manifest.get("version", "0.0.0"),
        author=manifest.get("author", "Unknown"),
        target_game=manifest.get("target_game", ""),
        target_builds=manifest.get("target_builds", []),
        description=manifest.get("description", ""),
        manifest_path=manifest_path,
        base_dir=pack_dir,
        manifest=manifest,
    )

    # Validation
    if not info.target_game:
        info.errors.append("Missing 'target_game' in manifest")
    if not info.target_builds:
        info.errors.append("No 'target_builds' specified")

    # Check texture files exist
    textures = manifest.get("textures", {})
    standalone = textures.get("standalone_tim", {})
    for iso_path, rel_path in standalone.items():
        abs_path = os.path.join(pack_dir, rel_path)
        if not os.path.exists(abs_path):
            info.errors.append(f"Missing standalone texture: {rel_path} (for {iso_path})")

    tmd_levels = textures.get("tmd_levels", {})
    for level_name, level_def in tmd_levels.items():
        groups = level_def.get("polygon_groups", {})
        for group_name, group_def in groups.items():
            rel = group_def.get("replacement")
            if rel:
                abs_path = os.path.join(pack_dir, rel)
                if not os.path.exists(abs_path):
                    info.errors.append(f"Missing TMD texture: {rel} (level={level_name}, group={group_name})")

    info.valid = len(info.errors) == 0
    return info


def list_available_packs(packs_root: str) -> List[PackInfo]:
    """Scan a directory containing pack subfolders and return validated pack infos."""
    packs = []
    if not os.path.isdir(packs_root):
        return packs
    for entry in os.listdir(packs_root):
        pack_dir = os.path.join(packs_root, entry)
        if os.path.isdir(pack_dir):
            info = load_pack(pack_dir)
            if info.valid:
                packs.append(info)
    return packs


def create_sample_manifest(
    pack_dir: str,
    pack_name: str = "Tiny Texture Pack 2",
    author: str = "Modder",
) -> str:
    """Generate a sample manifest.json in the given directory. Returns path."""
    manifest = {
        "manifest_version": "1.0",
        "name": pack_name,
        "version": "1.0.0",
        "author": author,
        "target_game": "bubsy3d",
        "target_builds": ["bubsy3d_ntsc_u", "bubsy3d_pal"],
        "description": "Sample texture pack demonstrating standalone TIM swaps and TMD group injection.",
        "textures": {
            "standalone_tim": {
                "DATA/TIM/LEVEL1.TIM;1": "textures/level1_overhaul.png",
                "DATA/TIM/BUBSY.TIM;1": "textures/bubsy_skin.png",
                "DATA/TIM/FONT.TIM;1": "textures/font_replacement.png"
            },
            "tmd_levels": {
                "level1": {
                    "tmd_file": "DATA/TMD/LEVEL1.TMD;1",
                    "polygon_groups": {
                        "ground": {
                            "replacement": "textures/level1_ground.png",
                            "uv_mode": "auto"
                        },
                        "walls": {
                            "replacement": "textures/level1_walls.png",
                            "uv_mode": "auto"
                        },
                        "skybox": {
                            "replacement": "textures/level1_sky.png",
                            "uv_mode": "auto"
                        }
                    }
                },
                "hub": {
                    "tmd_file": "DATA/TMD/HUB.TMD;1",
                    "polygon_groups": {
                        "portal": {
                            "replacement": "textures/hub_portal.png",
                            "uv_mode": "auto"
                        }
                    }
                }
            }
        }
    }
    os.makedirs(pack_dir, exist_ok=True)
    os.makedirs(os.path.join(pack_dir, "textures"), exist_ok=True)
    path = os.path.join(pack_dir, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path
