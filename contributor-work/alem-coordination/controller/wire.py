"""Bounded UTF-8 JSON frames. No pickle or candidate object deserialization."""
import json
import struct

MAX_FRAME = 2_097_152


def decode(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value
    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def pack(value):
    data = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if len(data) > MAX_FRAME:
        raise ValueError("frame too large")
    return struct.pack("!I", len(data)) + data


def read(stream):
    def exact(size, allow_eof=False):
        chunks = []
        remaining = size
        while remaining:
            chunk = stream.read(remaining)
            if not chunk:
                if allow_eof and remaining == size:
                    return None
                raise EOFError("short frame")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    header = exact(4, allow_eof=True)
    if header is None:
        return None
    size = struct.unpack("!I", header)[0]
    if size > MAX_FRAME:
        raise ValueError("frame too large")
    return decode(exact(size))


def write(stream, value):
    stream.write(pack(value))
    stream.flush()
