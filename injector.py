"""
injector.py — Texture injection engine.

Orchestrates:
  1) Loading the disc image
  2) Identifying target files (standalone TIMs vs TMD geometry)
  3) Mapping pack textures to polygon groups / levels
  4) Converting PNG/JPEG replacements to TIM
  5) Injecting TIMs into TMD packets or replacing standalone TIM files
  6) Building a patched disc image (or patching in-place for ISO)

Supports dry-run mode: reports everything it *would* do without writing.
"""

import os
import shutil
import struct
import io
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from pathlib import Path

from config import BuildConfig, get_build_by_name
from rom_parser import ISOParser, open_ps1_image
from tim_handler import (
    TIMImage, TIM_MODE_16BPP, TIM_MODE_8BPP, TIM_MODE_4BPP,
    pil_to_tim, read_tim, save_tim, preview_tim,
)
from tmd_parser import (
    read_tmd, write_tmd, find_textured_primitives,
    find_flat_shaded_primitives, upgrade_flat_to_textured,
    patch_texture_reference, PrimitivePacket,
)

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


@dataclass
class InjectionTarget:
    """Describes one texture replacement target."""
    source_type: str          # "standalone_tim" or "tmd_packet"
    iso_path: str             # Path inside ISO (e.g. "DATA/TIM/LEVEL1.TIM")
    # For TMD packets:
    obj_index: int = 0
    prim_index: int = 0
    # For mapping:
    level_name: str = ""
    polygon_group: str = ""   # Logical group name from manifest
    # Replacement:
    replacement_path: Optional[str] = None  # Path to PNG/JPEG/BMP in pack
    replacement_tim: Optional[TIMImage] = None
    dry_run_preview: Optional[str] = None   # Path to preview PNG


@dataclass
class InjectionResult:
    success: bool
    message: str
    targets_processed: int = 0
    targets_failed: int = 0
    patched_iso_path: Optional[str] = None
    backup_path: Optional[str] = None
    log_lines: List[str] = field(default_factory=list)


class TextureInjector:
    """Main injection orchestrator."""

    def __init__(
        self,
        iso_path: str,
        build_config: BuildConfig,
        pack_dir: str,
        manifest: dict,
        dry_run: bool = False,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        self.iso_path = iso_path
        self.build_config = build_config
        self.pack_dir = pack_dir
        self.manifest = manifest
        self.dry_run = dry_run
        self.output_dir = output_dir or os.path.join(os.path.dirname(iso_path), "patched")
        self.progress_callback = progress_callback
        self.log: List[str] = []
        self.parser: Optional[ISOParser] = None
        self._temp_workspace: Optional[str] = None

    def _log(self, msg: str):
        self.log.append(msg)
        if self.progress_callback:
            # progress_callback(current, total, msg) — we pass (-1,-1) for log-only
            self.progress_callback(-1, -1, msg)

    def _notify_progress(self, current: int, total: int, msg: str = ""):
        if self.progress_callback:
            self.progress_callback(current, total, msg)

    def run(self) -> InjectionResult:
        """Execute full injection pipeline."""
        try:
            return self._run_pipeline()
        except Exception as e:
            self._log(f"FATAL: {e}")
            return InjectionResult(success=False, message=str(e), log_lines=self.log)

    def _run_pipeline(self) -> InjectionResult:
        # 1) Open disc image
        self._log(f"Opening disc image: {self.iso_path}")
        self.parser = open_ps1_image(self.iso_path)
        self._log(f"Volume label: {self.parser.volume_label}")
        self._log(f"Files on disc: {len(self.parser.files)}")

        # 2) Create temp workspace (unless dry-run where we skip disk writes)
        if not self.dry_run:
            self._temp_workspace = os.path.join(self.output_dir, "_workspace")
            os.makedirs(self._temp_workspace, exist_ok=True)
            self._log(f"Workspace: {self._temp_workspace}")

        # 3) Resolve targets from manifest
        targets = self._resolve_targets()
        self._log(f"Resolved {len(targets)} injection targets from manifest")

        # 4) Convert pack images to TIM
        self._prepare_tim_replacements(targets)

        # 5) Apply patches
        patched_data = self._apply_patches(targets)

        # 6) Build output ISO / backup
        if self.dry_run:
            self._log("DRY RUN — no files were written.")
            return InjectionResult(
                success=True,
                message="Dry run completed successfully.",
                targets_processed=len(targets),
                targets_failed=0,
                log_lines=self.log,
            )

        # Backup original
        backup_path = self._backup_original()

        # Write patched ISO
        patched_iso = self._write_patched_iso(patched_data)
        self._log(f"Patched ISO written: {patched_iso}")

        return InjectionResult(
            success=True,
            message="Injection complete.",
            targets_processed=len(targets),
            targets_failed=0,
            patched_iso_path=patched_iso,
            backup_path=backup_path,
            log_lines=self.log,
        )

    def _resolve_targets(self) -> List[InjectionTarget]:
        """Read manifest and map texture replacements to disc files / TMD packets."""
        targets: List[InjectionTarget] = []
        textures_map = self.manifest.get("textures", {})

        # Case A: Standalone TIM replacements (direct file swaps)
        for iso_file, replacement in textures_map.get("standalone_tim", {}).items():
            src_path = os.path.join(self.pack_dir, replacement)
            targets.append(InjectionTarget(
                source_type="standalone_tim",
                iso_path=iso_file,
                replacement_path=src_path,
            ))

        # Case B: TMD packet replacements by level / polygon group
        for level_name, level_def in textures_map.get("tmd_levels", {}).items():
            tmd_iso_path = level_def.get("tmd_file")
            if not tmd_iso_path:
                continue

            groups = level_def.get("polygon_groups", {})
            for group_name, group_def in groups.items():
                replacement = group_def.get("replacement")
                if not replacement:
                    continue

                src_path = os.path.join(self.pack_dir, replacement)
                targets.append(InjectionTarget(
                    source_type="tmd_packet",
                    iso_path=tmd_iso_path,
                    level_name=level_name,
                    polygon_group=group_name,
                    replacement_path=src_path,
                ))

        return targets

    def _prepare_tim_replacements(self, targets: List[InjectionTarget]):
        """Convert all PNG/JPEG replacements in the pack to TIMImage objects."""
        preferred_mode = self.build_config.preferred_tim_mode
        for idx, tgt in enumerate(targets):
            if not tgt.replacement_path or not os.path.exists(tgt.replacement_path):
                self._log(f"  SKIP: Replacement not found: {tgt.replacement_path}")
                continue
            try:
                if Image is None:
                    raise RuntimeError("Pillow not installed")
                img = Image.open(tgt.replacement_path)
                tgt.replacement_tim = pil_to_tim(img, bpp_mode=preferred_mode)
                self._log(f"  [{idx+1}/{len(targets)}] Converted {os.path.basename(tgt.replacement_path)} → TIM ({tgt.replacement_tim.width}×{tgt.replacement_tim.height})")
            except Exception as e:
                self._log(f"  ERROR converting {tgt.replacement_path}: {e}")

    def _apply_patches(self, targets: List[InjectionTarget]) -> Dict[str, bytes]:
        """
        Apply all patches in-memory.
        Returns a dict mapping ISO logical path → patched bytes.
        """
        patched_files: Dict[str, bytes] = {}

        # Group targets by ISO file for batch processing
        by_file: Dict[str, List[InjectionTarget]] = {}
        for tgt in targets:
            by_file.setdefault(tgt.iso_path, []).append(tgt)

        total_files = len(by_file)
        for fidx, (iso_path, tgts) in enumerate(by_file.items()):
            self._notify_progress(fidx, total_files, f"Patching {iso_path}...")
            try:
                original = self.parser.extract_file(iso_path)
            except KeyError:
                self._log(f"  FILE NOT FOUND in ISO: {iso_path}")
                continue

            if not tgts:
                continue

            # Determine if this is a standalone TIM or a TMD
            first = tgts[0]
            if first.source_type == "standalone_tim":
                # Direct replacement: swap entire file with our converted TIM
                if first.replacement_tim:
                    patched_files[iso_path] = first.replacement_tim.raw_bytes
                    self._log(f"  REPLACED {iso_path} ({len(original)} → {len(patched_files[iso_path])} bytes)")
                continue

            if first.source_type == "tmd_packet":
                # Parse TMD, apply per-packet patches, serialize back
                try:
                    model = read_tmd(original)
                except Exception as e:
                    self._log(f"  ERROR parsing TMD {iso_path}: {e}")
                    continue

                textured = find_textured_primitives(model)
                flat_shaded = find_flat_shaded_primitives(model)

                self._log(f"  TMD objects: {len(model.objects)}, textured prims: {len(textured)}, flat prims: {len(flat_shaded)}")

                # Apply each target
                for tgt in tgts:
                    applied = self._inject_into_tmd(model, tgt, textured, flat_shaded)
                    if applied:
                        self._log(f"    ✓ Injected {tgt.polygon_group} into {iso_path}")
                    else:
                        self._log(f"    ✗ Could not inject {tgt.polygon_group} into {iso_path}")

                # Re-serialize
                try:
                    new_bytes = write_tmd(model)
                    patched_files[iso_path] = new_bytes
                    self._log(f"  RE-SERIALIZED {iso_path} ({len(original)} → {len(new_bytes)} bytes)")
                except Exception as e:
                    self._log(f"  ERROR serializing TMD {iso_path}: {e}")
                continue

        return patched_files

    def _inject_into_tmd(
        self,
        model,
        tgt: InjectionTarget,
        textured_prims: List[Tuple[int, int, PrimitivePacket]],
        flat_prims: List[Tuple[int, int, PrimitivePacket]],
        color_mapper=None,
    ) -> bool:
        """Inject a replacement texture into a TMD model."""
        if not tgt.replacement_tim:
            return False

        # Strategy 1: If a color_mapper is attached, try smart surface-type injection
        if color_mapper and tgt.polygon_group:
            surface = tgt.polygon_group  # e.g. "grass", "lava", "water"
            # Find flat-shaded primitives whose color matches this surface type
            matched = []
            for oi, pi, pkt in flat_prims:
                if pkt.color:
                    r, g, b = pkt.color
                    detected = color_mapper.classify_color(r, g, b)
                    if detected == surface:
                        matched.append((oi, pi, pkt))
            
            if matched:
                # Upgrade ALL matched flat-shaded polygons to textured
                for oi, pi, pkt in matched:
                    n_vert = 4 if pkt.is_quad else 3
                    uvs = self._generate_uvs(n_vert, tgt.replacement_tim.width, tgt.replacement_tim.height)
                    texpage = self._make_texpage_for_tim(tgt.replacement_tim)
                    upgrade_flat_to_textured(pkt, uvs, texpage, clut_addr=0)
                self._log(f"    Smart-mapped {len(matched)} {surface} polygons via color detection")
                return True

        # Strategy 2: If the polygon group already has textured primitives, patch existing
        for oi, pi, pkt in textured_prims:
            new_texpage = self._make_texpage_for_tim(tgt.replacement_tim)
            new_clut = 0
            if tgt.replacement_tim.has_clut:
                new_clut = 0x0000
            n_vert = 4 if pkt.is_quad else 3
            uvs = self._generate_uvs(n_vert, tgt.replacement_tim.width, tgt.replacement_tim.height)
            patch_texture_reference(pkt, new_texpage, new_clut, uvs)
            return True

        # Strategy 3: Fallback — upgrade first flat-shaded primitive to textured
        if flat_prims:
            oi, pi, pkt = flat_prims[0]
            n_vert = 4 if pkt.is_quad else 3
            uvs = self._generate_uvs(n_vert, tgt.replacement_tim.width, tgt.replacement_tim.height)
            texpage = self._make_texpage_for_tim(tgt.replacement_tim)
            upgrade_flat_to_textured(pkt, uvs, texpage, clut_addr=0)
            return True

        return False

    def _generate_uvs(self, n_vert: int, tex_w: int, tex_h: int) -> List[Tuple[int, int]]:
        """Generate UV coordinates that tile across the polygon."""
        # For world-space mapping, generate UVs that cover the full texture
        # with slight variation based on vertex index
        uvs = []
        for i in range(n_vert):
            if n_vert == 3:
                # Triangle mapping: corners of texture
                corners = [(0, 0), (255, 0), (128, 255)]
                uvs.append(corners[i])
            elif n_vert == 4:
                # Quad mapping: full texture corners
                corners = [(0, 0), (255, 0), (255, 255), (0, 255)]
                uvs.append(corners[i])
            else:
                # Fallback for unusual vertex counts
                u = int((i / max(1, n_vert - 1)) * 255)
                v = int((i / max(1, n_vert - 1)) * 255)
                uvs.append((u, v))
        return uvs

    def _make_texpage_for_tim(self, tim: TIMImage) -> int:
        """Construct a basic TexPage register value for the TIM."""
        # TexPage bits (PS1 GPU):
        #  bit 0-3  : texture page X base (64×64 word steps) → (vram_x // 64)
        #  bit 4    : semi-transparent mode
        #  bit 5-6  : color mode (0=4bpp, 1=8bpp, 2=16bpp)
        #  bit 7-8  : dither
        #  bit 9-10 : drawing area
        # For simplicity we assume the replacement texture will be placed at
        # a known VRAM position by the emulator / mod loader.
        mode_bits = tim.bpp_mode  # 0,1,2
        page_x = (tim.vram_x // 64) & 0x0F
        texpage = (page_x) | (mode_bits << 5)
        return texpage

    def _backup_original(self) -> str:
        """Create .bak of the original image."""
        base, ext = os.path.splitext(self.iso_path)
        backup = base + ".bak"
        if not os.path.exists(backup):
            shutil.copy2(self.iso_path, backup)
            self._log(f"Backup created: {backup}")
        return backup

    def _write_patched_iso(self, patched_files: Dict[str, bytes]) -> str:
        """Build a new ISO with patched file contents."""
        os.makedirs(self.output_dir, exist_ok=True)
        out_name = Path(self.iso_path).stem + "_patched" + Path(self.iso_path).suffix
        out_path = os.path.join(self.output_dir, out_name)

        # For ISO 9660 Level 1, replacing files in-place without changing directory
        # tables or LBA layout is the safest approach: we overwrite the data sectors
        # of each replaced file, padding/truncating to fit the original size or
        # rewriting the whole image if the new data is larger.
        #
        # Simplified strategy: copy the whole image, then for each patched file
        # overwrite its sector range.  If the new data is larger than the original
        # allocated sectors, we can't safely grow without rebuilding ISO tables.
        # In that case, we write a warning and truncate.
        shutil.copy2(self.iso_path, out_path)

        with open(out_path, "r+b") as out_fp:
            for iso_path, new_data in patched_files.items():
                entry = self.parser.files.get(iso_path)
                if not entry:
                    continue
                max_size = entry.size
                if len(new_data) > max_size:
                    self._log(f"  WARNING: {iso_path} new data ({len(new_data)}) exceeds original ({max_size}). Truncated.")
                    new_data = new_data[:max_size]
                # Seek to LBA and overwrite
                out_fp.seek(entry.lba * self.parser._sector_size + self.parser._data_offset)
                out_fp.write(new_data)
                # If new data is smaller, pad with zeros (optional)
                if len(new_data) < max_size:
                    out_fp.write(b'\x00' * (max_size - len(new_data)))

        return out_path
