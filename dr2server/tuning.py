"""DR2 tuning setup blob decoder.

The TuningSetup field in StageBegin/Championship requests is a binary blob
with this structure:

    offset  size  field
    ------  ----  --------
    0       4     version (always 1 observed)
    4       4     header_size (always 16)
    8       4     uncompressed_size
    12      4     reserved (always 0)
    16      N     zlib-deflated payload

The deflated payload starts with two uint32s (unknown purpose, likely
section/record counts — observed as 3 and 1), followed by a mix of floats
and small integers representing the car's tuning parameters.

Full field-level decoding is not yet complete. This module currently
supports encode/decode of the outer container, which is enough to
round-trip tuning blobs without corruption.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class TuningBlob:
    version: int
    uncompressed_size: int
    payload: bytes  # decompressed tuning data

    @classmethod
    def decode(cls, data: bytes) -> Optional[TuningBlob]:
        """Decode a tuning blob. Returns None on malformed data."""
        if len(data) < 16:
            return None
        version = struct.unpack_from("<I", data, 0)[0]
        header_size = struct.unpack_from("<I", data, 4)[0]
        uncompressed_size = struct.unpack_from("<I", data, 8)[0]

        if header_size != 16:
            return None

        try:
            payload = zlib.decompress(data[header_size:])
        except zlib.error:
            return None

        if len(payload) != uncompressed_size:
            return None

        return cls(version=version, uncompressed_size=uncompressed_size, payload=payload)

    def encode(self) -> bytes:
        """Re-encode the blob. Uses default zlib compression level (matches observed)."""
        compressed = zlib.compress(self.payload, level=6)
        header = struct.pack("<IIII", self.version, 16, self.uncompressed_size, 0)
        return header + compressed

    @classmethod
    def default(cls) -> TuningBlob:
        """Return a default tuning blob.

        Uses the exact 140-byte blob observed from upstream Clubs.GetClubs
        Progress entries (all defaults / untuned car).
        """
        # Decoded content is 222 bytes (matches upstream uncompressed_size)
        payload = zlib.decompress(bytes.fromhex(
            "789c63666060606400819cf8f43d25b90c0c6f022dec1914445c41626969cfec66ce"
            "9c69c7c0a0e0c4402478b174b6dd998397ed5eca70dbff6f31b0b70f88b0676068b0"
            "07c9852648d8715d5fbca7e423b7074471831b03c383fd2026489c4b618d3b583c45"
            "0c482fd83f6ba6a41db1f62200c42e100000ba10239c"
        ))
        return cls(version=1, uncompressed_size=len(payload), payload=payload)

    @classmethod
    def default_bytes(cls) -> bytes:
        """Return the raw 140-byte default blob as-is (no re-compression)."""
        return bytes.fromhex(
            "0100000010000000de00000000000000"
            "789c63666060606400819cf8f43d25b90c0c6f022dec1914445c41626969cfec66ce"
            "9c69c7c0a0e0c4402478b174b6dd998397ed5eca70dbff6f31b0b70f88b0676068b0"
            "07c9852648d8715d5fbca7e423b7074471831b03c383fd2026489c4b618d3b583c45"
            "0c482fd83f6ba6a41db1f62200c42e100000ba10239c"
        )


def decode_tuning_blob(data: bytes) -> Optional[TuningBlob]:
    """Module-level convenience wrapper."""
    return TuningBlob.decode(data)
