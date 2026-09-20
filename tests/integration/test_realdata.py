"""Local-only checks against a real export; never run in CI.

    NOTE_WXR_REALDATA_ZIP=/path/to/export.zip uv run pytest -m realdata

Nothing from the export is printed or copied into the repository.
"""

import os
import zipfile
from pathlib import Path

import pytest

from note_wxr_tools.frontmatter import parse as parse_front_matter
from note_wxr_tools.to_md import convert as to_md
from note_wxr_tools.to_wxr import convert as to_wxr
from note_wxr_tools.validate import validate
from note_wxr_tools.wxr import Source, parse

pytestmark = pytest.mark.realdata


@pytest.fixture
def export_zip() -> Path:
    value = os.environ.get("NOTE_WXR_REALDATA_ZIP")
    if not value or not Path(value).is_file():
        pytest.skip("NOTE_WXR_REALDATA_ZIP is not set to an export ZIP")
    return Path(value)


def _generated_titles(export_zip: Path, folder: Path) -> dict[str, str]:
    """Map each generated title to the original one it replaced."""
    originals = {
        item.fields["guid"]: item.fields["title"]
        for item in parse(Source(export_zip).read_xml()).items
    }
    changed = {}
    for path in folder.glob("*.md"):
        props, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        original = originals[props["platform_post_id"]]
        if props["title"] != original:
            changed[props["title"]] = original
    return changed


def test_real_export_round_trips_byte_for_byte(
    export_zip: Path, tmp_path: Path
) -> None:
    to_md(export_zip, tmp_path / "md", allow_lossy=True)
    folder = next((tmp_path / "md").iterdir())
    assert validate(folder).errors == []

    report = to_wxr(sorted(folder.glob("*.md")), tmp_path / "wxr")

    with (
        zipfile.ZipFile(export_zip) as original,
        zipfile.ZipFile(report.zip_path) as rebuilt,
    ):
        xml_name = next(n for n in original.namelist() if n.endswith(".xml"))
        expected = original.read(xml_name).decode("utf-8")
        actual = rebuilt.read(xml_name).decode("utf-8")
        for generated, title in _generated_titles(export_zip, folder).items():
            # Automatically named titles are the only intended difference.
            actual = actual.replace(
                f"<![CDATA[{generated}]]>", f"<![CDATA[{title}]]>", 1
            )
        assert actual == expected
        for name in original.namelist():
            if name.startswith("assets/") and not name.endswith("/"):
                assert rebuilt.read(name) == original.read(name)
