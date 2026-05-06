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
        "requires_confirmation": True,
        "description": "Lava — usually appears as BLACK AND WHITE CHECKERBOARD in Bubsy 3D!",
    },
    "mountain_sky": {
        "color_range": {"r": [60, 140], "g": [100, 180], "b": [180, 255]},
        "tolerance": 30,
        "textures": ["rock_01.png", "sky_01.png"],
        "uv_mode": "repeat",
        "requires_confirmation": True,
        "description": "Mountain or Sky — Level 1 mountains look BLUE, not water!",
    },
    "ground_rubble": {
        "color_range": {"r": [180, 255], "g": [80, 160], "b": [20, 80]},
        "tolerance": 35,
        "textures": ["dirt_01.png", "rock_01.png", "ground_01.png"],
        "uv_mode": "repeat",
        "description": "Ground and rubble — Bubsy 3D uses ORANGE for ground, NOT lava!",
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
    "stone_platform": {
        "color_range": {"r": [90, 160], "g": [90, 160], "b": [90, 160]},
        "tolerance": 25,
        "textures": ["rock_01.png", "stone_01.png", "ground_01.png"],
        "uv_mode": "repeat",
        "description": "Grey floating platforms — Bubsy 3D uses GREY for stone/rock platforms!",
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
    confidence: float = 0.0  # Detection confidence (0.0-1.0)
    needs_confirmation: bool = False  # Flag for ambiguous detections
    is_checkerboard_lava: bool = False  # Bubsy 3D specific signature
    warnings: List[Dict] = field(default_factory=list)  # Low-confidence warnings


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

    def classify_color(self, r: int, g: int, b: int) -> tuple:
        """Classify an RGB color into a surface type with confidence score."""
        best_match: Optional[str] = None
        best_score = float('inf')
        second_best_score = float('inf')
        all_scores = {}

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
                all_scores[surface] = score
                if score < best_score:
                    second_best_score = best_score
                    best_score = score
                    best_match = surface
                elif score < second_best_score:
                    second_best_score = score

        # Calculate confidence (0.0 - 1.0)
        confidence = 0.0
        if best_score != float('inf'):
            max_possible = 3 * 255  # Max RGB distance
            confidence = max(0.0, 1.0 - (best_score / max_possible))
            
            # Reduce confidence if second best is close
            if second_best_score != float('inf'):
                ratio = best_score / second_best_score if second_best_score > 0 else 1.0
                if ratio > 0.8:  # Second is very close
                    confidence *= 0.5

        needs_confirmation = False
        if best_match:
            mapping = self.color_map.get(best_match, {})
            if mapping.get("requires_confirmation", False):
                needs_confirmation = True
            # Also flag if confidence is low
            if confidence < 0.4:
                needs_confirmation = True

        return best_match, confidence, needs_confirmation
    
    def detect_checkerboard_lava(self, tmd_data: bytes, filename: str = "") -> List[ColorCluster]:
        """
        Detect checkerboard pattern (black/white alternating) = Bubsy 3D lava signature.
        Returns clusters marked as lava with high confidence.
        """
        try:
            model = read_tmd(tmd_data)
        except Exception:
            return []
        
        # Collect all flat-shaded primitive colors with positions
        colors_with_pos: List[Tuple[Tuple[int, int, int], int, int]] = []
        
        for obj_idx, obj in enumerate(model.objects):
            for prim_idx, pkt in enumerate(obj.primitives):
                if pkt.is_flat_shaded and pkt.color:
                    colors_with_pos.append((pkt.color, obj_idx, prim_idx))
        
        lava_clusters = []
        checked_indices = set()
        
        for i, (color1, obj1, prim1) in enumerate(colors_with_pos):
            if i in checked_indices:
                continue
            r1, g1, b1 = color1
            
            # Check if this is pure black or pure white
            is_black = r1 < 20 and g1 < 20 and b1 < 20
            is_white = r1 > 235 and g1 > 235 and b1 > 235
            
            if not (is_black or is_white):
                continue
            
            # Look for alternating pattern in nearby polygons
            checkerboard_group = [(color1, obj1, prim1)]
            expected_next = "white" if is_black else "black"
            
            for j, (color2, obj2, prim2) in enumerate(colors_with_pos[i+1:i+10]):
                r2, g2, b2 = color2
                is_black2 = r2 < 20 and g2 < 20 and b2 < 20
                is_white2 = r2 > 235 and g2 > 235 and b2 > 235
                
                if expected_next == "white" and is_white2:
                    checkerboard_group.append((color2, obj2, prim2))
                    expected_next = "black"
                    checked_indices.add(i + 1 + j)
                elif expected_next == "black" and is_black2:
                    checkerboard_group.append((color2, obj2, prim2))
                    expected_next = "white"
                    checked_indices.add(i + 1 + j)
                else:
                    break
            
            # If we found at least 3 alternating polygons, it's checkerboard
            if len(checkerboard_group) >= 3:
                cluster = ColorCluster(
                    surface_type="lava",
                    color=(0, 0, 0),  # Represent as black
                    polygon_count=len(checkerboard_group),
                    tmd_files=[filename],
                    obj_indices=[obj for _, obj, _ in checkerboard_group],
                    prim_indices=[prim for _, _, prim in checkerboard_group],
                )
                lava_clusters.append(cluster)
                for _, obj, prim in checkerboard_group:
                    checked_indices.add(colors_with_pos.index((color1, obj, prim)))
        
        return lava_clusters

    def scan_tmd_colors(self, tmd_data: bytes, filename: str = "") -> List[ColorCluster]:
        """Scan a TMD file and cluster flat-shaded polygons by color with confidence."""
        try:
            model = read_tmd(tmd_data)
        except Exception:
            return []

        # First, detect checkerboard lava (Bubsy 3D specific)
        lava_clusters = self.detect_checkerboard_lava(tmd_data, filename)
        lava_polys = set()
        for lc in lava_clusters:
            for oi, pi in zip(lc.obj_indices, lc.prim_indices):
                lava_polys.add((oi, pi))

        # Collect all flat-shaded primitive colors
        color_counts: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = defaultdict(list)

        for obj_idx, obj in enumerate(model.objects):
            for prim_idx, pkt in enumerate(obj.primitives):
                if pkt.is_flat_shaded and pkt.color:
                    # Skip if already detected as checkerboard lava
                    if (obj_idx, prim_idx) in lava_polys:
                        continue
                    color = pkt.color
                    color_counts[color].append((obj_idx, prim_idx))

        # Classify each unique color
        clusters: Dict[str, ColorCluster] = {}
        low_confidence_warnings = []
        
        for color, polys in color_counts.items():
            r, g, b = color
            surface, confidence, needs_confirmation = self.classify_color(r, g, b)
            
            if needs_confirmation and surface:
                low_confidence_warnings.append({
                    "color": color,
                    "surface": surface,
                    "confidence": confidence,
                    "polygon_count": len(polys),
                })
            
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

        # Add lava clusters
        all_clusters = list(clusters.values()) + lava_clusters
        
        # Attach warnings to the return
        for c in all_clusters:
            c.warnings = low_confidence_warnings
        
        return all_clusters

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
        
        # Show confidence summary
        all_warnings = []
        needs_manual_override = False
        
        for surface in sorted(all_clusters.keys()):
            clusters = all_clusters[surface]
            total_polys = sum(c.polygon_count for c in clusters)
            textures = self.color_map.get(surface, {}).get("textures", ["(none)"])
            mapping = self.color_map.get(surface, {})
            requires_confirmation = mapping.get("requires_confirmation", False)
            description = mapping.get("description", "")
            
            # Check for checkerboard lava
            is_checkerboard = any(c.is_checkerboard_lava for c in clusters)
            
            lines.append(f"🎨 {surface.upper()}")
            lines.append(f"   Polygons: {total_polys}")
            if is_checkerboard:
                lines.append(f"   ✅ CHECKERBOARD LAVA DETECTED — Bubsy 3D signature!")
            if requires_confirmation:
                lines.append(f"   ⚠️ REQUIRES CONFIRMATION — {description}")
                needs_manual_override = True
            if description and not requires_confirmation:
                lines.append(f"   ℹ️ {description}")
            lines.append(f"   Textures: {', '.join(textures)}")
            lines.append(f"   Files affected: {len(set(c.tmd_files for c in clusters))}")
            lines.append("")
            
            # Collect warnings
            for c in clusters:
                for w in c.warnings:
                    all_warnings.append(w)
        
        # Show warnings
        if all_warnings:
            lines.append("⚠️  LOW CONFIDENCE DETECTIONS (Manual review recommended):")
            seen = set()
            for w in all_warnings:
                key = (w["color"], w["surface"])
                if key not in seen:
                    seen.add(key)
                    r, g, b = w["color"]
                    lines.append(f"   • RGB({r},{g},{b}) detected as '{w['surface']}' — confidence: {w['confidence']:.0%}")
            lines.append("")
            needs_manual_override = True
        
        # Failsafe recommendation
        lines.append("=" * 60)
        if needs_manual_override:
            lines.append("🛡️ FAILSAFE RECOMMENDATION: Use MANUAL OVERRIDE mode!")
            lines.append("   The auto-detector found ambiguous colors that need your input.")
            lines.append("   Click 'Manual Override' to assign textures by hand.")
        else:
            lines.append("✅ Auto-detection looks safe for this ROM.")
            lines.append("   Review above and click INJECT when ready!")
        lines.append("=" * 60)
        
        # Add known problematic colors guide
        lines.append("")
        lines.append("📋 Bubsy 3D Color Quick Reference:")
        lines.append("   • Black/White checkerboard = LAVA (always)")
        lines.append("   • Orange/Brown = GROUND / RUBBLE (not lava!)")
        lines.append("   • Grey = STONE PLATFORMS (floating rock platforms)")
        lines.append("   • Blue mountains = MOUNTAIN (Level 1+, not water)")
        lines.append("   • Pure blue = WATER")
        lines.append("   • Green = GRASS")
        lines.append("   • White = SNOW")
        lines.append("=" * 60)

        return "\n".join(lines)

    def get_failsafe_recommendation(self, parser: ISOParser, tmd_files: List[str]) -> Tuple[str, str]:
        """
        Returns (mode, message) where mode is one of:
        - 'auto': Safe to auto-inject
        - 'assisted': Some ambiguous detections, recommend manual review
        - 'manual': Too risky, force manual override
        """
        total_warnings = 0
        total_checkerboard = 0
        total_polygons = 0
        
        for tmd_path in tmd_files:
            try:
                data = parser.extract_file(tmd_path)
                clusters = self.scan_tmd_colors(data, tmd_path)
                for c in clusters:
                    total_polygons += c.polygon_count
                    if c.is_checkerboard_lava:
                        total_checkerboard += c.polygon_count
                    total_warnings += len(c.warnings)
            except Exception:
                continue
        
        if total_checkerboard > 0 and total_warnings > 0:
            return "assisted", f"Found {total_checkerboard} checkerboard lava polygons + {total_warnings} ambiguous detections. Recommend manual review."
        elif total_warnings > 5:
            return "assisted", f"Found {total_warnings} ambiguous color detections. Recommend manual review."
        elif total_polygons == 0:
            return "manual", "No flat-shaded polygons detected. This ROM may not be compatible or already textured."
        else:
            return "auto", f"{total_polygons} polygons detected with clear surface types. Auto-injection should be safe."



def load_color_manifest(path: str) -> Dict[str, dict]:
    """Load a color mapping manifest from JSON."""
    with open(path, "r") as f:
        data = json.load(f)
    return data.get("color_map", DEFAULT_COLOR_MAP)
