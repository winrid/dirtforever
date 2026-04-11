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
        """Return a default (all-zero) tuning blob.

        The 222-byte payload matches the observed size for DR2 cars.
        All-zero payload means "use car defaults" for most fields.
        """
        # Observed layout: 8 bytes of counts (3, 1) + 214 bytes of tuning data
        payload = struct.pack("<II", 3, 1) + b"\x00" * 214
        return cls(version=1, uncompressed_size=len(payload), payload=payload)


def decode_tuning_blob(data: bytes) -> Optional[TuningBlob]:
    """Module-level convenience wrapper."""
    return TuningBlob.decode(data)
