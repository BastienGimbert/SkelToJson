"""SkelToJson — Convert Spine binary .skel files to JSON.

Supports Spine 4.2.x and 4.3.x binary formats.

Usage::

    from SkelToJson import convert_skel_to_json, convert_directory, SkelConverter

    # Convert a single file
    convert_skel_to_json("skeleton.skel", "skeleton.json")

    # Convert all .skel files in a directory
    convert_directory("skeletons/", "output/")

    # Low-level API
    converter = SkelConverter()
    result = converter.convert(skel_bytes)
"""

__version__ = "1.0.0"

from .binary_input import BinaryInput
from .converter import SkelConverter, convert_directory, convert_skel_to_json

__all__ = [
    "BinaryInput",
    "SkelConverter",
    "convert_directory",
    "convert_skel_to_json",
]
