"""Tests for SkelToJson package."""

import base64
import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

from SkelToJson import SkelConverter, convert_skel_to_json

# Minimal Spine 4.2 skeleton: 1 bone, 1 slot, 1 sequence attachment
SAMPLE_SKEL_B64 = (
    "wrOoSC7kMlYHNC4yLjQzwxYAAMPeAABDlgAARGEAAELIAAAAAR9hbnRpY2lwYXRpb252Mi9hbnRp"
    "Y2lwYXRpb252Ml8BBXJvb3QAAAAAAAAAAAAAAAA/gAAAP4AAAAAAAAAAAAAAAAAAAAAAAQ1hbnRp"
    "Y2lwYXRpb24A//////////8BAAAAAAABAAEBQB8AAgAAAAAAQMAAAD+AAAA/gAAAQ5YAAERhAAAA"
    "AAEKYW5pbWF0aW9uAQAAAAAAAAEAAQABAQECAAAAAAAAAAI9CIiJP4AAAAAAAAI9CIiJAAA="
)
SAMPLE_SKEL = base64.b64decode(SAMPLE_SKEL_B64)

# Resolve data directory (only for local mass tests)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
OUTPUT_DIR = WORKSPACE_ROOT / "test_output_pkg"


def _skel_files():
    """Collect all .skel files for parametrized tests."""
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.rglob("*.skel"))


# ── Unit tests (always run, no external data needed) ──────────────────


class TestSkelConverter:
    """Core converter tests."""

    def test_empty_data_raises(self):
        converter = SkelConverter()
        with pytest.raises(Exception):
            converter.convert(b"")

    def test_convert_sample(self):
        """Convert the embedded sample .skel and validate structure."""
        converter = SkelConverter()
        result = converter.convert(SAMPLE_SKEL)

        assert isinstance(result, dict)
        assert "skeleton" in result
        assert result["skeleton"]["spine"] == "4.2.43"
        assert result["skeleton"]["width"] == 300
        assert result["skeleton"]["height"] == 900

    def test_bones(self):
        result = SkelConverter().convert(SAMPLE_SKEL)
        assert len(result["bones"]) == 1
        assert result["bones"][0]["name"] == "root"

    def test_slots(self):
        result = SkelConverter().convert(SAMPLE_SKEL)
        assert len(result["slots"]) == 1
        assert result["slots"][0]["name"] == "anticipation"
        assert result["slots"][0]["bone"] == "root"

    def test_skins(self):
        result = SkelConverter().convert(SAMPLE_SKEL)
        assert len(result["skins"]) == 1
        assert result["skins"][0]["name"] == "default"
        assert "attachments" in result["skins"][0]

    def test_animations(self):
        result = SkelConverter().convert(SAMPLE_SKEL)
        assert "animations" in result
        assert "animation" in result["animations"]

    def test_json_serializable(self):
        """Result must be fully JSON-serializable."""
        result = SkelConverter().convert(SAMPLE_SKEL)
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["skeleton"]["spine"] == "4.2.43"

    def test_convert_skel_to_json_file(self):
        """Test the file-based conversion API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skel_path = Path(tmpdir) / "test.skel"
            json_path = Path(tmpdir) / "test.json"
            skel_path.write_bytes(SAMPLE_SKEL)

            result = convert_skel_to_json(str(skel_path), str(json_path))

            assert json_path.exists()
            assert json_path.stat().st_size > 0
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            assert loaded["skeleton"]["spine"] == "4.2.43"

    def test_unsupported_version_raises(self):
        """Tamper version bytes to trigger unsupported version error."""
        # Replace "4.2.43" with "3.8.00" in the binary
        bad_data = SAMPLE_SKEL.replace(b"4.2.43", b"3.8.00")
        converter = SkelConverter()
        with pytest.raises(ValueError, match="Unsupported Spine version"):
            converter.convert(bad_data)


# ── Local-only parametrized tests (skipped in CI) ─────────────────────


@pytest.mark.skipif(not DATA_DIR.exists(), reason="No data/ directory")
class TestLocalSkels:
    """Run against all local .skel files (skipped in CI)."""

    @pytest.mark.parametrize(
        "skel_file",
        _skel_files(),
        ids=lambda p: str(p.relative_to(DATA_DIR)) if DATA_DIR.exists() else str(p),
    )
    def test_convert_skel(self, skel_file: Path):
        data = skel_file.read_bytes()
        converter = SkelConverter()
        result = converter.convert(data)

        assert isinstance(result, dict)
        assert "skeleton" in result
        assert "spine" in result["skeleton"]

        assert failed == 0, f"{failed} files failed conversion"
