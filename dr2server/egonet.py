from __future__ import annotations

import base64
import struct
from typing import Any, Dict, Tuple


class Timestamp:
    """Wrapper to encode a value as tutc (4-byte Unix timestamp)."""
    __slots__ = ("value",)
    def __init__(self, value: int) -> None:
        self.value = value


class UInt32:
    """Wrapper to encode a value as ui32 (unsigned 32-bit integer)."""
    __slots__ = ("value",)
    def __init__(self, value: int) -> None:
        self.value = value


class UInt8:
    """Wrapper to encode a value as ui08 (unsigned 8-bit integer)."""
    __slots__ = ("value",)
    def __init__(self, value: int) -> None:
        self.value = value


class Int64:
    """Wrapper to force si64 encoding even for small values."""
    __slots__ = ("value",)
    def __init__(self, value: int) -> None:
        self.value = value


def decode_stream(payload: bytes) -> Dict[str, Any]:
    if len(payload) < 8 or payload[:4] != b"vdic":
        return {"raw_base64": base64.b64encode(payload).decode("ascii")}

    offset = 4
    count = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    result: Dict[str, Any] = {}

    for _ in range(count):
        if offset >= len(payload):
            break

        key_len = payload[offset]
        offset += 1
        key = payload[offset : offset + key_len].decode("ascii", errors="replace")
        offset += key_len

        value, offset = _decode_value(payload, offset)
        result[key] = value

    return result


def encode_stream(values: Dict[str, Any]) -> bytes:
    body = bytearray()
    body.extend(b"vdic")
    body.extend(struct.pack("<I", len(values)))

    for key, value in values.items():
        encoded_key = key.encode("ascii")
        if len(encoded_key) > 255:
            raise ValueError("keys must fit in one byte")
        body.append(len(encoded_key))
        body.extend(encoded_key)
        body.extend(_encode_value(value))

    return bytes(body)


def _decode_value(payload: bytes, offset: int) -> Tuple[Any, int]:
    marker = payload[offset : offset + 1]
    offset += 1

    if marker == b"v":
        value_type = payload[offset : offset + 3]
        offset += 3
        if value_type == b"dic":
            count = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            result: Dict[str, Any] = {}
            for _ in range(count):
                key_len = payload[offset]
                offset += 1
                key = payload[offset : offset + key_len].decode("ascii", errors="replace")
                offset += key_len
                value, offset = _decode_value(payload, offset)
                result[key] = value
            return result, offset
        if value_type == b"vtr":
            count = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            items = []
            for _ in range(count):
                value, offset = _decode_value(payload, offset)
                items.append(value)
            return items, offset
        return {"unsupported_vector_type": value_type.decode("ascii", errors="replace")}, offset

    if marker == b"b":
        value_type = payload[offset : offset + 3]
        offset += 3
        if value_type == b"ool":
            return payload[offset] != 0, offset + 1
        if value_type == b"lob":
            size = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            data = payload[offset : offset + size]
            return {"blob_base64": base64.b64encode(data).decode("ascii"), "size": size}, offset + size
        return {"unsupported_marker": marker.decode("ascii", errors="replace")}, offset

    # Timestamp type: tutc = 4-byte Unix timestamp
    if marker == b"t":
        value_type = payload[offset : offset + 3]
        offset += 3
        if value_type == b"utc":
            return Timestamp(struct.unpack_from("<I", payload, offset)[0]), offset + 4
        return {"unsupported_time_type": value_type.decode("ascii", errors="replace")}, offset

    if marker not in {b"s", b"d", b"u", b"f"}:
        return {"unsupported_marker": marker.decode("ascii", errors="replace")}, offset

    value_type = payload[offset : offset + 3]
    offset += 3

    # Float types
    if marker == b"f":
        if value_type == b"p32":
            return struct.unpack_from("<f", payload, offset)[0], offset + 4
        if value_type == b"p64":
            return struct.unpack_from("<d", payload, offset)[0], offset + 8
        return {"unsupported_float_type": value_type.decode("ascii", errors="replace")}, offset

    # Unsigned integers — preserve type via wrapper so re-encoding matches
    if marker == b"u":
        if value_type == b"i08":
            return UInt8(payload[offset]), offset + 1
        if value_type == b"i16":
            return struct.unpack_from("<H", payload, offset)[0], offset + 2
        if value_type == b"i32":
            return UInt32(struct.unpack_from("<I", payload, offset)[0]), offset + 4
        if value_type == b"i64":
            return struct.unpack_from("<Q", payload, offset)[0], offset + 8

    # Signed integers (marker == b"s")
    if value_type == b"i08":
        return payload[offset], offset + 1
    if value_type == b"i16":
        return struct.unpack_from("<h", payload, offset)[0], offset + 2
    if value_type == b"i32":
        return struct.unpack_from("<i", payload, offset)[0], offset + 4
    if value_type == b"i64":
        return Int64(struct.unpack_from("<q", payload, offset)[0]), offset + 8
    if value_type == b"str":
        size = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        return payload[offset : offset + size].decode("utf-8", errors="replace"), offset + size
    if value_type == b"boo":
        return payload[offset] != 0, offset + 1

    return {"unsupported_type": value_type.decode("ascii", errors="replace")}, offset


def _encode_value(value: Any) -> bytes:
    if isinstance(value, Timestamp):
        return b"tutc" + struct.pack("<I", value.value)
    if isinstance(value, UInt8):
        return b"ui08" + struct.pack("<B", value.value)
    if isinstance(value, UInt32):
        return b"ui32" + struct.pack("<I", value.value)
    if isinstance(value, Int64):
        return b"si64" + struct.pack("<q", value.value)
    if isinstance(value, bool):
        return b"bool" + (b"\x01" if value else b"\x00")
    if isinstance(value, float):
        return b"fp32" + struct.pack("<f", value)
    if isinstance(value, int):
        # Always use si32 minimum — the game client expects si32 for most fields.
        # Using si16 causes misalignment crashes.
        if -(2**31) <= value < 2**31:
            return b"si32" + struct.pack("<i", value)
        return b"si64" + struct.pack("<q", value)
    if isinstance(value, str):
        data = value.encode("utf-8")
        return b"dstr" + struct.pack("<I", len(data)) + data
    if isinstance(value, bytes):
        return b"blob" + struct.pack("<I", len(value)) + value
    if isinstance(value, dict):
        return encode_stream(value)
    if isinstance(value, (list, tuple)):
        body = bytearray()
        body.extend(b"vvtr")
        body.extend(struct.pack("<I", len(value)))
        for item in value:
            body.extend(_encode_value(item))
        return bytes(body)
    raise TypeError(f"unsupported egonet value: {type(value)!r}")
