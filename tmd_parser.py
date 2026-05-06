"""
tmd_parser.py — Sony PlayStation TMD (Transformed Model Data) parser.

TMD is the native geometry format used by many PS1 games including Bubsy 3D.
It contains:
  • Fixed header
  • Object table (one or more objects)
  • Each object has a primitive packet stream
  • Primitive packets describe polygons with vertex refs, normals, colors, UVs, texture info

Primitive packet opcodes we care about:
  Flat-shaded polygons (no texture):
    0x20-0x23 : Triangle / Quad, flat shaded, no texture
  Texture-mapped polygons:
    0x24-0x27 : Triangle / Quad, texture-mapped (with UVs + texpage)
    0x30-0x37 : Triangle / Quad, texture-mapped + gouraud + etc.

For texture injection we need to:
  1) Find all primitive packets that reference textures
  2) Record UV coordinate ranges, texture page numbers, CLUT addresses
  3) Identify flat-shaded polygons that could be upgraded to texture-mapped
  4) Provide hooks to rewrite packet data (inject TIM references / UVs)

References:
  • libpsx (psxdev.net) TMD docs
  • No$PSX specs
"""

import struct
import io
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


# ── Data structures ──
@dataclass
class TMDVertex:
    x: int
    y: int
    z: int
    pad: int = 0

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "TMDVertex":
        x, y, z, pad = struct.unpack_from("<hhhh", data, offset)
        return cls(x, y, z, pad)


@dataclass
class TMDNormal:
    nx: int
    ny: int
    nz: int
    pad: int = 0

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> "TMDNormal":
        nx, ny, nz, pad = struct.unpack_from("<hhhh", data, offset)
        return cls(nx, ny, nz, pad)


@dataclass
class PrimitivePacket:
    """One primitive packet inside a TMD object."""
    opcode: int                 # First byte — primitive type
    info_byte: int              # Second byte — flags / mode
    length: int                 # Third byte — packet size in words (32-bit words)
    data: bytes                 # Raw packet body (variable length)

    # Decoded fields (populated by decoder)
    is_textured: bool = False
    is_flat_shaded: bool = False
    is_gouraud: bool = False
    is_quad: bool = False
    has_transparency: bool = False
    vertex_indices: List[int] = field(default_factory=list)
    normal_indices: List[int] = field(default_factory=list)
    uv_coords: List[Tuple[int, int]] = field(default_factory=list)  # (u, v) per vertex
    color: Optional[Tuple[int, int, int]] = None  # (R, G, B) for flat shaded
    texpage: int = 0            # Texture page register value
    clut_addr: int = 0          # CLUT address in VRAM (for 4/8bpp)
    palette_id: int = 0

    @property
    def raw_size(self) -> int:
        """Return byte length of this packet (header + data)."""
        return 3 + len(self.data)


@dataclass
class TMDObject:
    """One object inside a TMD model."""
    obj_index: int
    n_vert: int
    n_norm: int
    n_prim: int
    scale: int
    vertices: List[TMDVertex] = field(default_factory=list)
    normals: List[TMDNormal] = field(default_factory=list)
    primitives: List[PrimitivePacket] = field(default_factory=list)

    # Byte offsets into the original file for safe rewriting
    vertex_offset: int = 0
    normal_offset: int = 0
    primitive_offset: int = 0


@dataclass
class TMDModel:
    """Complete parsed TMD."""
    id: int
    flags: int
    n_obj: int
    objects: List[TMDObject] = field(default_factory=list)
    raw_data: bytes = b""        # Original bytes for patching

    # Maps: (obj_idx, prim_idx) -> original primitive data byte offset
    _prim_offsets: Dict[Tuple[int, int], int] = field(default_factory=dict, repr=False)


# ── Primitive decoders ──
def _decode_triangle_flat(packet: PrimitivePacket):
    packet.is_flat_shaded = True
    packet.is_quad = False
    if len(packet.data) >= 12:
        packet.color = (packet.data[0], packet.data[1], packet.data[2])
        vi = struct.unpack_from("<HHH", packet.data, 4)
        packet.vertex_indices = list(vi)
        ni = struct.unpack_from("<HHH", packet.data, 10) if len(packet.data) >= 16 else (0, 0, 0)
        packet.normal_indices = list(ni)


def _decode_triangle_tex(packet: PrimitivePacket):
    packet.is_textured = True
    packet.is_flat_shaded = False
    packet.is_quad = False
    d = packet.data
    if len(d) >= 12:
        # Byte 0-2: color/brightness (ignored for pure textured)
        # Byte 3: padding
        vi = struct.unpack_from("<HHH", d, 4)
        packet.vertex_indices = list(vi)
        ni = struct.unpack_from("<HHH", d, 10) if len(d) >= 16 else (0, 0, 0)
        packet.normal_indices = list(ni)
        # UVs start after vertex indices — offset varies by exact packet subtype
        uv_offset = 16
        if len(d) >= uv_offset + 12:
            uvs = []
            for i in range(3):
                u, v = struct.unpack_from("<BB", d, uv_offset + i * 4)
                uvs.append((u, v))
            packet.uv_coords = uvs
            # Texpage / CLUT may follow UVs
            if len(d) >= uv_offset + 16:
                packet.clut_addr = struct.unpack_from("<H", d, uv_offset + 12)[0]
                packet.texpage = struct.unpack_from("<H", d, uv_offset + 14)[0]


def _decode_quad_flat(packet: PrimitivePacket):
    packet.is_flat_shaded = True
    packet.is_quad = True
    if len(packet.data) >= 14:
        packet.color = (packet.data[0], packet.data[1], packet.data[2])
        vi = struct.unpack_from("<HHHH", packet.data, 4)
        packet.vertex_indices = list(vi)


def _decode_quad_tex(packet: PrimitivePacket):
    packet.is_textured = True
    packet.is_quad = True
    d = packet.data
    if len(d) >= 14:
        vi = struct.unpack_from("<HHHH", d, 4)
        packet.vertex_indices = list(vi)
        uv_offset = 20
        if len(d) >= uv_offset + 16:
            uvs = []
            for i in range(4):
                u, v = struct.unpack_from("<BB", d, uv_offset + i * 4)
                uvs.append((u, v))
            packet.uv_coords = uvs
            if len(d) >= uv_offset + 20:
                packet.clut_addr = struct.unpack_from("<H", d, uv_offset + 16)[0]
                packet.texpage = struct.unpack_from("<H", d, uv_offset + 18)[0]


def decode_primitive(packet: PrimitivePacket) -> PrimitivePacket:
    """Enrich a raw PrimitivePacket with decoded fields."""
    opc = packet.opcode
    if opc in (0x20, 0x21, 0x22, 0x23):
        _decode_triangle_flat(packet) if opc in (0x20, 0x21) else _decode_quad_flat(packet)
    elif opc in (0x24, 0x25, 0x26, 0x27):
        _decode_triangle_tex(packet) if opc in (0x24, 0x25) else _decode_quad_tex(packet)
    elif opc in (0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37):
        packet.is_gouraud = True
        if opc in (0x34, 0x35, 0x36, 0x37):
            packet.is_textured = True
            if opc in (0x34, 0x35):
                _decode_triangle_tex(packet)
            else:
                _decode_quad_tex(packet)
        else:
            _decode_triangle_flat(packet) if opc in (0x30, 0x31) else _decode_quad_flat(packet)
    return packet


# ── Parser ──
def read_tmd(data: bytes) -> TMDModel:
    """Parse a TMD model from bytes."""
    if len(data) < 12:
        raise ValueError("TMD data too short")

    model = TMDModel(raw_data=data)
    model.id = struct.unpack_from("<I", data, 0)[0]
    model.flags = struct.unpack_from("<I", data, 4)[0]
    model.n_obj = struct.unpack_from("<I", data, 8)[0]

    # Header length = 12 bytes (id, flags, n_obj)
    # Object table follows immediately
    obj_table_offset = 12
    for i in range(model.n_obj):
        off = obj_table_offset + i * 12
        vert_top = struct.unpack_from("<I", data, off)[0]
        n_vert = struct.unpack_from("<I", data, off + 4)[0]
        norm_top = struct.unpack_from("<I", data, off + 8)[0]
        n_norm = struct.unpack_from("<I", data, off + 12)[0]
        prim_top = struct.unpack_from("<I", data, off + 16)[0]
        n_prim = struct.unpack_from("<I", data, off + 20)[0]
        scale = struct.unpack_from("<I", data, off + 24)[0]

        obj = TMDObject(
            obj_index=i,
            n_vert=n_vert,
            n_norm=n_norm,
            n_prim=n_prim,
            scale=scale,
            vertex_offset=vert_top,
            normal_offset=norm_top,
            primitive_offset=prim_top,
        )

        # Vertices (8 bytes each: x,y,z,pad as signed shorts)
        for v in range(n_vert):
            obj.vertices.append(TMDVertex.from_bytes(data, vert_top + v * 8))

        # Normals
        for n in range(n_norm):
            obj.normals.append(TMDNormal.from_bytes(data, norm_top + n * 8))

        # Primitives
        pos = prim_top
        prim_idx = 0
        for _ in range(n_prim):
            if pos + 3 > len(data):
                break
            opcode = data[pos]
            info = data[pos + 1]
            length = data[pos + 2]  # length in 32-bit words
            # Actual primitive length in bytes = length * 4, but header is 3 bytes.
            # Wait: Sony docs say length is in words INCLUDING the 1-word header.
            # So data length in bytes = (length * 4) - 4?  No — the standard
            # interpretation is: packet size = length * 4 bytes total (opcode+info+len+data).
            # However many dumps use length as "extra words after header".
            # We'll use: total bytes = max(4, length * 4)
            total_bytes = max(4, length * 4)
            pkt_data = data[pos + 3:pos + total_bytes]
            pkt = PrimitivePacket(
                opcode=opcode,
                info_byte=info,
                length=length,
                data=pkt_data,
            )
            decode_primitive(pkt)
            obj.primitives.append(pkt)
            model._prim_offsets[(i, prim_idx)] = pos
            prim_idx += 1
            pos += total_bytes

        model.objects.append(obj)

    return model


def write_tmd(model: TMDModel) -> bytes:
    """Serialize TMD back to bytes. Supports patching primitive packets."""
    buf = io.BytesIO(model.raw_data)

    # Only primitive packets may have changed size; for simplicity we rewrite
    # the whole TMD with the same object table layout but updated primitive data.
    # If a primitive packet grew, we may need to shift everything after it.
    # For production we do a full rebuild.
    out = io.BytesIO()
    out.write(struct.pack("<III", model.id, model.flags, model.n_obj))

    # Compute new layout
    obj_table_size = model.n_obj * 12 * 4  # Actually each entry is 7*4 = 28 bytes? Wait.
    # Standard TMD object top table: each entry is 3 DWORDs?  No.
    # vert_top, n_vert, norm_top, n_norm, prim_top, n_prim, scale = 7 * 4 = 28 bytes per object
    obj_table_entry_size = 28
    header_size = 12
    obj_table_offset = header_size

    current_offset = obj_table_offset + model.n_obj * obj_table_entry_size

    for obj in model.objects:
        vert_top = current_offset
        current_offset += obj.n_vert * 8
        norm_top = current_offset
        current_offset += obj.n_norm * 8
        prim_top = current_offset

        # Write primitives
        for pkt in obj.primitives:
            out.seek(prim_top)
            out.write(struct.pack("<BBB", pkt.opcode, pkt.info_byte, pkt.length))
            out.write(pkt.data)
            prim_top += 3 + len(pkt.data)
            # Pad to 4-byte alignment
            while (prim_top % 4) != 0:
                out.write(b'\x00')
                prim_top += 1

        # Write vertices
        out.seek(vert_top)
        for v in obj.vertices:
            out.write(struct.pack("<hhhh", v.x, v.y, v.z, v.pad))

        # Write normals
        out.seek(norm_top)
        for n in obj.normals:
            out.write(struct.pack("<hhhh", n.nx, n.ny, n.nz, n.pad))

        # Write object table entry
        entry_offset = obj_table_offset + obj.obj_index * obj_table_entry_size
        out.seek(entry_offset)
        out.write(struct.pack("<IIIIIII",
                              vert_top, obj.n_vert,
                              norm_top, obj.n_norm,
                              prim_top, obj.n_prim,
                              obj.scale))

    out.seek(0, io.SEEK_END)
    return out.getvalue()


# ── Helpers for injection ──
def find_textured_primitives(model: TMDModel) -> List[Tuple[int, int, PrimitivePacket]]:
    """Return list of (obj_index, prim_index, packet) for all texture-mapped primitives."""
    result = []
    for oi, obj in enumerate(model.objects):
        for pi, pkt in enumerate(obj.primitives):
            if pkt.is_textured:
                result.append((oi, pi, pkt))
    return result


def find_flat_shaded_primitives(model: TMDModel) -> List[Tuple[int, int, PrimitivePacket]]:
    """Return list of (obj_index, prim_index, packet) for flat-shaded primitives."""
    result = []
    for oi, obj in enumerate(model.objects):
        for pi, pkt in enumerate(obj.primitives):
            if pkt.is_flat_shaded and not pkt.is_textured:
                result.append((oi, pi, pkt))
    return result


def upgrade_flat_to_textured(
    packet: PrimitivePacket,
    uv_coords: List[Tuple[int, int]],
    texpage: int,
    clut_addr: int = 0,
) -> PrimitivePacket:
    """
    Convert a flat-shaded primitive to a texture-mapped one.
    This REPLACES the packet raw bytes — caller must ensure UV list length matches vertex count.
    """
    if packet.is_quad:
        new_opcode = 0x26  # Quad textured
        n_vert = 4
    else:
        new_opcode = 0x24  # Triangle textured
        n_vert = 3

    if len(uv_coords) < n_vert:
        raise ValueError(f"Need {n_vert} UVs, got {len(uv_coords)}")

    new_data = bytearray()
    # Brightness/color word (4 bytes) — white full brightness
    new_data.extend(b'\x80\x80\x80\x00')
    # Vertex indices (2 bytes each)
    for vi in packet.vertex_indices[:n_vert]:
        new_data.extend(struct.pack("<H", vi))
    # Normal indices (2 bytes each) — reuse existing if available
    for ni in packet.normal_indices[:n_vert]:
        new_data.extend(struct.pack("<H", ni))
    else:
        if len(packet.normal_indices) < n_vert:
            for _ in range(n_vert - len(packet.normal_indices)):
                new_data.extend(struct.pack("<H", 0))

    # UV coords (u, v) per vertex, 4 bytes each (2 for UV, 2 padding or CLUT/texpage)
    for i in range(n_vert):
        u, v = uv_coords[i]
        new_data.extend(struct.pack("<BB", u, v))
        if i == 0:
            # First vertex gets CLUT address
            new_data.extend(struct.pack("<H", clut_addr))
        elif i == 1:
            # Second vertex gets TexPage
            new_data.extend(struct.pack("<H", texpage))
        else:
            new_data.extend(b'\x00\x00')

    packet.opcode = new_opcode
    packet.info_byte = 0x00
    # Recalculate length in words (total bytes / 4)
    packet.length = max(1, (4 + len(new_data)) // 4)
    packet.data = bytes(new_data)
    packet.is_textured = True
    packet.is_flat_shaded = False
    packet.uv_coords = uv_coords[:n_vert]
    packet.texpage = texpage
    packet.clut_addr = clut_addr
    return packet


def patch_texture_reference(
    packet: PrimitivePacket,
    new_texpage: int,
    new_clut_addr: int,
    new_uvs: Optional[List[Tuple[int, int]]] = None,
) -> PrimitivePacket:
    """
    Update an already-textured primitive with a new texpage / CLUT / UVs.
    Modifies packet in-place and returns it.
    """
    if not packet.is_textured:
        raise ValueError("Cannot patch texture ref on non-textured primitive")

    packet.texpage = new_texpage
    packet.clut_addr = new_clut_addr
    if new_uvs:
        packet.uv_coords = new_uvs

    # Rewrite the raw data bytes where texpage / CLUT / UVs live.
    # This is a best-effort in-place patch.  For robustness, the caller should
    # use upgrade_flat_to_textured or full rebuild.
    d = bytearray(packet.data)
    # UVs start at offset 12 for triangle textured, 16 for quad textured
    # We overwrite the UVs and the embedded CLUT/texpage words.
    n_vert = 4 if packet.is_quad else 3
    base_uv = 12 if not packet.is_quad else 16  # rough; varies by gouraud flags
    if len(d) >= base_uv + n_vert * 4:
        for i in range(n_vert):
            if new_uvs and i < len(new_uvs):
                u, v = new_uvs[i]
                struct.pack_into("<BB", d, base_uv + i * 4, u, v)
            if i == 0 and len(d) >= base_uv + (i + 1) * 4 - 2:
                struct.pack_into("<H", d, base_uv + i * 4 + 2, new_clut_addr)
            if i == 1 and len(d) >= base_uv + (i + 1) * 4 - 2:
                struct.pack_into("<H", d, base_uv + i * 4 + 2, new_texpage)
    packet.data = bytes(d)
    return packet
