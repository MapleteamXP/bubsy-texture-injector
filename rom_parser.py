"""
rom_parser.py — PS1 disc image parser (BIN/CUE and ISO 9660).

Supports:
  • Raw ISO 9660 files (.iso)
  • BIN/CUE pairs where the BIN is a raw 2352-byte/sector image
  • Simple MODE1/2048 and MODE2/2352 extraction

Produces an in-memory file tree so callers can extract files by ISO path.
"""

import os
import struct
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, BinaryIO, Tuple
from pathlib import Path


SECTOR_SIZE_2048 = 2048
SECTOR_SIZE_2352 = 2352


@dataclass
class IsoFileEntry:
    """Represents a single file or directory inside ISO 9660."""
    name: str                     # ISO name (e.g. "SLUS_001.06;1")
    ext_name: str                 # Rock Ridge / Joliet cleaned name (best effort)
    is_directory: bool
    lba: int                      # Logical block address (sector start)
    size: int                     # File size in bytes
    parent_path: str = ""         # Logical path like "DATA/TMD"
    raw_sector_size: int = SECTOR_SIZE_2048  # 2048 or 2352
    data_offset_in_sector: int = 0


class ISOParser:
    """Parse ISO 9660 from a raw disc image stream."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fp: Optional[BinaryIO] = None
        self._sector_size = SECTOR_SIZE_2048
        self._data_offset = 0          # In a 2352 image, user data starts at offset 0x10 (MODE1) or 0x18 (MODE2 XA)
        self.volume_label = ""
        self.files: Dict[str, IsoFileEntry] = {}   # keyed by logical path like "DATA/TIM/LEVEL1.TIM"
        self._root_entries: List[IsoFileEntry] = []

    def open(self) -> bool:
        """Open and probe the image. Returns True if ISO 9660 Primary Volume Descriptor found."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Image not found: {self.file_path}")

        self.fp = open(self.file_path, "rb")

        # Detect whether image is 2048 or 2352 bytes/sector by probing PVD
        if self._probe_sector_size():
            return True
        return False

    def close(self):
        if self.fp:
            self.fp.close()
            self.fp = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _probe_sector_size(self) -> bool:
        """Try 2048 and 2352 offsets to locate PVD at sector 16."""
        # Attempt 1: raw 2048 (data starts at byte 0 of each sector)
        if self._check_pvd_at(2048, 0):
            self._sector_size = 2048
            self._data_offset = 0
            return True
        # Attempt 2: 2352 MODE1 (sync 12 + header 4 + data 2048 + ecc 276 + eedc 4)
        # User data begins at offset 0x10 within each 2352 sector for MODE1
        if self._check_pvd_at(2352, 0x10):
            self._sector_size = 2352
            self._data_offset = 0x10
            return True
        # Attempt 3: 2352 MODE2 XA Form 1 — user data at offset 0x18
        if self._check_pvd_at(2352, 0x18):
            self._sector_size = 2352
            self._data_offset = 0x18
            return True
        return False

    def _check_pvd_at(self, sector_size: int, data_offset: int) -> bool:
        """Look for Primary Volume Descriptor signature at sector 16."""
        self.fp.seek(0)
        pvd_byte = 16 * sector_size + data_offset
        self.fp.seek(pvd_byte)
        sig = self.fp.read(7)
        return sig == b"\x01CD001\x01"  # PVD type 1

    def _read_sector(self, lba: int, count: int = 1) -> bytes:
        """Read 'count' sectors starting at LBA. Returns concatenated data bytes."""
        if not self.fp:
            raise RuntimeError("Parser not open")
        self.fp.seek(lba * self._sector_size + self._data_offset)
        # If 2352, we only want the 2048 user-data bytes per sector
        if self._sector_size == SECTOR_SIZE_2352:
            data = b""
            for _ in range(count):
                data += self.fp.read(SECTOR_SIZE_2048)
                self.fp.seek(self._sector_size - SECTOR_SIZE_2048, os.SEEK_CUR)
            return data
        return self.fp.read(SECTOR_SIZE_2048 * count)

    def parse(self):
        """Parse the ISO 9660 filesystem tree."""
        # PVD is at sector 16
        pvd = self._read_sector(16)
        # Volume label at offset 0x28 (40) for 32 bytes
        self.volume_label = pvd[0x28:0x28 + 32].decode("ascii", errors="ignore").strip()

        # Root directory entry — try BOTH offsets (0x9C and 0x9E)
        # ISO 9660 standard says 0x9C (156), some implementations use 0x9E (158)
        root_lba, root_size = self._find_root_directory(pvd)

        if root_lba == 0 or root_size == 0:
            raise ValueError("Could not locate root directory in ISO 9660 PVD")

        self._parse_directory("", root_lba, root_size)

    def _find_root_directory(self, pvd: bytes) -> Tuple[int, int]:
        """Find the root directory LBA and size from the PVD.
        
        Tries offset 0x9C first (ISO 9660 standard), then 0x9E (common alternative).
        Validates by checking that the resulting LBA points to readable directory data.
        """
        for offset in (0x9C, 0x9E):
            if offset + 34 > len(pvd):
                continue
            entry = pvd[offset:offset + 34]
            lba = struct.unpack_from("<I", entry, 2)[0]
            size = struct.unpack_from("<I", entry, 10)[0]
            
            # Basic sanity checks
            if lba < 16 or lba > 0xFFFFFFFF // self._sector_size:
                continue
            if size == 0 or size > 10 * 1024 * 1024:  # Max 10MB for a directory
                continue
            
            # Verify: try to read the first few bytes at that LBA
            # A valid directory should start with a record for "."
            try:
                test_data = self._read_sector(lba, 1)[:min(size, 64)]
                if len(test_data) >= 34 and test_data[0] >= 34:
                    # Check if first entry is "." (current dir)
                    name_len = test_data[32]
                    name = test_data[33:33 + name_len].decode("ascii", errors="ignore")
                    if name == "." or name == "\x00":
                        return lba, size
                    # Even if name doesn't match, if record length looks valid, use it
                    return lba, size
            except Exception:
                continue
        
        # Fallback: scan the PVD for any directory record-like structure
        for offset in range(0x80, min(len(pvd) - 34, 0x200)):
            entry = pvd[offset:offset + 34]
            lba = struct.unpack_from("<I", entry, 2)[0]
            size = struct.unpack_from("<I", entry, 10)[0]
            if lba > 16 and 0 < size < 10 * 1024 * 1024:
                return lba, size
        
        return 0, 0

    def _parse_directory(self, path_prefix: str, lba: int, size: int):
        """Recursively parse an ISO 9660 directory table."""
        data = self._read_sector(lba, (size // SECTOR_SIZE_2048) + 1)[:size]
        idx = 0
        while idx < size:
            rec_len = data[idx]
            if rec_len == 0:
                idx += 1
                continue
            if idx + rec_len > len(data):
                break

            entry = self._parse_dir_record(data[idx:idx + rec_len], path_prefix)
            idx += rec_len
            if entry is None:
                continue

            logical_path = f"{path_prefix}/{entry.name}".lstrip("/")
            if entry.is_directory:
                if entry.name not in (".", ".."):
                    self._parse_directory(logical_path, entry.lba, entry.size)
            else:
                entry.parent_path = path_prefix.lstrip("/")
                self.files[logical_path] = entry

    def _parse_dir_record(self, record: bytes, parent: str) -> Optional[IsoFileEntry]:
        """Parse a single ISO 9660 directory record."""
        if len(record) < 34:
            return None
        rec_len = record[0]
        ext_attr_len = record[1]
        lba = struct.unpack_from("<I", record, 2)[0]
        size = struct.unpack_from("<I", record, 10)[0]
        flags = record[25]
        is_dir = bool(flags & 0x02)
        name_len = record[32]
        name_bytes = record[33:33 + name_len]
        name = name_bytes.decode("ascii", errors="ignore").strip()

        return IsoFileEntry(
            name=name,
            ext_name=name,  # Joliet / Rock Ridge parsing omitted for brevity
            is_directory=is_dir,
            lba=lba,
            size=size,
            parent_path=parent,
            raw_sector_size=self._sector_size,
            data_offset_in_sector=self._data_offset,
        )

    def extract_file(self, logical_path: str, dest_path: Optional[str] = None) -> bytes:
        """Extract a file by logical ISO path. Returns bytes; optionally writes to disk."""
        entry = self.files.get(logical_path)
        if not entry:
            raise KeyError(f"File not found in ISO: {logical_path}")

        data = self._read_sector(entry.lba, (entry.size // SECTOR_SIZE_2048) + 1)[:entry.size]
        if dest_path:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(data)
        return data

    def extract_all(self, dest_dir: str, progress_callback=None):
        """Extract every file to a destination directory tree."""
        for idx, (lpath, entry) in enumerate(self.files.items()):
            dest = os.path.join(dest_dir, lpath)
            self.extract_file(lpath, dest)
            if progress_callback:
                progress_callback(idx + 1, len(self.files))

    def list_files(self) -> List[str]:
        """Return all logical file paths in the ISO."""
        return list(self.files.keys())


class CueSheetParser:
    """Minimal CUE sheet parser to resolve which BIN file to open."""

    @staticmethod
    def resolve_bin(cue_path: str) -> str:
        """Given a .cue, find the referenced .bin (same dir, first FILE line)."""
        cue_dir = os.path.dirname(os.path.abspath(cue_path))
        with open(cue_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.search(r'FILE\s+"([^"]+)"', line, re.IGNORECASE)
                if m:
                    bin_name = m.group(1)
                    bin_path = os.path.join(cue_dir, bin_name)
                    if os.path.exists(bin_path):
                        return bin_path
        # Try same name with .bin extension
        fallback = os.path.join(cue_dir, Path(cue_path).stem + ".bin")
        if os.path.exists(fallback):
            return fallback
        raise FileNotFoundError(f"Could not resolve BIN from CUE: {cue_path}")


def convert_chd_to_bin(chd_path: str) -> str:
    """Convert .chd to a temporary .bin file using chdman if available."""
    # Check for chdman
    chdman_paths = ["chdman", "chdman.exe"]
    chdman = None
    for cmd in chdman_paths:
        try:
            result = subprocess.run([cmd, "--help"], capture_output=True, timeout=5)
            if result.returncode == 0:
                chdman = cmd
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    
    if not chdman:
        raise RuntimeError(
            "chdman not found. Please install MAME tools or extract the CHD manually.\n"
            "CHD files must be converted to BIN/CUE or ISO before use.\n"
            "Download chdman from: https://www.mamedev.org"
        )
    
    # Create temp output files
    temp_dir = tempfile.mkdtemp(prefix="bubsy_chd_")
    base_name = Path(chd_path).stem
    out_bin = os.path.join(temp_dir, base_name + ".bin")
    out_cue = os.path.join(temp_dir, base_name + ".cue")
    
    # Run chdman extractcd
    result = subprocess.run(
        [chdman, "extractcd", "-i", chd_path, "-o", out_cue, "-ob", out_bin],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"chdman failed: {result.stderr}\n{result.stdout}")
    
    if not os.path.exists(out_bin):
        raise RuntimeError(f"chdman did not produce output: {out_bin}")
    
    return out_bin


def open_ps1_image(path: str) -> ISOParser:
    """
    Factory: open a PS1 disc image, whether .iso, .bin, .cue, or .chd.
    Returns a ready-to-use ISOParser.
    
    For .chd files, attempts to use chdman to convert to BIN first.
    """
    ext = Path(path).suffix.lower()
    actual_path = path
    
    if ext == ".chd":
        # Convert CHD to BIN
        actual_path = convert_chd_to_bin(path)
        print(f"Converted CHD to temporary BIN: {actual_path}")
    
    if ext == ".cue":
        bin_path = CueSheetParser.resolve_bin(actual_path)
        parser = ISOParser(bin_path)
    else:
        parser = ISOParser(actual_path)
    
    if not parser.open():
        raise ValueError(
            f"Could not detect ISO 9660 filesystem in {path}\n"
            f"Tried sector sizes: 2048, 2352 (MODE1), 2352 (MODE2 XA)\n"
            f"The file may be corrupted, not a PS1 disc image, or use an unsupported format."
        )
    parser.parse()
    return parser
