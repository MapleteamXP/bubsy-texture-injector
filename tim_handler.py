"""
tim_handler.py — Sony PlayStation TIM texture read/write + PNG/JPEG → TIM conversion.

TIM format basics:
  Header (16 bytes):
    0x00  : ID     = 0x10
    0x01  : Version= 0x00
    0x02-0x03: Flags
      bit 0-1: BPP mode  (0=4bpp, 1=8bpp, 2=16bpp, 3=24bpp)
      bit 2  : CLUT presence (1 for 4/8bpp, 0 for 16/24bpp)
      bit 3  : Reserved
      bit 4-7: CLUT org  (usually 0)
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
      0x04-0x05: X position in VRAM
      0x06-0x07: Y position in VRAM
      0x08-0x09: Width in pixels (word-aligned)
      0x0A-0x0B: Height in pixels
    Pixel data follows.

For 16bpp TIM we use direct 16-bit ABGR1555 color (bit 15 = semi-transparent flag).
For 4/8bpp TIM we generate a CLUT from the source image palette.
"""

import struct
import io
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
TIM_MODE_24BPP = 3


@dataclass
class TIMImage:
    """Parsed or created TIM texture."""
    bpp_mode: int               # 0,1,2,3
    has_clut: bool
    clut_data: Optional[bytes] = None   # Raw CLUT bytes (16-bit colors packed little-endian)
    clut_colors: int = 0        # 16 or 256
    clut_count: int = 1
    vram_x: int = 0
    vram_y: int = 0
    width: int = 0
    height: int = 0
    pixel_data: bytes = b""

    @property
    def raw_bytes(self) -> bytes:
        """Serialize TIM to bytes."""
        flags = (self.bpp_mode & 0x03) | (0x08 if self.has_clut else 0x00)
        buf = io.BytesIO()
        # TIM header
        buf.write(struct.pack("<BBBB", TIM_ID, TIM_VERSION, flags, 0))
        if self.has_clut:
            # CLUT length placeholder
            clut_header_len = 12
            clut_data_len = len(self.clut_data) if self.clut_data else 0
            buf.write(struct.pack("<I", clut_header_len + clut_data_len))
            buf.write(struct.pack("<I", 0x10))  # CLUT block offset relative to header start
            # CLUT block header
            buf.write(struct.pack("<I", clut_header_len + clut_data_len))
            buf.write(struct.pack("<HH", self.clut_count, self.clut_colors))
            if self.clut_data:
                buf.write(self.clut_data)
        else:
            buf.write(struct.pack("<I", 0))  # no CLUT
            buf.write(struct.pack("<I", 0x10))  # pixel block starts at 0x10

        # Pixel block
        pixel_block_header_len = 12
        pixel_data_len = len(self.pixel_data)
        buf.write(struct.pack("<I", pixel_block_header_len + pixel_data_len))
        buf.write(struct.pack("<HH", self.vram_x, self.vram_y))
        buf.write(struct.pack("<HH", self.width, self.height))
        buf.write(self.pixel_data)
        return buf.getvalue()


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

    tim = TIMImage(bpp_mode=bpp_mode, has_clut=has_clut)

    # Offsets
    clut_block_len = struct.unpack_from("<I", data, 4)[0]
    pixel_block_offset = struct.unpack_from("<I", data, 8)[0]

    if has_clut:
        clut_offset = 16  # Usually 0x10
        clut_hdr = struct.unpack_from("<IHH", data, clut_offset)
        clut_block_size, tim.clut_count, tim.clut_colors = clut_hdr
        clut_data_start = clut_offset + 12
        tim.clut_data = data[clut_data_start:clut_offset + clut_block_size]

    # Pixel block
    pix_hdr_offset = pixel_block_offset
    pix_block_size = struct.unpack_from("<I", data, pix_hdr_offset)[0]
    tim.vram_x, tim.vram_y = struct.unpack_from("<HH", data, pix_hdr_offset + 4)
    tim.width, tim.height = struct.unpack_from("<HH", data, pix_hdr_offset + 8)
    pixel_start = pix_hdr_offset + 12
    tim.pixel_data = data[pixel_start:pix_hdr_offset + pix_block_size]
    return tim


def tim_to_pil(tim: TIMImage) -> Optional["Image.Image"]:
    """Convert a TIM back into a PIL Image for preview."""
    if Image is None:
        return None

    if tim.bpp_mode == TIM_MODE_16BPP:
        # Decode 16bpp ABGR1555 directly
        img = Image.new("RGBA", (tim.width, tim.height))
        pixels = []
        for y in range(tim.height):
            row = []
            for x in range(tim.width):
                idx = (y * tim.width + x) * 2
                val = struct.unpack_from("<H", tim.pixel_data, idx)[0]
                r = ((val >> 0) & 0x1F) << 3
                g = ((val >> 5) & 0x1F) << 3
                b = ((val >> 10) & 0x1F) << 3
                a = 255 if (val & 0x8000) else 255  # semi-transparent flag ignored for preview
                row.append((r, g, b, a))
            pixels.extend(row)
        img.putdata(pixels)
        return img

    elif tim.bpp_mode in (TIM_MODE_4BPP, TIM_MODE_8BPP):
        if tim.clut_data is None:
            raise ValueError("CLUT missing for 4/8bpp TIM")
        palette = []
        color_count = tim.clut_colors
        for i in range(color_count):
            val = struct.unpack_from("<H", tim.clut_data, i * 2)[0]
            r = ((val >> 0) & 0x1F) << 3
            g = ((val >> 5) & 0x1F) << 3
            b = ((val >> 10) & 0x1F) << 3
            a = 255 if (val & 0x8000) else 255
            palette.extend([r, g, b, a])

        if tim.bpp_mode == TIM_MODE_8BPP:
            img = Image.new("P", (tim.width, tim.height))
            img.putpalette(palette)
            img.putdata(list(tim.pixel_data))
            return img.convert("RGBA")
        else:
            # 4bpp: unpack nibbles
            flat = []
            for b in tim.pixel_data:
                flat.append(b & 0x0F)
                flat.append((b >> 4) & 0x0F)
            # Width in TIM is stored as word count for 4bpp, so real pixel width = width*4?
            # Standard TIM 4bpp: width field is number of 16-pixel words. So real width = width*4?
            # Actually Sony docs: width is number of pixels for 8/16/24bpp, but number of 16-pixel
            # groups for 4bpp. Let's trust the unpacked length.
            real_w = len(flat) // tim.height if tim.height else tim.width
            img = Image.new("P", (real_w, tim.height))
            img.putpalette(palette)
            img.putdata(flat[:real_w * tim.height])
            return img.convert("RGBA")

    elif tim.bpp_mode == TIM_MODE_24BPP:
        img = Image.new("RGB", (tim.width, tim.height))
        pixels = []
        for y in range(tim.height):
            for x in range(tim.width):
                idx = (y * tim.width + x) * 3
                pixels.append((
                    tim.pixel_data[idx + 0],
                    tim.pixel_data[idx + 1],
                    tim.pixel_data[idx + 2],
                ))
        img.putdata(pixels)
        return img

    return None


# ── Create TIM from PIL Image ──
def pil_to_tim(
    img: "Image.Image",
    bpp_mode: int = TIM_MODE_16BPP,
    vram_x: int = 0,
    vram_y: int = 0,
) -> TIMImage:
    """Convert a PIL Image to a TIM. Recommended: 16bpp for quality on PS1."""
    if Image is None:
        raise RuntimeError("PIL/Pillow is required for image conversion")

    # Ensure dimensions fit PS1 constraints (max 256×256 typical, word-aligned)
    w, h = img.size
    if w > 256:
        h = int(h * (256 / w))
        w = 256
        img = img.resize((w, h), Image.LANCZOS)
    if h > 256:
        w = int(w * (256 / h))
        h = 256
        img = img.resize((w, h), Image.LANCZOS)

    img = img.convert("RGBA")

    if bpp_mode == TIM_MODE_16BPP:
        # Convert to 16bpp ABGR1555
        pixel_bytes = bytearray()
        for y in range(h):
            for x in range(w):
                r, g, b, a = img.getpixel((x, y))
                # Quantize to 5 bits per channel
                r5 = (r >> 3) & 0x1F
                g5 = (g >> 3) & 0x1F
                b5 = (b >> 3) & 0x1F
                semi = 1 if a < 128 else 0  # Simple alpha threshold
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
        )

    elif bpp_mode == TIM_MODE_8BPP:
        # Quantize to 256 colors
        img_p = img.quantize(colors=256, method=ImageQuantize.MEDIANCUT)
        palette_raw = img_p.getpalette()  # 768 ints [R,G,B, R,G,B, ...]
        clut_bytes = bytearray()
        for i in range(256):
            r = palette_raw[i * 3 + 0] >> 3
            g = palette_raw[i * 3 + 1] >> 3
            b = palette_raw[i * 3 + 2] >> 3
            val = (b << 10) | (g << 5) | r  # No STP flag for now
            clut_bytes.extend(struct.pack("<H", val))

        # Pixel data
        indices = list(img_p.tobytes())
        # Pad width to multiple of 2 for 8bpp
        if w % 2 != 0:
            padded_w = w + 1
            padded = bytearray()
            for y in range(h):
                row = indices[y * w:(y + 1) * w]
                row.append(0)
                padded.extend(row)
            indices = padded
            w = padded_w

        return TIMImage(
            bpp_mode=TIM_MODE_8BPP,
            has_clut=True,
            clut_data=bytes(clut_bytes),
            clut_colors=256,
            vram_x=vram_x,
            vram_y=vram_y,
            width=w,
            height=h,
            pixel_data=bytes(indices),
        )

    elif bpp_mode == TIM_MODE_4BPP:
        img_p = img.quantize(colors=16, method=ImageQuantize.MEDIANCUT)
        palette_raw = img_p.getpalette()
        clut_bytes = bytearray()
        for i in range(16):
            r = palette_raw[i * 3 + 0] >> 3
            g = palette_raw[i * 3 + 1] >> 3
            b = palette_raw[i * 3 + 2] >> 3
            val = (b << 10) | (g << 5) | r
            clut_bytes.extend(struct.pack("<H", val))

        flat = list(img_p.tobytes())
        # Pack nibbles
        packed = bytearray()
        for i in range(0, len(flat), 2):
            lo = flat[i] & 0x0F
            hi = (flat[i + 1] & 0x0F) if (i + 1) < len(flat) else 0
            packed.append((hi << 4) | lo)

        # TIM 4bpp width field is pixel count / 4 (words), but we'll store actual pixels
        # and let the injector adjust if needed.
        return TIMImage(
            bpp_mode=TIM_MODE_4BPP,
            has_clut=True,
            clut_data=bytes(clut_bytes),
            clut_colors=16,
            vram_x=vram_x,
            vram_y=vram_y,
            width=w // 4 if w % 4 == 0 else (w // 4 + 1),
            height=h,
            pixel_data=bytes(packed),
        )

    else:
        raise ValueError(f"Unsupported TIM mode: {bpp_mode}")


# ── File-level helpers ──
def load_tim(path: str) -> TIMImage:
    with open(path, "rb") as f:
        return read_tim(f.read())


def save_tim(tim: TIMImage, path: str):
    with open(path, "wb") as f:
        f.write(tim.raw_bytes)


def convert_image_to_tim(image_path: str, out_path: str, bpp_mode: int = TIM_MODE_16BPP):
    """High-level: PNG/JPEG/BMP → TIM."""
    if Image is None:
        raise RuntimeError("Pillow is required. Install: pip install Pillow")
    img = Image.open(image_path)
    tim = pil_to_tim(img, bpp_mode=bpp_mode)
    save_tim(tim, out_path)


def preview_tim(tim: TIMImage, out_path: str):
    """Export TIM preview as PNG."""
    if Image is None:
        raise RuntimeError("Pillow is required")
    pil_img = tim_to_pil(tim)
    if pil_img:
        pil_img.save(out_path)
