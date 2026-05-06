"""
config.py — Build configuration and version detection for Bubsy 3D.

Detects known game builds/versions from disc contents and configures
texture injection parameters accordingly.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional, Dict
from rom_parser import ISOParser


@dataclass
class BuildConfig:
    """Configuration for a specific Bubsy 3D build."""
    name: str                           # e.g. "bubsy3d_ntsc_u"
    gamecode: str = ""                  # SLUS/SLES/SLPS code
    version_string: str = ""
    preferred_tim_mode: int = 2        # 0=4bpp, 1=8bpp, 2=16bpp
    max_texture_size: int = 128
    tmd_subdir: str = "DATA/TMD"
    tim_subdir: str = "DATA/TIM"
    exe_name: str = "SLUS_001.06;1"   # Typical US EXE path on disc


# ── Known builds ──
KNOWN_BUILDS: Dict[str, BuildConfig] = {
    "bubsy3d_ntsc_u": BuildConfig(
        name="bubsy3d_ntsc_u",
        gamecode="SLUS-00106",
        preferred_tim_mode=2,  # 16bpp for best quality
        max_texture_size=128,
        exe_name="SLUS_001.06;1",
    ),
    "bubsy3d_pal": BuildConfig(
        name="bubsy3d_pal",
        gamecode="SLES-00000",  # Replace with actual if known
        preferred_tim_mode=2,
        max_texture_size=128,
        exe_name="SLES_XXX.XX;1",
    ),
    "bubsy3d_ntsc_j": BuildConfig(
        name="bubsy3d_ntsc_j",
        gamecode="SLPS-00000",  # Replace with actual if known
        preferred_tim_mode=2,
        max_texture_size=128,
        exe_name="SLPS_XXX.XX;1",
    ),
}


def get_build_by_name(name: str) -> Optional[BuildConfig]:
    """Retrieve a known build config by name."""
    return KNOWN_BUILDS.get(name)


def detect_build_from_iso(parser: ISOParser) -> str:
    """
    Analyze disc contents to identify which Bubsy 3D build this is.
    Returns the build name key, or 'unknown'.
    """
    files = list(parser.files.keys())
    file_set = set(f.upper() for f in files)

    # Check for known EXE names
    for build_name, cfg in KNOWN_BUILDS.items():
        exe_upper = cfg.exe_name.upper()
        if exe_upper in file_set:
            return build_name

    # Check for GAMECODE in any file path
    for build_name, cfg in KNOWN_BUILDS.items():
        if cfg.gamecode and any(cfg.gamecode.upper() in f.upper() for f in files):
            return build_name

    # Heuristic: look for Bubsy-specific file patterns
    bubsy_markers = [
        "BUBSY", "Bubsy", "bubsy",
        "ACCOLADE", "Accolade",
        "EIDETIC", "Eidetic",
    ]
    for marker in bubsy_markers:
        if any(marker in f for f in files):
            return "bubsy3d_unknown"

    # Generic PS1 detection
    if any(f.upper().endswith(".TMD") for f in files):
        return "generic_ps1_tmd_game"

    return "unknown"


def find_tmd_files(parser: ISOParser, build: BuildConfig) -> list:
    """Find all TMD files for the given build."""
    tmd_files = []
    prefix = build.tmd_subdir.upper()
    for path in parser.files.keys():
        if path.upper().endswith(".TMD"):
            if prefix in path.upper() or prefix == "":
                tmd_files.append(path)
    return sorted(tmd_files)


def find_tim_files(parser: ISOParser, build: BuildConfig) -> list:
    """Find all TIM files for the given build."""
    tim_files = []
    prefix = build.tim_subdir.upper()
    for path in parser.files.keys():
        if path.upper().endswith(".TIM"):
            if prefix in path.upper() or prefix == "":
                tim_files.append(path)
    return sorted(tim_files)
