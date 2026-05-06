"""
color_mapper.py — Semantic color-to-texture mapping engine for Bubsy 3D.

This module implements the core innovation: analyzing flat-shaded polygon
colors in TMD files and mapping them to appropriate textures from the pack.

Key insight: Bubsy 3D's bare naked polygons use colors semantically:
  • Green polygons = grass areas
  • Red/orange polygons = lava/hazards
  • Blue polygons = water
  • Brown/gray polygons = rock/ground
  • etc.

The ColorMapper scans TMD primitive packets, clusters polygons by color,
and assigns textures based on the color manifest.
"""

import os
import json
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from tmd_parser import read_tmd, PrimitivePacket, TMDModel
from rom_parser import ISOParser


# ── Default color-to-surface mapping for Bubsy 3D ──
DEFAULT_COLOR_MAP = {
    "grass": {
        "color_range": {"r": [0, 60], "g": [120, 255], "b": [0, 80]},
        "tolerance": 25,
        "textures": ["grass_01.png"],
        "uv_mode": "repeat",
    },
    "water": {
        "color_range": {"r": [0, 40], "g": [40, 120], "b": [120, 255]},
        "tolerance": 20,
        "textures": ["water_01.png"],
        "uv_mode": "repeat",
    },
    "lava": {
        "color_range": {"r": [180, 255], "g": [0, 80], "b": [0, 40]},
        "tolerance": 30,
        "textures": ["lava_01.png"],
        "uv_mode": "repeat",
    },
    "rock": {
        "color_range": {"r": [80, 160], "g": [60, 120], "b": [40, 80]},
        "tolerance": 20,
        "textures": ["rock_01.png"],
        "uv_mode": "repeat",
    },
    "sand": {
        "color_range": {"r": [180, 255], "g": [140, 220], "b": [60, 120]},
        "tolerance": 25,
        "textures": ["sand_01.png"],
        "uv_mode": "repeat",
    },
    "snow": {
        "color_range": {"r": [200, 255], "g": [200, 255], "b": [200, 255]},
        "tolerance": 15,
        "textures": ["snow_01.png"],
        "uv_mode": "repeat",
    },
    "metal": {
        "color_range": {"r": [120, 180], "g": [120, 180], "b": [120, 180]},
        "tolerance": 20,
        "textures": ["metal_01.png"],
        "uv_mode": "repeat",
    },
    "wood": {
        "color_range": {"r": [120, 180], "g": [80, 120], "b": [20, 60]},
        "tolerance": 20,
        "textures": ["wood_01.png"],
        "uv_mode": "repeat",
    },
    "dirt": {
        "color_range": {"r": [100, 160], "g": [60, 100], "b": [20, 60]},
        "tolerance": 20,
        "textures": ["dirt_01.png"],
        "uv_mode": "repeat",
    },
}


@dataclass
class ColorCluster:
    """A cluster of polygons sharing a similar color."""
    surface_type: str
    color: Tuple[int, int, int]  # Representative RGB
    polygon_count: int = 0
    tmd_files: List[str] = field(default_factory=list)
    obj_indices: List[int] = field(default_factory=list)
    prim_indices: List[int] = field(default_factory=list)


class ColorMapper:
    """Maps polygon colors to surface types and selects textures."""

    def __init__(self, pack_dir: str, manifest_path: Optional[str] = None):
        self.pack_dir = pack_dir
        self.color_map: Dict[str, dict] = {}

        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                data = json.load(f)
            self.color_map = data.get("color_map", DEFAULT_COLOR_MAP)
        else:
            self.color_map = DEFAULT_COLOR_MAP

        # Build quick lookup
        self._surface_types = list(self.color_map.keys())

    def classify_color(self, r: int, g: int, b: int) -> Optional[str]:
        """Classify an RGB color into a surface type."""
        best_match: Optional[str] = None
        best_score = float('inf')

        for surface, mapping in self.color_map.items():
            cr = mapping.get("color_range", {})
            r_range = cr.get("r", [0, 255])
            g_range = cr.get("g", [0, 255])
            b_range = cr.get("b", [0, 255])
            tolerance = mapping.get("tolerance", 20)

            # Check if color falls within range (with tolerance)
            r_min, r_max = r_range[0] - tolerance, r_range[1] + tolerance
            g_min, g_max = g_range[0] - tolerance, g_range[1] + tolerance
            b_min, b_max = b_range[0] - tolerance, b_range[1] + tolerance

            if r_min <= r <= r_max and g_min <= g <= g_max and b_min <= b <= b_max:
                # Compute distance to center for scoring
                r_center = (r_range[0] + r_range[1]) / 2
                g_center = (g_range[0] + g_range[1]) / 2
                b_center = (b_range[0] + b_range[1]) / 2
                score = abs(r - r_center) + abs(g - g_center) + abs(b - b_center)
                if score < best_score:
                    best_score = score
                    best_match = surface

        return best_match

    def scan_tmd_colors(self, tmd_data: bytes, filename: str = "") -> List[ColorCluster]:
        """Scan a TMD file and cluster flat-shaded polygons by color."""
        try:
            model = read_tmd(tmd_data)
        except Exception:
            return []

        # Collect all flat-shaded primitive colors
        color_counts: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = defaultdict(list)

        for obj_idx, obj in enumerate(model.objects):
            for prim_idx, pkt in enumerate(obj.primitives):
                if pkt.is_flat_shaded and pkt.color:
                    color = pkt.color
                    # Normalize to 0-255 (PS1 uses 0-255 in packet data already)
                    color_counts[color].append((obj_idx, prim_idx))

        # Classify each unique color
        clusters: Dict[str, ColorCluster] = {}
        for color, polys in color_counts.items():
            r, g, b = color
            surface = self.classify_color(r, g, b)
            if surface:
                if surface not in clusters:
                    clusters[surface] = ColorCluster(
                        surface_type=surface,
                        color=color,
                    )
                clusters[surface].polygon_count += len(polys)
                clusters[surface].tmd_files.append(filename)
                for oi, pi in polys:
                    clusters[surface].obj_indices.append(oi)
                    clusters[surface].prim_indices.append(pi)

        return list(clusters.values())

    def preview_mapping(self, parser: ISOParser, tmd_files: List[str]) -> str:
        """Generate a text report of detected colors and their texture assignments."""
        lines = []
        lines.append("=" * 60)
        lines.append("COLOR-TO-TEXTURE MAPPING PREVIEW")
        lines.append("=" * 60)
        lines.append("")

        total_polygons = 0
        all_clusters: Dict[str, List[ColorCluster]] = defaultdict(list)

        for tmd_path in tmd_files:
            try:
                data = parser.extract_file(tmd_path)
                clusters = self.scan_tmd_colors(data, tmd_path)
                for c in clusters:
                    all_clusters[c.surface_type].append(c)
                    total_polygons += c.polygon_count
            except Exception as e:
                lines.append(f"  [ERROR] {tmd_path}: {e}")

        lines.append(f"Total TMD files scanned: {len(tmd_files)}")
        lines.append(f"Total textured polygons to be enhanced: {total_polygons}")
        lines.append("")

        for surface in sorted(all_clusters.keys()):
            clusters = all_clusters[surface]
            total_polys = sum(c.polygon_count for c in clusters)
            textures = self.color_map.get(surface, {}).get("textures", ["(none)"])
            lines.append(f"🎨 {surface.upper()}")
            lines.append(f"   Polygons: {total_polys}")
            lines.append(f"   Textures: {', '.join(textures)}")
            lines.append(f"   Files affected: {len(set(c.tmd_files for c in clusters))}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("This is what the injector will apply. Review and click INJECT when ready!")
        lines.append("=" * 60)

        return "\n".join(lines)

    def get_texture_for_surface(self, surface: str) -> Optional[str]:
        """Get the first texture file path for a surface type."""
        mapping = self.color_map.get(surface)
        if not mapping:
            return None
        textures = mapping.get("textures", [])
        if textures:
            return os.path.join(self.pack_dir, "textures", textures[0])
        return None


def load_color_manifest(path: str) -> Dict[str, dict]:
    """Load a color mapping manifest from JSON."""
    with open(path, "r") as f:
        data = json.load(f)
    return data.get("color_map", DEFAULT_COLOR_MAP)
