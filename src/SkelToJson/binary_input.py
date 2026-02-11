from __future__ import annotations

import struct


class BinaryInput:
    """Reads primitive types from Spine's big-endian binary format."""

    def __init__(self, data: bytes):
        self.data = data
        self.index = 0
        self.strings: list[str] = []

    # ── Primitives ────────────────────────────────────────────────────────

    def read_byte(self) -> int:
        val = self.data[self.index]
        self.index += 1
        return val

    def read_sbyte(self) -> int:
        val = self.read_byte()
        return val - 256 if val > 127 else val

    def read_boolean(self) -> bool:
        return self.read_byte() != 0

    def read_int32(self) -> int:
        """Read 4-byte big-endian signed int."""
        val = struct.unpack_from(">i", self.data, self.index)[0]
        self.index += 4
        return val

    def read_float(self) -> float:
        """Read 4-byte big-endian float."""
        val = struct.unpack_from(">f", self.data, self.index)[0]
        self.index += 4
        return val

    # ── Variable-length encoding ──────────────────────────────────────────

    def read_varint(self, optimize_positive: bool = True) -> int:
        """Read variable-length integer (1-5 bytes)."""
        b = self.read_byte()
        value = b & 0x7F
        if b & 0x80:
            b = self.read_byte()
            value |= (b & 0x7F) << 7
            if b & 0x80:
                b = self.read_byte()
                value |= (b & 0x7F) << 14
                if b & 0x80:
                    b = self.read_byte()
                    value |= (b & 0x7F) << 21
                    if b & 0x80:
                        value |= (self.read_byte() & 0x7F) << 28
        if not optimize_positive:
            value = (value >> 1) ^ -(value & 1)
        return value

    # ── Strings ───────────────────────────────────────────────────────────

    def read_string(self) -> str | None:
        """Read length-prefixed modified UTF-8 string. Returns ``None`` for null."""
        byte_count = self.read_varint(True)
        if byte_count == 0:
            return None
        if byte_count == 1:
            return ""
        byte_count -= 1
        raw = self.data[self.index : self.index + byte_count]
        self.index += byte_count
        return self._decode_modified_utf8(raw)

    @staticmethod
    def _decode_modified_utf8(data: bytes) -> str:
        """Decode Java-style modified UTF-8 used by Spine binary format."""
        chars: list[str] = []
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b & 0x80 == 0:  # 0xxxxxxx — single byte
                chars.append(chr(b))
                i += 1
            elif b >> 5 == 0b110:  # 110xxxxx — two bytes
                if i + 1 < n:
                    c2 = data[i + 1]
                    chars.append(chr(((b & 0x1F) << 6) | (c2 & 0x3F)))
                    i += 2
                else:
                    chars.append("?")
                    i += 1
            elif b >> 4 == 0b1110:  # 1110xxxx — three bytes
                if i + 2 < n:
                    c2 = data[i + 1]
                    c3 = data[i + 2]
                    chars.append(
                        chr(((b & 0x0F) << 12) | ((c2 & 0x3F) << 6) | (c3 & 0x3F))
                    )
                    i += 3
                else:
                    chars.append("?")
                    i += 1
            else:
                chars.append("?")
                i += 1
        return "".join(chars)

    def read_string_ref(self) -> str | None:
        """Read string reference from the strings table."""
        idx = self.read_varint(True)
        return None if idx == 0 else self.strings[idx - 1]

    # ── Colors ────────────────────────────────────────────────────────────

    def read_color_int(self) -> int:
        """Read RGBA color as 32-bit int."""
        return self.read_int32()

    def read_color_bytes(self) -> tuple[int, int, int, int]:
        """Read RGBA as 4 separate bytes."""
        return (self.read_byte(), self.read_byte(), self.read_byte(), self.read_byte())
