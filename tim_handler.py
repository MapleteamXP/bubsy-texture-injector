"""
tim_handler.py — Sony PlayStation TIM texture read/write + PNG/JPEG → TIM conversion.

PS1 HARDWARE COMPLIANCE — CRITICAL RULES:
  • Texture sizes MUST be power of 2: 8, 16, 32, 64, 128, 256
  • Width/height max 256 (PS1 GPU limit for single texture)
  • 4bpp: width field = number of 16-pixel WORDs (width // 4)
  • 8bpp: width field = actual pixel width
  • 16bpp: width field = actual pixel width
  • 24bpp: NOT SUPPORTED by PS1 hardware — we reject it
  • Total VRAM for textures: aim for < 512KB to leave room for framebuffers
  • CLUT for 4bpp: 16 colors, for 8bpp: 256 colors
  • CLUT stored separately in VRAM, referenced by address in primitive packet

TIM format:
  Header (16 bytes):
    0x00  : ID     = 0x10
    0x01  : Version= 0x00
    0x02-0x03: Flags
      bit 0-1: BPP mode  (0=4bpp, 1=8bpp, 2=16bpp)
      bit 2  : CLUT presence (1 for 4/8bpp, 0 for 16bpp)
    0x04-0x07: CLUT length in bytes (if CLUT present)
    0x08-0x0B: CLUT data offset relative to header (usually 0x10)
    0x0C-0x0F: Unknown / padding
  If CLUT present:
    CLUT header (12 bytes):
      0x00-0x03: Length of CLUT block (including this header)
      0x04-0x05: Number of CLUTs (usually 1)
      0x06-0x07: Colors per CLUT (16 for 4bpp, 256 for 8bpp)
      CLUT data follows — each color is 16-bit ABGR1555 / BGR555
  Pixel block:
    Header (12 bytes):
      0x00-0x03: Length of pixel block
      0x04-0x05: X position in VRAM (must align to TPAGE: 64 for 4/8bpp, 128 for 16bpp)
      0x06-0x07: Y position in VRAM
      0x08-0x09: Width in pixels (word-aligned, see above)
      0x0A-0x0B: Height in pixels
    Pixel data follows.
"""

import struct
import io
import math
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path

try:
    from PIL import Image, ImageQuantize
except ImportError:
    Image = None  # type: ignore


# ── TIM constants ──
TIM_ID = 0x10
TIM_VERSION = 0x00

TIM_MODE_4BPP = 0
TIM_MODE_8BPP = 1
TIM_MODE_16BPP = 2
TIM_MODE_24BPP = 3  # NOT SUPPORTED by PS1 hardware — we reject it

# PS1 VRAM limits
VRAM_TOTAL = 1024 * 1024  # 1 MB
VRAM_TEXTURE_BUDGET = 512 * 1024  # Leave half for framebuffers
TPAGE_WIDTH_4BPP_8BPP = 64   # TPAGE cell width for 4bpp/8bpp
TPAGE_WIDTH_16BPP = 128      # TPAGE cell width for 16bpp
TPAGE_HEIGHT = 256           # All modes


@dataclass
class TIMImage:
    """Parsed or created TIM texture with PS1 hardware compliance info."""
    bpp_mode: int               # 0, 1, 2 (24bpp rejected)
    has_clut: bool
    clut_data: Optional[bytes] = None
    clut_colors: int = 0        # 16 or 256
    clut_count: int = 1
    vram_x: int = 0
    vram_y: int = 0
    width: int = 0              # Width FIELD value (see PS1 rules above)
    height: int = 0             # Actual pixel height
    pixel_data: bytes = b""
    original_pixel_width: int = 0  # Store actual pixel width for UV calculation
    original_pixel_height: int = 0 # Store actual pixel height for UV calculation

    @property
    def raw_bytes(self) -> bytes:
        """Serialize TIM to bytes."""
        flags = (self.bpp_mode & 0x03) | (0x08 if self.has_clut else 0x00)
        buf = io.BytesIO()
        # TIM header
        buf.write(struct.pack("<BBBB", TIM_ID, TIM_VERSION, flags, 0))
        if self.has_clut:
            clut_header_len = 12
            clut_data_len = len(self.clut_data) if self.clut_data else 0
            buf.write(struct.pack("<I", clut_header_len + clut_data_len))
            buf.write(struct.pack("<I", 0x10))
            buf.write(struct.pack("<I", clut_header_len + clut_data_len))
            buf.write(struct.pack("<HH", self.clut_count, self.clut_colors))
            if self.clut_data:
                buf.write(self.clut_data)
        else:
            buf.write(struct.pack("<I", 0))
            buf.write(struct.pack("<I", 0x10))

        pixel_block_header_len = 12
        pixel_data_len = len(self.pixel_data)
        buf.write(struct.pack("<I", pixel_block_header_len + pixel_data_len))
        buf.write(struct.pack("<HH", self.vram_x, self.vram_y))
        buf.write(struct.pack("<HH", self.width, self.height))
        buf.write(self.pixel_data)
        return buf.getvalue()

    @property
    def vram_size_bytes(self) -> int:
        """Calculate VRAM footprint in bytes."""
        pixel_bytes = len(self.pixel_data)
        clut_bytes = len(self.clut_data) if self.clut_data else 0
        return pixel_bytes + clut_bytes

    @property
    def is_ps1_compliant(self) -> bool:
        """Check if this TIM follows PS1 hardware rules."""
        if self.bpp_mode == TIM_MODE_24BPP:
            return False
        if self.original_pixel_width > 256 or self.original_pixel_height > 256:
            return False
        # Power of 2 check
        if not _is_power_of_2(self.original_pixel_width) or not _is_power_of_2(self.original_pixel_height):
            return False
        # VRAM alignment
        if self.bpp_mode in (TIM_MODE_4BPP, TIM_MODE_8BPP):
            if self.vram_x % TPAGE_WIDTH_4BPP_8BPP != 0:
                return False
        elif self.bpp_mode == TIM_MODE_16BPP:
            if self.vram_x % TPAGE_WIDTH_16BPP != 0:
                return False
        return True


def _is_power_of_2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _next_power_of_2(n: int) -> int:
    """Return the next power of 2 >= n, capped at 256."""
    if n <= 0:
        return 8
    if n > 256:
        return 256
    return 1 << (n - 1).bit_length()


# ── Read TIM ──
def read_tim(data: bytes) -> TIMImage:
    """Parse a TIM file from bytes."""
    if len(data) < 16:
        raise ValueError("TIM file too small")
    if data[0] != TIM_ID or data[1] != TIM_VERSION:
        raise ValueError("Invalid TIM magic/version")

    flags = data[2]
    bpp_mode = flags & 0x03
    has_clut = bool(flags & 0x08)

    if bpp_mode == TIM_MODE_24BPP:
        raise ValueError("24bpp TIM is NOT supported by PS1 hardware!")

    tim = TIMImage(bpp_mode=bpp_mode, has_clut=has_clut)

    clut_block_len = struct.unpack_from("<I", data, 4)[0]
    pixel_block_offset = struct.unpack_from("<I", data, 8)[0]

    if has_clut:
        clut_offset = 16
        clut_hdr = struct.unpack_from("<IHH", data, clut_offset)
        clut_block_size, tim.clut_count, tim.clut_colors = clut_hdr
        clut_data_start = clut_offset + 12
        tim.clut_data = data[clut_data_start:clut_offset + clut_block_size]

    pix_hdr_offset = pixel_block_offset
    pix_block_size = struct.unpack_from("<I", data, pix_hdr_offset)[0]
    tim.vram_x, tim.vram_y = struct.unpack_from("<HH", data, pix_hdr_offset + 4)
    tim.width, tim.height = struct.unpack_from("<HH", data, pix_hdr_offset + 8)
    pixel_start = pix_hdr_offset + 12
    tim.pixel_data = data[pixel_start:pix_hdr_offset + pix_block_size]

    # Derive actual pixel dimensions from width field
    if bpp_mode == TIM_MODE_4BPP:
        tim.original_pixel_width = tim.width * 4
    else:
        tim.original_pixel_width = tim.width
    tim.original_pixel_height = tim.height

    return tim


def tim_to_pil(tim: TIMImage) -> Optional["Image.Image"]:
    """Convert a TIM back into a PIL Image for preview."""
    if Image is None:
        return None

    # Calculate actual pixel width for display
    if tim.bpp_mode == TIM_MODE_4BPP:
        actual_w = tim.width * 4
    else:
        actual_w = tim.width

    if tim.bpp_mode == TIM_MODE_16BPP:
        img = Image.new("RGBA", (actual_w, tim.height))
        pixels = []
        for y in range(tim.height):
            for x in range(actual_w):
                idx = (y * actual_w + x) * 2
                if idx + 2 > len(tim.pixel_data):
                    pixels.append((0, 0, 0, 255))
                    continue
                val = struct.unpack_from("<H", tim.pixel_data, idx)[0]
                r = ((val >> 0) & 0x1F) << 3
                g = ((val >> 5) & 0x1F) << 3
                b = ((val >> 10) & 0x1F) << 3
                a = 255 if (val & 0x8000) else 255
                pixels.append((r, g, b, a))
        img.putdata(pixels)
        return img

    elif tim.bpp_mode in (TIM_MODE_4BPP, TIM_MODE_8BPP):
        if tim.clut_data is None:
            raise ValueError("CLUT missing for 4/8bpp TIM")
        palette = []
        color_count = tim.clut_colors
        for i in range(color_count):
            if i * 2 + 2 > len(tim.clut_data):
                break
            val = struct.unpack_from("<H", tim.clut_data, i * 2)[0]
            r = ((val >> 0) & 0x1F) << 3
            g = ((val >> 5) & 0x1F) << 3
            b = ((val >> 10) & 0x1F) << 3
            a = 255 if (val & 0x8000) else 255
            palette.extend([r, g, b, a])

        if tim.bpp_mode == TIM_MODE_8BPP:
            img = Image.new("P", (actual_w, tim.height))
            img.putpalette(palette)
            indices = list(tim.pixel_data[:actual_w * tim.height])
            img.putdata(indices)
            return img.convert("RGBA")
        else:
            # 4bpp: unpack nibbles
            flat = []
            for b in tim.pixel_data:
                flat.append(b & 0x0F)
                flat.append((b >> 4) & 0x0F)
            img = Image.new("P", (actual_w, tim.height))
            img.putpalette(palette)
            img.putdata(flat[:actual_w * tim.height])
            return img.convert("RGBA")

    return None


# ── Create TIM from PIL Image ──
def pil_to_tim(
    img: "Image.Image",
    bpp_mode: int = TIM_MODE_16BPP,
    vram_x: int = 0,
    vram_y: int = 0,
    force_power_of_2: bool = True,
) -> TIMImage:
    """Convert a PIL Image to a PS1-compliant TIM.
    
    PS1 COMPLIANCE enforced:
      • Sizes rounded UP to nearest power of 2 (8, 16, 32, 64, 128, 256)
      • Max 256×256
      • 24bpp REJECTED
      • VRAM X position aligned to TPAGE
    """
    if Image is None:
        raise RuntimeError("PIL/Pillow is required for image conversion")
    if bpp_mode == TIM_MODE_24BPP:
        raise ValueError("24bpp is NOT supported by PS1 hardware!")

    # ── Step 1: Resize to PS1-compliant dimensions ──
    w, h = img.size
    orig_w, orig_h = w, h

    if force_power_of_2:
        w = _next_power_of_2(w)
        h = _next_power_of_2(h)
    else:
        # Still cap at 256 and ensure word alignment
        w = min(256, w)
        h = min(256, h)

    if w != orig_w or h != orig_h:
        img = img.resize((w, h), Image.LANCZOS)

    # Pad to word-aligned width for pixel data
    if bpp_mode == TIM_MODE_4BPP:
        # 4bpp: each byte = 2 pixels, so width must be even for clean packing
        if w % 2 != 0:
            w += 1
    elif bpp_mode == TIM_MODE_8BPP:
        # 8bpp: each byte = 1 pixel, width can be anything
        pass
    elif bpp_mode == TIM_MODE_16BPP:
        # 16bpp: each pixel = 2 bytes, width can be anything
        pass

    img = img.convert("RGBA")

    # ── Step 2: Align VRAM position to TPAGE ──
    if bpp_mode in (TIM_MODE_4BPP, TIM_MODE_8BPP):
        vram_x = (vram_x // TPAGE_WIDTH_4BPP_8BPP) * TPAGE_WIDTH_4BPP_8BPP
    elif bpp_mode == TIM_MODE_16BPP:
        vram_x = (vram_x // TPAGE_WIDTH_16BPP) * TPAGE_WIDTH_16BPP

    # ── Step 3: Convert pixel data ──
    if bpp_mode == TIM_MODE_16BPP:
        pixel_bytes = bytearray()
        for y in range(h):
            for x in range(w):
                r, g, b, a = img.getpixel((x, y))
                r5 = (r >> 3) & 0x1F
                g5 = (g >> 3) & 0x1F
                b5 = (b >> 3) & 0x1F
                semi = 1 if a < 128 else 0
                val = (semi << 15) | (b5 << 10) | (g5 << 5) | r5
                pixel_bytes.extend(struct.pack("<H", val))

        return TIMImage(
            bpp_mode=TIM_MODE_16BPP,
            has_clut=False,
            vram_x=vram_x,
            vram_y=vram_y,
            width=w,
            height=h,
            pixel_data=bytes(pixel_bytes),
            original_pixel_width=w,
            original_pixel_height=h,
        )

    elif bpp_mode == TIM_MODE_8BPP:
        img_p = img.quantize(colors=256, method=ImageQuantize.MEDIANCUT)
        palette_raw = img_p.getpalette()
        clut_bytes = bytearray()
        for i in range(256):
            if palette_raw and i * 3 + 2 < len(palette_raw):
                r = palette_raw[i * 3 + 0] >> 3
                g = palette_raw[i * 3 + 1] >> 3
                b = palette_raw[i * 3 + 2] >> 3
            else:
                r = g = b = 0
            val = (b << 10) | (g << 5) | r
            clut_bytes.extend(struct.pack("<H", val))

        indices = list(img_p.tobytes())
        # Pad each row to even width for alignment
        padded = bytearray()
        for y in range(h):
            row = indices[y * w:(y + 1) * w]
            if len(row) < w:
                row.extend([0] * (w - len(row)))
            padded.extend(row)

        return TIMImage(
            bpp_mode=TIM_MODE_8BPP,
            has_clut=True,
            clut_data=bytes(clut_bytes),
            clut_colors=256,
            vram_x=vram_x,
            vram_y=vram_y,
            width=w,
            height=h,
            pixel_data=bytes(padded),
            original_pixel_width=w,
            original_pixel_height=h,
        )

    elif bpp_mode == TIM_MODE_4BPP:
        img_p = img.quantize(colors=16, method=ImageQuantize.MEDIANCUT)
        palette_raw = img_p.getpalette()
        clut_bytes = bytearray()
        for i in range(16):
            if palette_raw and i * 3 + 2 < len(palette_raw):
                r = palette_raw[i * 3 + 0] >> 3
                g = palette_raw[i * 3 + 1] >> 3
                b = palette_raw[i * 3 + 2] >> 3
            else:
                r = g = b = 0
            val = (b << 10) | (g << 5) | r
            clut_bytes.extend(struct.pack("<H", val))

        flat = list(img_p.tobytes())
        # Pack nibbles: 2 pixels per byte
        packed = bytearray()
        for i in range(0, len(flat), 2):
            lo = flat[i] & 0x0F
            hi = (flat[i + 1] & 0x0F) if (i + 1) < len(flat) else 0
            packed.append((hi << 4) | lo)

        # 4bpp width field = number of 16-pixel WORDs = pixel_width / 4
        # But must be stored as a word value, not actual pixels
        tim_width_field = w // 4
        if w % 4 != 0:
            tim_width_field += 1

        return TIMImage(
            bpp_mode=TIM_MODE_4BPP,
            has_clut=True,
            clut_data=bytes(clut_bytes),
            clut_colors=16,
            vram_x=vram_x,
            vram_y=vram_y,
            width=tim_width_field,
            height=h,
            pixel_data=bytes(packed),
            original_pixel_width=w,
            original_pixel_height=h,
        )

    else:
        raise ValueError(f"Unsupported TIM mode: {bpp_mode}")


# ── VRAM layout manager ──
class VRAMLayout:
    """Track PS1 VRAM usage to ensure textures fit within hardware limits."""

    def __init__(self, texture_budget: int = VRAM_TEXTURE_BUDGET):
        self.budget = texture_budget
        self.used = 0
        self.textures: List[Tuple[str, int, int, int, int]] = []  # name, x, y, w, h

    def allocate(self, name: str, tim: TIMImage) -> Tuple[int, int]:
        """Allocate a texture position in VRAM. Returns (vram_x, vram_y)."""
        size = tim.vram_size_bytes
        if self.used + size > self.budget:
            raise RuntimeError(
                f"VRAM overflow! Need {size} bytes, only {self.budget - self.used} left. "
                f"Total used: {self.used}/{self.budget}. Consider using smaller textures or 4bpp mode."
            )

        # Simple layout: stack textures vertically within TPAGE columns
        # For production, you'd want a proper rectangle-packing algorithm
        bpp = tim.bpp_mode
        if bpp in (TIM_MODE_4BPP, TIM_MODE_8BPP):
            tpage_w = TPAGE_WIDTH_4BPP_8BPP
        else:
            tpage_w = TPAGE_WIDTH_16BPP

        # Place at next available TPAGE-aligned X, stack Y
        x = 0
        y = 0
        # Find a position that doesn't overlap
        # Simplified: just place sequentially
        if self.textures:
            last = self.textures[-1]
            y = last[2] + last[4]  # last_y + last_height
            if y + tim.height > TPAGE_HEIGHT:
                y = 0
                x = last[1] + tpage_w  # next TPAGE column

        self.used += size
        self.textures.append((name, x, y, tim.original_pixel_width, tim.original_pixel_height))
        return x, y

    def report(self) -> str:
        lines = [f"VRAM Usage: {self.used}/{self.budget} bytes ({100*self.used/self.budget:.1f}%)"]
        for name, x, y, w, h in self.textures:
            lines.append(f"  {name}: ({x},{y}) {w}×{h}")
        return "\n".join(lines)


# ── File-level helpers ──
def load_tim(path: str) -> TIMImage:
    with open(path, "rb") as f:
        return read_tim(f.read())


def save_tim(tim: TIMImage, path: str):
    with open(path, "wb") as f:
        f.write(tim.raw_bytes)


def convert_image_to_tim(
    image_path: str,
    out_path: str,
    bpp_mode: int = TIM_MODE_16BPP,
    vram_x: int = 0,
    vram_y: int = 0,
):
    """High-level: PNG/JPEG/BMP → PS1-compliant TIM."""
    if Image is None:
        raise RuntimeError("Pillow is required. Install: pip install Pillow")
    img = Image.open(image_path)
    tim = pil_to_tim(img, bpp_mode=bpp_mode, vram_x=vram_x, vram_y=vram_y)
    save_tim(tim, out_path)


def preview_tim(tim: TIMImage, out_path: str):
    """Export TIM preview as PNG."""
    if Image is None:
        raise RuntimeError("Pillow is required")
    pil_img = tim_to_pil(tim)
    if pil_img:
        pil_img.save(out_path)


def validate_tim_for_ps1(tim: TIMImage) -> List[str]:
    """Return list of compliance issues, or empty if fully compliant."""
    issues = []
    if tim.bpp_mode == TIM_MODE_24BPP:
        issues.append("24bpp is NOT supported by PS1 hardware")
    if tim.original_pixel_width > 256:
        issues.append(f"Width {tim.original_pixel_width} exceeds PS1 max of 256")
    if tim.original_pixel_height > 256:
        issues.append(f"Height {tim.original_pixel_height} exceeds PS1 max of 256")
    if not _is_power_of_2(tim.original_pixel_width):
        issues.append(f"Width {tim.original_pixel_width} is not a power of 2 (required: 8,16,32,64,128,256)")
    if not _is_power_of_2(tim.original_pixel_height):
        issues.append(f"Height {tim.original_pixel_height} is not a power of 2 (required: 8,16,32,64,128,256)")
    if tim.bpp_mode in (TIM_MODE_4BPP, TIM_MODE_8BPP):
        if tim.vram_x % TPAGE_WIDTH_4BPP_8BPP != 0:
            issues.append(f"VRAM X={tim.vram_x} not aligned to {TPAGE_WIDTH_4BPP_8BPP} (4bpp/8bpp TPAGE)")
    elif tim.bpp_mode == TIM_MODE_16BPP:
        if tim.vram_x % TPAGE_WIDTH_16BPP != 0:
            issues.append(f"VRAM X={tim.vram_x} not aligned to {TPAGE_WIDTH_16BPP} (16bpp TPAGE)")
    return issues
