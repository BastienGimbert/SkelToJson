from __future__ import annotations

import argparse
import sys

from .converter import convert_directory, convert_skel_to_json


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert Spine binary .skel files to JSON (Spine 4.2/4.3)",
    )
    parser.add_argument("input", help="Input .skel file or directory")
    parser.add_argument("-o", "--output", help="Output .json file or directory")
    parser.add_argument(
        "--indent",
        default="\t",
        help="JSON indentation (default: tab)",
    )

    args = parser.parse_args()

    from pathlib import Path

    input_path = Path(args.input)

    if input_path.is_dir():
        convert_directory(str(input_path), args.output)
    elif input_path.is_file():
        convert_skel_to_json(str(input_path), args.output, indent=args.indent)
    else:
        print(f"Error: '{args.input}' not found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
