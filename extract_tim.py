"""
extract_tim.py — Scan a PS1 ROM/ISO for embedded TIM textures and extract them.

This tool searches for TIM magic bytes (0x10 0x00) across the entire image,
then attempts to parse each potential TIM. Successfully parsed TIMs are saved
to a folder for analysis and comparison.

Usage:
    python extract_tim.py path/to/bubsy3d.iso --output extracted_tims/
"""

import struct
import os
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

from tim_handler import read_tim, TIMImage, tim_to_pil, save_tim, validate_tim_for_ps1


def scan_for_tim_offsets(data: bytes) -> List[int]:
    """Find all potential TIM starting positions by scanning for magic bytes."""
    offsets = []
    start = 0
    while True:
        idx = data.find(b'\x10\x00', start)
        if idx == -1:
            break
        # Check if this looks like a TIM header:
        # byte 2 = flags (BPP mode 0-3, CLUT bit)
        # byte 3 = 0x00 (reserved)
        if idx + 4 <= len(data):
            flags = data[idx + 2]
            reserved = data[idx + 3]
            bpp_mode = flags & 0x03
            has_clut = bool(flags & 0x08)
            # Basic sanity check: BPP mode must be 0-3
            if bpp_mode <= 3 and reserved == 0:
                offsets.append(idx)
        start = idx + 1
    return offsets


def try_parse_tim_at(data: bytes, offset: int, max_search_size: int = 0x100000) -> Optional[TIMImage]:
    """Attempt to parse a TIM at the given offset. Returns TIMImage on success, None on failure."""
    if offset >= len(data):
        return None
    
    # Try with a reasonable chunk size — TIMs in Bubsy 3D are typically 128×128 to 256×256
    chunk_size = min(max_search_size, len(data) - offset)
    chunk = data[offset:offset + chunk_size]
    
    try:
        tim = read_tim(chunk)
        # Validate it's actually a valid TIM (not a false positive)
        if tim.original_pixel_width > 256 or tim.original_pixel_height > 256:
            return None
        if tim.original_pixel_width == 0 or tim.original_pixel_height == 0:
            return None
        # Check that pixel data size makes sense
        expected_pixel_size = _calculate_pixel_data_size(tim)
        if len(tim.pixel_data) < expected_pixel_size * 0.5:  # Allow some variance
            return None
        return tim
    except Exception:
        return None


def _calculate_pixel_data_size(tim: TIMImage) -> int:
    """Calculate expected pixel data size based on TIM properties."""
    if tim.bpp_mode == 0:  # 4bpp
        # Each byte = 2 pixels, so total bytes = (w * h) / 2
        return (tim.original_pixel_width * tim.original_pixel_height) // 2
    elif tim.bpp_mode == 1:  # 8bpp
        return tim.original_pixel_width * tim.original_pixel_height
    elif tim.bpp_mode == 2:  # 16bpp
        return tim.original_pixel_width * tim.original_pixel_height * 2
    elif tim.bpp_mode == 3:  # 24bpp
        return tim.original_pixel_width * tim.original_pixel_height * 3
    return 0


def extract_tims_from_file(
    file_path: str,
    output_dir: str,
    min_size: int = 32,
    max_size: int = 256,
    export_png: bool = True,
    export_tim: bool = True,
) -> Tuple[int, int]:
    """
    Scan a file for TIM textures and extract them.
    
    Returns: (total_found, valid_extracted)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    with open(file_path, "rb") as f:
        data = f.read()
    
    print(f"Scanning {len(data)} bytes for TIM textures...")
    offsets = scan_for_tim_offsets(data)
    print(f"Found {len(offsets)} potential TIM signatures")
    
    extracted = 0
    total = 0
    
    for i, offset in enumerate(offsets):
        tim = try_parse_tim_at(data, offset)
        total += 1
        
        if tim is None:
            continue
        
        # Skip if dimensions are outside our target range
        if (tim.original_pixel_width < min_size or 
            tim.original_pixel_height < min_size or
            tim.original_pixel_width > max_size or 
            tim.original_pixel_height > max_size):
            continue
        
        # Validate PS1 compliance
        issues = validate_tim_for_ps1(tim)
        
        base_name = f"tim_{offset:08X}_{tim.original_pixel_width}x{tim.original_pixel_height}"
        
        # Export TIM
        if export_tim:
            tim_path = os.path.join(output_dir, f"{base_name}.tim")
            save_tim(tim, tim_path)
        
        # Export PNG preview
        if export_png and Image is not None:
            try:
                pil_img = tim_to_pil(tim)
                if pil_img:
                    png_path = os.path.join(output_dir, f"{base_name}.png")
                    pil_img.save(png_path)
            except Exception as e:
                print(f"  Warning: PNG export failed for {base_name}: {e}")
        
        # Save metadata
        meta_path = os.path.join(output_dir, f"{base_name}.txt")
        with open(meta_path, "w") as f:
            f.write(f"Offset: 0x{offset:08X}\n")
            f.write(f"Dimensions: {tim.original_pixel_width}x{tim.original_pixel_height}\n")
            f.write(f"BPP Mode: {tim.bpp_mode} ({['4bpp','8bpp','16bpp','24bpp'][tim.bpp_mode]})\n")
            f.write(f"Has CLUT: {tim.has_clut}\n")
            f.write(f"CLUT Colors: {tim.clut_colors}\n")
            f.write(f"VRAM Position: ({tim.vram_x}, {tim.vram_y})\n")
            f.write(f"Width Field: {tim.width} (TIM internal)\n")
            f.write(f"Height: {tim.height}\n")
            f.write(f"VRAM Size: {tim.vram_size_bytes} bytes\n")
            f.write(f"PS1 Compliant: {tim.is_ps1_compliant}\n")
            if issues:
                f.write("Compliance Issues:\n")
                for issue in issues:
                    f.write(f"  - {issue}\n")
        
        extracted += 1
        print(f"  ✓ Extracted {base_name} ({tim.original_pixel_width}x{tim.original_pixel_height}, "
              f"{['4bpp','8bpp','16bpp','24bpp'][tim.bpp_mode]})")
    
    print(f"\nDone! Found {total} candidates, extracted {extracted} valid TIMs to: {output_dir}")
    return total, extracted


def generate_tim_report(output_dir: str) -> str:
    """Generate a summary report of all extracted TIMs."""
    tim_files = sorted(Path(output_dir).glob("*.txt"))
    
    if not tim_files:
        return "No TIMs extracted yet."
    
    lines = [f"TIM Extraction Report — {len(tim_files)} textures found\n", "=" * 60]
    
    total_vram = 0
    bpp_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    size_counts = {}
    
    for meta_file in tim_files:
        with open(meta_file) as f:
            content = f.read()
        
        # Quick parse
        dims = "?"
        bpp = "?"
        vram = "?"
        compliant = "?"
        for line in content.split("\n"):
            if line.startswith("Dimensions:"):
                dims = line.split(":", 1)[1].strip()
                size_counts[dims] = size_counts.get(dims, 0) + 1
            elif line.startswith("BPP Mode:"):
                bpp = line.split(":", 1)[1].strip()
                # Count BPP
                try:
                    mode_num = int(bpp.split()[0])
                    bpp_counts[mode_num] = bpp_counts.get(mode_num, 0) + 1
                except:
                    pass
            elif line.startswith("VRAM Size:"):
                vram = line.split(":", 1)[1].strip().split()[0]
                try:
                    total_vram += int(vram)
                except:
                    pass
            elif line.startswith("PS1 Compliant:"):
                compliant = line.split(":", 1)[1].strip()
        
        lines.append(f"  {meta_file.stem}")
        lines.append(f"    Size: {dims} | {bpp} | VRAM: {vram} | Compliant: {compliant}")
    
    lines.extend(["", "Summary:", f"  Total VRAM: {total_vram:,} bytes ({total_vram/1024:.1f} KB)",
                  f"  4bpp: {bpp_counts[0]}, 8bpp: {bpp_counts[1]}, 16bpp: {bpp_counts[2]}, 24bpp: {bpp_counts[3]}"])
    
    if size_counts:
        lines.append("  Size distribution:")
        for size, count in sorted(size_counts.items()):
            lines.append(f"    {size}: {count}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract TIM textures from PS1 ROM/ISO")
    parser.add_argument("input_file", help="Path to PS1 ROM/ISO file")
    parser.add_argument("--output", "-o", default="extracted_tims", help="Output directory")
    parser.add_argument("--min-size", type=int, default=32, help="Minimum texture dimension")
    parser.add_argument("--max-size", type=int, default=256, help="Maximum texture dimension")
    parser.add_argument("--no-png", action="store_true", help="Skip PNG export")
    parser.add_argument("--no-tim", action="store_true", help="Skip TIM export")
    parser.add_argument("--report", "-r", action="store_true", help="Generate summary report")
    
    args = parser.parse_args()
    
    total, extracted = extract_tims_from_file(
        args.input_file,
        args.output,
        min_size=args.min_size,
        max_size=args.max_size,
        export_png=not args.no_png,
        export_tim=not args.no_tim,
    )
    
    if args.report:
        report = generate_tim_report(args.output)
        report_path = os.path.join(args.output, "REPORT.txt")
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")
        print(report)


if __name__ == "__main__":
    main()
