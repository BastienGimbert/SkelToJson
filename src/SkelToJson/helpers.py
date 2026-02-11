"""Helper functions for Spine binary format conversion."""

import math


def rf(value: float, precision: int = 5):
    """Round float, convert to int if whole number."""
    if math.isnan(value) or math.isinf(value):
        return value
    r = round(value, precision)
    if r == int(r) and abs(r) < 2**31:
        return int(r)
    return r


def color_to_rgba_hex(r: int, g: int, b: int, a: int) -> str:
    """Convert 4 bytes (0-255) to RGBA hex color string."""
    return f"{r:02x}{g:02x}{b:02x}{a:02x}"


def color_to_rgb_hex(r: int, g: int, b: int) -> str:
    """Convert 3 bytes (0-255) to RGB hex color string."""
    return f"{r:02x}{g:02x}{b:02x}"


def int32_to_rgba_hex(val: int) -> str:
    """Convert signed int32 to RGBA hex string."""
    if val < 0:
        val += 0x100000000
    return (
        f"{(val >> 24) & 0xFF:02x}{(val >> 16) & 0xFF:02x}"
        f"{(val >> 8) & 0xFF:02x}{val & 0xFF:02x}"
    )


def int32_to_rgb_hex(val: int) -> str:
    """Convert signed int32 to RGB hex string."""
    if val < 0:
        val += 0x100000000
    return (
        f"{(val >> 24) & 0xFF:02x}{(val >> 16) & 0xFF:02x}"
        f"{(val >> 8) & 0xFF:02x}"
    )
